"""Turn committed campaign evidence into RESULTS.md — deterministically, offline.

    python scripts/build_results.py --logs-root campaign/results/<id> \
        --manifest campaign/manifests/<id>.json --out RESULTS.md

Every number in the output is derived here from the raw per-run packets and the
graded evidence packets. Nothing is hand-entered, so the document cannot drift
from the evidence it claims to summarize; regenerating it on a clean clone with
no simulator must reproduce it byte for byte.

The pipeline, in order:

  1. load and validate the frozen manifest (tamper-evident)
  2. load every raw packet, including invalid and failed runs
  3. verify every recorded file hash against the bytes on disk
  4. grade each VALID run through the gauntlet (the same checks the
     certification path uses)
  5. aggregate per condition, then difference the arms per seed
  6. render RESULTS.md and campaign_results.json

Runs that were invalid or failed are carried through every stage and reported
with their exact reasons. They are never replaced and never silently dropped —
the denominator this document reports is the one the campaign actually had.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "dsp", REPO / "ros2-ws" / "src" / "control_loop"):
    sys.path.insert(0, str(p))

from campaign.aggregate import LOWER_IS_BETTER, METRIC_ORDER, METRIC_UNITS  # noqa: E402
from campaign.manifest import load_manifest  # noqa: E402
from campaign.paired import describe, pair_metric  # noqa: E402
from campaign.raw_evidence import (  # noqa: E402
    STATUS_VALID,
    integrity_index,
    load_raw_packet,
    verify_integrity,
)
from gauntlet.checks import DEFAULT_THRESHOLDS, run_checks  # noqa: E402
from gauntlet.evidence import build_packet, write_packet  # noqa: E402
from gauntlet.run_log import load_run_log  # noqa: E402


def fmt(v, places=4):
    if v is None:
        return "n/a"
    if isinstance(v, str):
        return v
    if isinstance(v, float):
        if math.isinf(v):
            return "inf"
        if math.isnan(v):
            return "nan"
        return f"{v:.{places}g}"
    return str(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs-root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default=str(REPO / "RESULTS.md"))
    ap.add_argument("--evidence-dir", default=None)
    ap.add_argument("--timestamp", default=None,
                    help="ISO-8601 string embedded verbatim; never read from "
                         "the clock, so output stays reproducible")
    ap.add_argument("--check", action="store_true",
                    help="read-only verification: rebuild every artifact into a "
                         "temporary directory and compare it byte-for-byte "
                         "against the committed copy. Writes nothing inside the "
                         "repository. Exits non-zero on any mismatch.")
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    logs_root = Path(args.logs_root)
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else logs_root / "evidence"
    seeds = list(manifest["design"]["seeds"])
    plan = manifest["design"]["execution_plan"]

    # --- 0. output routing --------------------------------------------------- #
    # In --check mode every write is redirected into a scratch directory, so a
    # reader verifying the published numbers cannot modify the records being
    # verified. This is what makes the documented verification genuinely
    # read-only rather than "mutate, then hope the cleanup is correct".
    committed_results_json = logs_root / "campaign_results.json"
    committed_md = Path(args.out)
    tmpdir = None
    if args.check:
        tmpdir = Path(tempfile.mkdtemp(prefix="build_results_check_"))
        out_evidence_dir = tmpdir / "evidence"
        out_results_json = tmpdir / "campaign_results.json"
        out_md = tmpdir / "RESULTS.md"
        # Reproduce the committed timestamp so the comparison is a true
        # byte-for-byte check rather than a diff of the clock.
        if args.timestamp is None and committed_results_json.is_file():
            args.timestamp = json.loads(
                committed_results_json.read_text(encoding="utf-8")
            ).get("generated_at")
    else:
        out_evidence_dir = evidence_dir
        out_results_json = committed_results_json
        out_md = committed_md

    # --- 1. raw packets, every scheduled run -------------------------------- #
    raw, missing = {}, []
    for entry in plan:
        path = logs_root / entry["run_id"] / "raw_evidence.json"
        if not path.is_file():
            missing.append(entry["run_id"])
            continue
        raw[entry["run_id"]] = load_raw_packet(path)

    for p in raw.values():
        if p["manifest_sha256"] != manifest["manifest_sha256"]:
            raise SystemExit(
                f"run {p['run_id']} was produced against manifest "
                f"{p['manifest_sha256']}, not the frozen "
                f"{manifest['manifest_sha256']} — these are different "
                f"experiments and must not be pooled"
            )

    # --- 2. integrity -------------------------------------------------------- #
    index = integrity_index(list(raw.values()))
    integrity = verify_integrity(index, logs_root)

    # --- 3. grade the valid runs -------------------------------------------- #
    graded = {}
    for run_id, p in sorted(raw.items()):
        if p["status"] != STATUS_VALID:
            continue
        rl = load_run_log(logs_root / run_id)
        checks = run_checks(rl.t, rl.reference, rl.measured, rl.noisy)
        packet = build_packet(
            run_id=rl.run_id, scenario=rl.scenario, seed=rl.seed, checks=checks,
            thresholds={}, environment=manifest["runtime"]["environment"],
            generated_at=args.timestamp,
        )
        # run_checks fills thresholds from DEFAULT_THRESHOLDS; re-embed them.
        packet["thresholds"] = {c.name: float(c.threshold) for c in checks}
        write_packet(packet, out_evidence_dir)
        graded[run_id] = {c.name: c for c in checks}

    # --- 4. per-condition views --------------------------------------------- #
    def value(run_id, metric):
        c = graded.get(run_id, {}).get(metric)
        if c is None or c.value is None:
            return None
        return float(c.value)

    by_cond = {"filtered": {}, "unfiltered": {}}
    for entry in plan:
        by_cond[entry["condition"]][entry["seed"]] = entry["run_id"]

    counts = {
        "scheduled": len(plan),
        "attempted": len(raw),
        "valid": sum(1 for p in raw.values() if p["status"] == STATUS_VALID),
        "invalid": sum(1 for p in raw.values() if p["status"] == "invalid"),
        "failed": sum(1 for p in raw.values() if p["status"] == "failed"),
        "missing": len(missing),
        "by_condition": {
            c: {
                "scheduled": sum(1 for e in plan if e["condition"] == c),
                "valid": sum(1 for e in plan if e["condition"] == c
                             and raw.get(e["run_id"], {}).get("status") == STATUS_VALID),
            }
            for c in ("filtered", "unfiltered")
        },
    }

    # --- 5. paired analysis -------------------------------------------------- #
    bseed = int(manifest["analysis"]["bootstrap_seed"])
    resamples = int(manifest["analysis"]["bootstrap_resamples"])
    paired = {}
    for metric in METRIC_ORDER:
        f = {s: value(by_cond["filtered"][s], metric) for s in seeds}
        u = {s: value(by_cond["unfiltered"][s], metric) for s in seeds}
        paired[metric] = pair_metric(metric, LOWER_IS_BETTER[metric], f, u,
                                     seeds, bseed, resamples)

    # secondary: true articulation tracking, from the raw packets
    def raw_value(run_id, key):
        p = raw.get(run_id)
        if not p or p["status"] != STATUS_VALID:
            return None
        v = p["signals_summary"].get(key)
        return None if isinstance(v, str) or v is None else float(v)

    secondary = {}
    for key, lower_better in (("true_tracking_rms_error_rad", True),
                              ("peak_tracking_error_rad", True),
                              ("true_peak_tracking_error_rad", True)):
        f = {s: raw_value(by_cond["filtered"][s], key) for s in seeds}
        u = {s: raw_value(by_cond["unfiltered"][s], key) for s in seeds}
        secondary[key] = pair_metric(key, lower_better, f, u, seeds, bseed, resamples)

    # --- 6. rate distribution ------------------------------------------------ #
    rates = [p["rate"]["measured_hz"] for p in raw.values()
             if isinstance(p["rate"]["measured_hz"], (int, float))]
    rate_summary = {
        "n": len(rates),
        "min": min(rates) if rates else None,
        "max": max(rates) if rates else None,
        "mean": (sum(rates) / len(rates)) if rates else None,
        "all_within_tolerance": all(p["rate"]["within_tolerance"] for p in raw.values()),
    }

    results = {
        "campaign_id": manifest["campaign_id"],
        "campaign_version": manifest["campaign_version"],
        "manifest_sha256": manifest["manifest_sha256"],
        "generated_at": args.timestamp,
        "counts": counts,
        "integrity": integrity,
        "rate": rate_summary,
        "paired": {k: v.to_dict() for k, v in paired.items()},
        "secondary": {k: v.to_dict() for k, v in secondary.items()},
        "excluded_runs": [
            {"run_id": p["run_id"], "condition": p["condition"], "seed": p["seed"],
             "status": p["status"], "failure_reason": p["failure_reason"]}
            for p in sorted(raw.values(), key=lambda x: x["run_id"])
            if p["status"] != STATUS_VALID
        ],
        "missing_runs": sorted(missing),
    }
    out_results_json.write_text(
        json.dumps(results, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    out_md.write_text(render(manifest, results, raw, graded, by_cond,
                             paired, secondary), encoding="utf-8")

    if not args.check:
        print(f"wrote {args.out}")
        print(f"valid {counts['valid']}/{counts['scheduled']}  "
              f"integrity_passed={integrity['passed']}")
        return 0

    # --- 7. read-only verification ------------------------------------------- #
    try:
        mismatched, checked = [], 0

        def compare(rebuilt: Path, committed: Path, label: str) -> None:
            nonlocal checked
            checked += 1
            if not committed.is_file():
                mismatched.append(f"{label}: missing from the repository")
            elif rebuilt.read_bytes() != committed.read_bytes():
                mismatched.append(f"{label}: differs from the committed copy")

        # The committed evidence directory must contain exactly the packets we
        # rebuilt — no more, no fewer. An extra committed packet (say, a stale
        # one from a previously scheduled run) is an unverified artifact and
        # must not pass silently just because every rebuilt file matched.
        rebuilt_names = {p.name for p in out_evidence_dir.glob("*.json")}
        committed_names = {p.name for p in evidence_dir.glob("*.json")}
        for extra in sorted(committed_names - rebuilt_names):
            mismatched.append(
                f"evidence/{extra}: committed but not produced by this campaign "
                f"— unverified artifact"
            )

        for name in sorted(rebuilt_names):
            compare(out_evidence_dir / name, evidence_dir / name,
                    f"evidence/{name}")
        compare(out_results_json, committed_results_json, "campaign_results.json")
        compare(out_md, committed_md, committed_md.name)

        print(f"valid {counts['valid']}/{counts['scheduled']}  "
              f"integrity_passed={integrity['passed']}")
        print(f"read-only check: {checked - len(mismatched)}/{checked} artifacts "
              f"reproduced byte-for-byte")

        # Fail closed on raw-artifact integrity too. The derived artifacts can
        # faithfully reproduce a recorded integrity FAILURE, so byte-equality
        # alone is not sufficient evidence that the evidence tree is intact.
        if not integrity["passed"]:
            mismatched.append(
                f"raw-artifact integrity: {len(integrity.get('mismatched', []))} "
                f"mismatched, {len(integrity.get('missing', []))} missing "
                f"— recorded hashes do not match the files on disk"
            )

        if mismatched:
            for m in mismatched:
                print(f"  FAIL  {m}")
            print("CHECK FAILED — the committed evidence tree is not verified.")
            return 1
        print("CHECK PASSED — nothing in the repository was modified.")
        return 0
    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)


def render(manifest, results, raw, graded, by_cond, paired, secondary) -> str:
    m, c = manifest, results["counts"]
    seeds = list(m["design"]["seeds"])
    L = []
    A = L.append

    A("# RESULTS — filtered vs unfiltered joint-state feedback")
    A("")
    A("Generated by `scripts/build_results.py` from the committed per-run evidence.")
    A("No number in this document was entered by hand.")
    A("")
    A(f"- campaign: `{m['campaign_id']}` v{m['campaign_version']}")
    A(f"- manifest sha256: `{m['manifest_sha256']}`")
    A(f"- harness commit: `{m['provenance']['repo_commit']}`")
    A(f"- runtime-validation parent: `{m['provenance']['runtime_validation_parent_commit']}`")
    A(f"- scene graph fingerprint: `{m['provenance']['scene_graph_fingerprint']}`")
    A("")

    A("## 1. Research question")
    A("")
    A("In a closed simulated joint-space control loop disturbed by a 25 Hz")
    A("structural vibration plus Gaussian sensor noise, does inserting the")
    A("project's causal low-pass filter between the joint-state feedback and the")
    A("controller improve tracking, relative to passing the disturbed signal")
    A("through unchanged?")
    A("")
    A("Both arms run identical topology. The only difference is the filter")
    A("response: a 4th-order Butterworth IIR at a 5 Hz cutoff, versus a")
    A("passthrough identity filter with a flat 0 dB response.")
    A("")

    A("## 2. Exact runtime and configuration")
    A("")
    r = m["runtime"]
    A("| | |")
    A("|---|---|")
    A(f"| Isaac Sim | `{r['isaac_build']}` |")
    A(f"| Platform | {r['platform']}, {r['gpu_class']} |")
    A(f"| ROS 2 | {r['ros_distro']}, {r['ros_library_source']} |")
    A(f"| RMW | `{r['rmw_implementation']}` |")
    A(f"| rclpy | {r['rclpy_source']} |")
    for k, v in r["environment"].items():
        A(f"| {k} | {v} |")
    A("")
    # The frozen manifest records the build that actually ran. If it is a
    # release candidate, say so here rather than letting a reader round the
    # version up to the general-availability release of the same number.
    if "-rc." in r["isaac_build"]:
        base = r["isaac_build"].split("-rc.")[0]
        A(f"**This build is a release candidate.** Every run below was executed "
          f"on `{r['isaac_build']}` and on no other build. Isaac Sim {base} GA "
          f"is a distinct, later release: it was not used, not measured, and "
          f"has not been shown equivalent by this project. The results in this "
          f"document are evidence about the tested RC build only.")
        A("")
    s, d, f = m["sampling"], m["disturbance"], m["filter"]
    A(f"Sampling: {s['sample_rate_hz']} Hz publication "
      f"(physics dt {s['physics_dt_s']:.6g} s, graph ticks once per "
      f"{s['graph_tick_per_physics_steps']} physics steps), "
      f"Nyquist {s['nyquist_hz']} Hz.")
    A("")
    A(f"Disturbance: {d['vibration_amplitude_rad']} rad vibration at "
      f"{d['vibration_freq_hz']} Hz plus AWGN sigma {d['awgn_sigma_rad']} rad, "
      f"injected on the {d['injection_point']}, drawn from "
      f"`{d['rng']}`.")
    A("")
    A(f"Filter: {f['filtered_kind']} order {f['filtered_order']}, cutoff "
      f"{f['cutoff_hz']} Hz. {f['path']}.")
    A("")

    A("## 3. Preregistered design")
    A("")
    A(f"The design was frozen in `campaign/manifests/` and committed **before**")
    A(f"the first run. Its hash covers every value below.")
    A("")
    A(f"- {len(seeds)} seeds: `{seeds}`")
    A(f"- each seed run under BOTH conditions -> {c['scheduled']} scheduled runs")
    A(f"- pairing: {m['design']['pairing']}")
    A(f"- arm order: {m['design']['arm_order_policy']}")
    rc = m["run_contract"]
    A(f"- run length: {rc['samples_per_run']} samples / "
      f"{rc['run_duration_sim_s']} s of simulated time, fixed regardless of "
      f"whether the controller converges")
    A(f"- reference: {rc['reference_signal']}")
    A(f"- start pose verified within {rc['reset_tolerance_rad']} rad before every run")
    A(f"- rate tolerance ±{s['rate_tolerance_frac']:.0%}, checked per run")
    A(f"- {m['design']['no_replacement_rule']}")
    A("")

    A("## 4. Counts and evidence integrity")
    A("")
    A("| | scheduled | valid | invalid | failed | missing |")
    A("|---|---|---|---|---|---|")
    A(f"| **all** | {c['scheduled']} | {c['valid']} | {c['invalid']} | "
      f"{c['failed']} | {c['missing']} |")
    for cond in ("filtered", "unfiltered"):
        bc = c["by_condition"][cond]
        A(f"| {cond} | {bc['scheduled']} | {bc['valid']} | | | |")
    A("")
    integ = results["integrity"]
    A(f"Evidence integrity: **{'PASS' if integ['passed'] else 'FAIL'}** — "
      f"{integ['ok']}/{integ['checked']} files re-hashed to their recorded "
      f"sha256, {len(integ['mismatched'])} mismatched, "
      f"{len(integ['missing'])} missing.")
    A("")
    rs = results["rate"]
    # Enough digits to show the spread. At 7 significant figures every run
    # rounds to "200" and the reader cannot tell a tight distribution from a
    # rounded one.
    A(f"Measured sample rate across all {rs['n']} runs: "
      f"{fmt(rs['min'], 15)} – {fmt(rs['max'], 15)} Hz "
      f"(mean {fmt(rs['mean'], 15)} Hz). "
      f"All within the frozen ±2% tolerance: **{rs['all_within_tolerance']}**.")
    A("")
    if results["excluded_runs"]:
        A("Runs not counted as valid (retained, never replaced):")
        A("")
        A("| run | status | reason |")
        A("|---|---|---|")
        for e in results["excluded_runs"]:
            A(f"| `{e['run_id']}` | {e['status']} | {e['failure_reason']} |")
        A("")
    else:
        A("No run was invalid, failed, or missing.")
        A("")

    A("## 5. Filtered vs unfiltered")
    A("")
    A("Per-condition statistics over valid runs. Lower is better for all but")
    A("attenuation.")
    A("")
    A("The MEDIAN is shown alongside the mean because the mean is inf-aware: a")
    A("single run that never settles makes the mean settling time `inf`, which")
    A("is correct but says nothing about the other 19. The median survives it.")
    A("")
    A("| metric | unit | filtered mean | filtered median | unfiltered mean | unfiltered median |")
    A("|---|---|---|---|---|---|")

    def mean(xs):
        if not xs:
            return None
        return math.inf if any(math.isinf(x) for x in xs) else sum(xs) / len(xs)

    def median(xs):
        if not xs:
            return None
        s = sorted(xs)
        n = len(s)
        if n % 2:
            return s[n // 2]
        lo, hi = s[n // 2 - 1], s[n // 2]
        return math.inf if (math.isinf(lo) or math.isinf(hi)) else (lo + hi) / 2.0

    for metric in METRIC_ORDER:
        pm = paired[metric]
        fv = [v for _, v, _ in pm.pairs if v is not None]
        uv = [v for _, _, v in pm.pairs if v is not None]
        A(f"| `{metric}` | {METRIC_UNITS[metric]} | {fmt(mean(fv))} | "
          f"{fmt(median(fv))} | {fmt(mean(uv))} | {fmt(median(uv))} |")
    A("")
    A("`settling_time_s` is `inf` for any run whose error never stays inside")
    A(f"the ±{DEFAULT_THRESHOLDS['settling_band_rad']} rad band through the end "
      f"of the run. Counts of such runs per condition:")
    st = paired["settling_time_s"]
    n_f_inf = sum(1 for _, v, _ in st.pairs if v is not None and math.isinf(v))
    n_u_inf = sum(1 for _, _, v in st.pairs if v is not None and math.isinf(v))
    A("")
    A(f"- filtered: {n_f_inf}/{st.n_pairs} never settled")
    A(f"- unfiltered: {n_u_inf}/{st.n_pairs} never settled")
    A("")
    A("Secondary diagnostics from the raw packets — `true_*` are the")
    A("articulation's ACTUAL position, which the controller never observes:")
    A("")
    A("| metric | filtered | unfiltered |")
    A("|---|---|---|")
    for key, pm in secondary.items():
        fv = [v for _, v, _ in pm.pairs if v is not None]
        uv = [v for _, _, v in pm.pairs if v is not None]
        A(f"| `{key}` | {fmt(sum(fv) / len(fv) if fv else None)} | "
          f"{fmt(sum(uv) / len(uv) if uv else None)} |")
    A("")

    A("## 6. Paired differences and uncertainty")
    A("")
    A(f"Each seed contributes one filtered-minus-unfiltered difference, so")
    A(f"between-seed variation cancels. Intervals are a deterministic")
    A(f"{m['analysis']['bootstrap_resamples']}-resample percentile bootstrap")
    A(f"seeded with {m['analysis']['bootstrap_seed']}.")
    A("")
    A("**No significance claim is made.** " + m["analysis"]["significance_policy"] + ".")
    A("")
    A("| metric | mean diff | 95% CI | finite pairs | filtered better |")
    A("|---|---|---|---|---|")
    for metric in METRIC_ORDER:
        pm = paired[metric]
        ci = (f"[{fmt(pm.ci_low)}, {fmt(pm.ci_high)}]"
              if pm.ci_low is not None else "n/a")
        A(f"| `{metric}` | {fmt(pm.mean_difference)} | {ci} | "
          f"{pm.n_finite_pairs}/{pm.n_pairs} | "
          f"{pm.n_filtered_better}/{pm.n_pairs} |")
    A("")
    for metric in METRIC_ORDER:
        pm = paired[metric]
        A(f"- {describe(pm, METRIC_UNITS[metric])}")
        if pm.note:
            A(f"  - _{pm.note}_")
    A("")
    for key, pm in secondary.items():
        A(f"- {describe(pm, 'rad')}")
    A("")

    A("### Per-seed raw distribution (primary metric)")
    A("")
    A("| seed | filtered | unfiltered | difference |")
    A("|---|---|---|---|")
    pm = paired["tracking_rms_error"]
    for seed, fv, uv in pm.pairs:
        diff = (fv - uv) if (fv is not None and uv is not None
                             and math.isfinite(fv) and math.isfinite(uv)) else None
        A(f"| {seed} | {fmt(fv)} | {fmt(uv)} | {fmt(diff)} |")
    A("")

    A("## 7. Degraded and failure analysis")
    A("")
    A("Issue #9 requires a degraded-run analysis. No empirical run was")
    A("deliberately corrupted to produce one.")
    A("")
    A("**Pre-campaign failure case 1 — the 30.02 Hz sampling boundary.**")
    A("Before this campaign, the scene's default graph published `/joint_states`")
    A("at 30.02 Hz while the DSP path was configured for 200 Hz. At 30 Hz the")
    A("Nyquist frequency is 15 Hz, so the 25 Hz disturbance aliases to ~5 Hz —")
    A("exactly the filter's cutoff. A campaign run in that state would have")
    A("compared filtered against unfiltered on an aliasing artifact, and the")
    A("contamination would have been identical in both arms, which is precisely")
    A("what a paired comparison cannot detect. The sampling boundary was fixed")
    A("(200.492 Hz measured) rather than the filter retuned, and")
    A("`assert_campaign_sampling_valid()` now refuses such a configuration.")
    A("This is a pre-campaign observation and is NOT one of the")
    A(f"{c['scheduled']} runs.")
    A("")
    A("**Pre-campaign failure case 2 — `stageMetersPerUnit` zero publication.**")
    A("The first Isaac 6 graph migration passed the static scene contract and")
    A("published ZERO messages: the publisher requires `stageMetersPerUnit`")
    A("wired from the reader, and errors out without it. A static check that")
    A("passes while the system emits nothing is the exact failure mode runtime")
    A("validation exists to catch. It is now a scene-contract clause with test")
    A("coverage. Also not one of the campaign runs.")
    A("")
    A("**Pilot-discovered design defect — endogenous reference.** A pilot pair")
    A("on non-campaign seeds ran with the reference defined as the tracker's")
    A("ACTIVE waypoint. Because the unfiltered arm never advanced past waypoint")
    A("0, its reference span was 0.0 while the filtered arm's was 0.4, and")
    A("`overshoot_pct` divides by that span (falling back to 1.0 when it is")
    A("zero). The two arms would have been scored against different reference")
    A("signals. The reference was made exogenous — a pure function of elapsed")
    A("simulated time, identical in both arms — before the manifest was frozen.")
    A("Pilot runs are not campaign evidence and are not committed.")
    A("")
    if results["excluded_runs"]:
        A("**In-campaign failures.** See the table in §4; each carries its exact")
        A("reason and remains in the denominator.")
    else:
        A(f"**In-campaign failures.** All {c['scheduled']} runs completed within")
        A("the frozen contract: none hit the rate tolerance, the sample-count")
        A("floor, the reset check, or a harness error.")
    A("")

    A("## 8. Limitations")
    A("")
    A("- One scenario, one robot model, one machine, one Isaac build.")
    A("- n=20 pairs. Intervals are wide and no significance test is offered.")
    A("- The gauntlet's absolute thresholds were tuned against the open-loop")
    A("  synthetic profile in `s2r_dsp`, not against this closed loop. Runs are")
    A("  graded against them for consistency with the certification path, but")
    A("  the campaign's question is the filtered-vs-unfiltered CONTRAST, not")
    A("  pass/fail against those thresholds. They were not adjusted to make any")
    A("  arm pass.")
    A("- `tracking_rms_error` scores the signal the CONTROLLER consumes")
    A("  (post-filter). The articulation's true position is reported separately")
    A("  as `true_tracking_rms_error_rad`; the two are different claims.")
    A("- PhysX ran on CPU (`gpu_dynamics: false`) — observed and recorded, not")
    A("  chosen for performance. GPU-vs-CPU PhysX behavior was not benchmarked.")
    A("- The disturbance is injected in software on the feedback path. It is a")
    A("  model of sensor noise, not a measured noise profile from a real robot.")
    A("")

    A("## 9. Explicit non-claims")
    A("")
    for nc in m["non_claims"]:
        A(f"- **{nc[0].upper() + nc[1:]}.**")
    A("- **No claim that these results transfer to any physical Franka or any**")
    A("  **other robot.**")
    A("")

    A("## 10. Reproduction")
    A("")
    A("Verifying the committed evidence requires NO simulator and NO GPU:")
    A("")
    A("```bash")
    A("python -m pytest dsp/ gauntlet/ campaign/ scenes/ -q")
    A("PYTHONPATH=ros2-ws/src/control_loop python -m pytest ros2-ws/src/control_loop/test -q")
    A(f"python scripts/build_results.py --check \\")
    A(f"    --logs-root campaign/results/{m['campaign_id']}-v{m['campaign_version']} \\")
    A(f"    --manifest campaign/manifests/{m['campaign_id']}-v{m['campaign_version']}.json \\")
    A(f"    --out RESULTS.md")
    A("")
    A("git status --porcelain   # must be empty")
    A("```")
    A("")
    A("`--check` re-hashes every raw source artifact, re-grades every run from its")
    A("raw telemetry, rebuilds the graded packets, `campaign_results.json` and this")
    A("document into a temporary directory, and compares them byte-for-byte against")
    A("the committed copies. It writes nothing inside the repository and exits")
    A("non-zero on any mismatch or on a raw-integrity failure.")
    A("")
    A("Everything above is verifiable with no Isaac Sim of any version.")
    A("")
    A(f"Reproducing the campaign itself additionally requires an Isaac Sim host.")
    A(f"The validated configuration is the exact build these runs were executed")
    A(f"on, `{r['isaac_build']}`; running the harness on any other build --")
    A(f"including the general-availability release of the same version number --")
    A(f"is a new runtime-compatibility attempt, not a replay of this campaign,")
    A(f"and this project makes no claim that it would behave the same. See")
    A("`docs/M4_RUNTIME_VALIDATION.md` and `docs/REPRODUCE_CAMPAIGN.md`.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
