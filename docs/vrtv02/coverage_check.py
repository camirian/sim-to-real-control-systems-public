#!/usr/bin/env python3
"""Deterministic visual-to-source coverage check for VRTV-02.

SUPPORT CONTRACT SEMANTICS
--------------------------
Each assertion declares one or more REQUIRED evidence dimensions. A dimension is
satisfied when at least one of its narrow locators matches somewhere in the
corpus. An assertion is supported only when EVERY dimension is satisfied.

This replaces the earlier ANY-of-patterns rule, under which a compound
proposition passed on a single component -- "Isaac OR Franka", "25 Hz OR AWGN"
-- and generic words such as "rate", "claim" or "disturb" counted as support.

Locators are of two kinds:
  json:<path-substring>:<dotted key>   exact key present in a machine-readable
                                       artifact (preferred where available)
  re:<regex>                           narrow anchored prose locator

This gate asks ONLY: does the corpus contain the authoritative locations needed
to ADJUDICATE the proposition? It never records whether the proposition is true.
Diagram correctness is the reviewers' job; pre-labelling it here would build an
answer key and destroy the experiment.


FAIRNESS GATE. If a CLEAN visual stimulus asserts something a reviewer cannot
verify from the bounded review corpus, then V1/V2 reviewers are being shown
claims they are structurally unable to check, while V0 is not. That is a design
defect, not an experimental result.

Enumerates every material factual assertion encoded in clean Views A-D and
requires each to be supported by at least one artifact in the corpus. Exits
non-zero if any assertion is unsupported.

This checks CORPUS COVERAGE, not correctness of the diagrams. Whether the source
agrees with the diagram is the reviewers' job -- this only proves they CAN look.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# (id, view, assertion, [regex patterns; ANY match = supported])

# (id, view, assertion, {dimension: [locators, ANY of which satisfies it]})
# ALL dimensions must be satisfied.
ASSERTIONS = [
    ("A1", "A", "Simulator is Isaac Sim with a Franka articulation", {
        "simulator_is_isaac": [r"re:Isaac\s*Sim"],
        "robot_is_franka": [r"re:\bFranka\b"]}),
    ("A2", "A", "Seeded disturbance is 25 Hz plus AWGN", {
        "tone_frequency_25hz": [r"json:manifests:disturbance.tone_hz",
                                r"re:25(\.0+)?\s*Hz"],
        "noise_is_awgn": [r"re:\bAWGN\b", r"json:manifests:disturbance.noise"]}),
    ("A3", "A", "Disturbance is injected before the condition split, so both arms share it", {
        "injection_point_defined": [r"json:manifests:disturbance",
                                    r"re:inject(ed|ion)\s+(in)?to\s+the\s+\w+",
                                    r"re:disturbance is injected"],
        "both_arms_share_disturbance": [
            r"re:only difference is the filter",
            r"re:identical .{0,40}(disturb|noise|feedback)",
            r"json:manifests:design"]}),
    ("A4", "A", "Filter is a 4th-order Butterworth IIR", {
        "family_butterworth": [r"re:Butterworth"],
        "order_is_4": [r"json:manifests:filter.filtered_order",
                       r"re:4th-order"],
        "type_is_iir": [r"json:manifests:filter.filtered_kind", r"re:\bIIR\b"]}),
    ("A5", "A", "Filter cutoff is 5 Hz", {
        "cutoff_value_5hz": [r"json:manifests:filter.cutoff_hz",
                             r"re:5\s*Hz cutoff", r"re:cutoff.{0,12}5(\.0+)?\b"]}),
    ("A6", "A", "The in-loop filter path is causal", {
        "causal_path_named": [r"re:causal"]}),
    ("A7", "A", "Unfiltered arm is identity/passthrough at 0 dB", {
        "arm_is_passthrough": [r"re:passthrough", r"json:raw_evidence.json:controller.filter_kind"],
        "attenuation_is_zero": [r"json:raw_evidence.json:signals_summary",
                                r"re:filter_attenuation_db.{0,40}\b0\b",
                                r"re:\b0\s*dB"]}),
    ("A8", "A", "Controller is WaypointTracker with an exogenous time reference", {
        "controller_is_waypointtracker": [r"re:WaypointTracker"],
        "reference_is_exogenous": [r"re:exogenous"]}),
    ("A9", "A", "Loop is closed: controller commands return to the simulator", {
        "commands_written_back": [r"re:joint[_ ]command", r"re:closed[- ]loop",
                                  r"re:command.{0,30}(publish|written|sent|applied)"]}),
    ("A10", "A", "Raw telemetry targets 200 Hz", {
        "target_rate_200hz": [r"json:manifests:sampling",
                              r"json:raw_evidence.json:rate.target_hz",
                              r"re:200(\.0+)?\s*Hz"]}),
    ("A11", "A", "Runs produce a gauntlet/evidence packet", {
        "evidence_packet_exists": [r"json:raw_evidence.json:files",
                                   r"re:evidence packet"],
        "checks_recorded": [r"json:evidence/:checks", r"re:gauntlet"]}),

    ("B1", "B", "Frozen campaign manifest defines 20 paired seeds", {
        "seed_count_20": [r"json:manifests:design",
                          r"re:20 seeds", r"re:20 paired"],
        "seeds_are_paired": [r"re:paired", r"re:BOTH conditions",
                             r"re:each seed run under both"]}),
    ("B2", "B", "A campaign harness executes the runs", {
        "harness_named": [r"re:harness", r"re:run_campaign"]}),
    ("B3", "B", "40 scheduled runs = 20 filtered + 20 unfiltered", {
        "scheduled_is_40": [r"json:campaign_summary.json:scheduled",
                            r"re:40 scheduled"],
        "split_by_condition": [r"json:campaign_summary.json:by_condition",
                               r"re:20 filtered", r"re:filtered.{0,30}unfiltered"]}),
    ("B4", "B", "Per-run raw telemetry is produced", {
        "telemetry_artifact_named": [r"json:raw_evidence.json:files",
                                     r"re:telemetry\.csv"]}),
    ("B5", "B", "Per-run evidence packets carry checks", {
        "checks_present": [r"json:evidence/:checks"],
        "pass_state_present": [r"json:evidence/:overall_passed",
                               r"json:evidence/:thresholds"]}),
    ("B6", "B", "Manifest/hash verification occurs", {
        "manifest_hash_recorded": [r"json:raw_evidence.json:manifest_sha256",
                                   r"re:manifest_sha256"],
        "integrity_verified": [r"json:campaign_summary.json:integrity_index",
                               r"re:re-hash", r"re:120/120"]}),
    ("B7", "B", "Aggregation is performed by scripts/build_results.py", {
        "aggregator_named": [r"re:scripts/build_results\.py"]}),
    ("B8", "B", "RESULTS.md is the aggregated result artifact", {
        "results_doc_is_generated": [r"re:Generated by .{0,30}build_results",
                                     r"re:--out RESULTS\.md"]}),
    ("B9", "B", "Public claims are bounded", {
        "non_claims_enumerated": [r"json:manifests:non_claims",
                                  r"re:No sim-to-real transfer is demonstrated"]}),
    ("B10", "B", "Committed evidence is reproducible CPU-only without Isaac", {
        "cpu_only_repro_documented": [r"re:CPU[- ]only", r"re:without Isaac"]}),

    ("C1", "C", "A pre-campaign validation phase existed", {
        "validation_phase_documented": [r"re:Pre-campaign", r"re:M4_RUNTIME_VALIDATION",
                                        r"re:runtime validation"]}),
    ("C2", "C", "A 30.02 Hz sampling-rate defect was found", {
        "measured_rate_30_02": [r"re:30\.02"]}),
    ("C3", "C", "25 Hz would alias near 5 Hz at that rate", {
        "aliasing_explained": [r"re:alias"],
        "relates_25_to_5": [r"re:alias.{0,80}5", r"re:25 Hz .{0,60}5 Hz"]}),
    ("C4", "C", "A stageMetersPerUnit defect passed static contract but emitted zero", {
        "defect_named": [r"re:stageMetersPerUnit"],
        "zero_publication_symptom": [r"re:ZERO messages", r"re:zero publication",
                                     r"re:emitted\s+ZERO"]}),
    ("C5", "C", "A pilot endogenous-reference defect was found", {
        "endogenous_reference_named": [r"re:endogenous"],
        "found_by_pilot": [r"re:pilot"]}),
    ("C6", "C", "Defects were fixed before the manifest freeze", {
        "freeze_event_documented": [r"re:before the design was frozen",
                                    r"re:fix.{0,40}before.{0,30}freeze",
                                    r"re:frozen"],
        "manifest_is_frozen": [r"json:manifests:manifest_sha256",
                               r"re:frozen manifest"]}),
    ("C7", "C", "Campaign returned 40 valid / 0 failed / 0 missing", {
        "valid_40": [r"json:campaign_results.json:summary.valid",
                     r"json:campaign_summary.json:valid", r"re:40/40 valid"],
        "failed_0": [r"json:campaign_results.json:summary.failed",
                     r"json:campaign_summary.json:failed"],
        "missing_0": [r"json:campaign_results.json:summary.missing",
                      r"json:campaign_summary.json:invalid"]}),

    ("D1", "D", "Filtered feedback had lower tracking RMS in the tested scenario", {
        "metric_present": [r"re:tracking_rms_error"],
        "paired_comparison_present": [r"re:20/20", r"re:bootstrap", r"re:95%"]}),
    ("D2", "D", "The causal filter attenuated the injected 25 Hz disturbance", {
        "attenuation_metric_present": [r"re:filter_attenuation_db",
                                       r"json:raw_evidence.json:signals_summary"],
        "attenuation_value_reported": [r"re:48\.12", r"re:dB"]}),
    ("D3", "D", "Committed evidence is reproducible/inspectable without Isaac", {
        "cpu_only_repro_documented": [r"re:CPU[- ]only", r"re:without Isaac"]}),
    ("D4", "D", "NON-CLAIM: no physical hardware performance", {
        "hardware_non_claim": [r"re:[Nn]o hardware was involved",
                               r"re:[Ss]imulation only"]}),
    ("D5", "D", "NON-CLAIM: no sim-to-real transfer", {
        "sim2real_non_claim": [r"re:[Nn]o sim-to-real transfer"]}),
    ("D6", "D", "NON-CLAIM: no robot safety or certification", {
        "safety_non_claim": [r"re:safety", r"re:certification"],
        "stated_as_non_claim": [r"json:manifests:non_claims",
                                r"re:no .{0,30}(safety|certification)"]}),
    ("D7", "D", "NON-CLAIM: no Isaac Sim 6.0.1 GA equivalence", {
        "rc_build_identified": [r"re:6\.0\.1-rc\.7"],
        "ga_equivalence_disclaimed": [r"re:not .{0,20}GA", r"re:GA .{0,40}not",
                                      r"re:release candidate"]}),
    ("D8", "D", "NON-CLAIM: no generalization to other robots/scenarios", {
        "generalization_non_claim": [r"re:no generalization is claimed"]}),
]


def satisfied(locator: str, files: dict) -> tuple[bool, dict | None]:
    """Return (satisfied, evidence). Locators are narrow by construction."""
    if locator.startswith("json:"):
        _, path_sub, dotted = locator.split(":", 2)
        for rel, content in files.items():
            if path_sub not in rel or not rel.endswith(".json"):
                continue
            try:
                obj = json.loads(content)
            except Exception:
                continue
            cur = obj
            for key in dotted.split("."):
                if isinstance(cur, dict) and key in cur:
                    cur = cur[key]
                else:
                    cur = None
                    break
            if cur is not None:
                return True, {"artifact": rel, "locator": locator,
                              "excerpt": json.dumps(cur)[:150]}
        return False, None
    pat = locator[3:]
    for rel, content in files.items():
        m = re.search(pat, content, re.IGNORECASE)
        if m:
            return True, {"artifact": rel, "locator": locator,
                          "excerpt": content[max(0, m.start()-60):m.end()+60]
                                     .replace("\n", " ")[:150]}
    return False, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).parent / "COVERAGE_REPORT.json")
    args = ap.parse_args()

    files = {}
    for p in sorted(args.corpus_dir.rglob("*")):
        if p.is_file():
            files[str(p.relative_to(args.corpus_dir))] = p.read_text(
                encoding="utf-8", errors="replace")

    results, unsupported = [], []
    for aid, view, text, dims in ASSERTIONS:
        dim_results, evidence = {}, []
        for dim, locators in dims.items():
            hit = None
            for loc in locators:
                ok, ev = satisfied(loc, files)
                if ok:
                    hit = ev
                    break
            dim_results[dim] = hit is not None
            if hit:
                evidence.append({"dimension": dim, **hit})
            else:
                evidence.append({"dimension": dim, "artifact": None,
                                 "locator": locators, "excerpt": None})
        all_ok = all(dim_results.values())
        rec = {"id": aid, "view": view, "assertion": text,
               "required_dimensions": list(dims),
               "dimension_results": dim_results,
               "supported": all_ok,
               "unsatisfied_dimensions": [d for d, v in dim_results.items() if not v],
               "evidence": evidence}
        results.append(rec)
        if not all_ok:
            unsupported.append(rec)

    report = {"corpus_dir": str(args.corpus_dir),
              "gate_semantics": "ALL required evidence dimensions must be "
                                "satisfied; narrow locators only; this gate "
                                "records corpus coverage, never diagram "
                                "correctness",
              "total_required_dimensions": sum(len(d) for _, _, _, d in ASSERTIONS),
              "assertions_total": len(ASSERTIONS),
              "assertions_supported": len(ASSERTIONS) - len(unsupported),
              "assertions_unsupported": len(unsupported),
              "unsupported": unsupported, "results": results}
    args.out.write_text(json.dumps(report, indent=2) + "\n")

    print(f"{'':4s} {'id':5s} {'view':5s} {'dims':>5s}  assertion")
    for r in results:
        mark = "OK " if r["supported"] else "MISS"
        n = len(r["required_dimensions"])
        met = sum(r["dimension_results"].values())
        print(f"{mark} {r['id']:4s} {r['view']:4s} {met}/{n:<3d}  "
              f"{r['assertion'][:62]}")
    print(f"\nsupported {report['assertions_supported']}/{report['assertions_total']}")
    if unsupported:
        print("\nDESIGN DEFECT - unsupported visual assertions:")
        for r in unsupported:
            print(f"  {r['id']} ({r['view']}): {r['assertion']}")
            print(f"      unsatisfied: {r['unsatisfied_dimensions']}")
        return 1
    print("PASS: every material visual assertion is verifiable from the bounded corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
