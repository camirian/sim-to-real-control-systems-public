# M4 claim-boundary and public-surface audit

**Date:** 2026-08-16
**Baseline audited:** `main` @ `f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29`, plus the
public-proof changes on `docs/m4-public-proof`.
**Method:** every public-facing claim traced to a primary artifact under
`campaign/`. Numbers were re-derived directly from the committed JSON, not copied
from prose.

---

## 1. Verified facts

Re-derived from primary artifacts during this audit:

| Fact | Value | Source |
|---|---|---|
| Run counts | attempted 40, valid 40, invalid 0, **execution** failures 0, missing 0 | `campaign_summary.json`, `campaign_results.json.counts` |
| Raw-artifact integrity | checked 120, ok 120, mismatched 0, missing 0 — composition: 40 runs × {run_meta.json, telemetry.csv, truth.csv} | `campaign_results.json.integrity`, `campaign_summary.json.integrity_index` |
| Loop rate | mean 199.99999999899944 Hz, n=40, all within tolerance | `campaign_results.json.rate` |
| Tracking RMS diff | −0.22884766390016834 rad, CI [−0.24835462992253976, −0.2122944430180847], 20/20 | `paired.tracking_rms_error` |
| Attenuation diff | +48.11513753981959 dB, CI [45.783948768227255, 50.47822417129975], 20/20 | `paired.filter_attenuation_db` |
| Overshoot diff | −162.9113539936193 %, CI [−171.27, −156.37], 20/20 | `paired.overshoot_pct` |
| Settling diff | −3.4355 s, CI [−4.6395, −2.1265], 19/20; **10/20 pairs non-finite** | `paired.settling_time_s` |
| True-position RMS diff | −0.11963329154837872 rad, CI [−0.13959854697590873, −0.10283181224689561], 20/20 | `secondary.true_tracking_rms_error_rad` |
| **Gauntlet verdict** | **0 of 40 runs `overall_passed: true`** | all 40 evidence packets |
| Filtered per-check | attenuation 20/20 pass · tracking RMS 3/20 · settling 0/20 · overshoot 0/20 | evidence packets |
| Unfiltered per-check | 0/20 pass on all four checks | evidence packets |
| Simulator | `6.0.1-rc.7+release.42383.32955d8d.gl` | manifest `environment` |
| Manifest hash | `1d227e437317bac11df209d39ac264d7b4ffe9d5f9b5d4bf8c805f266b238052` | `campaign_summary.json` |

## 2. Findings

### F-1 — "40/40 valid" is readily misread as "40/40 passed" — **FIXED**

**Severity: high.** The single largest misreading risk on the public surface.
`valid` means *admitted under the preregistered exclusion rules*. It carries no
information about acceptance thresholds. Placed next to the phrase "certification
gauntlet", a reader will reasonably infer the runs passed. **They did not — 0 of
40 passed.**

Before this branch, the fact was disclosed only in `RESULTS.md` §8 Limitations,
phrased as a caveat about threshold provenance, and never stated as a count.

**Fix:** the count is now stated explicitly and prominently in
`README.md` ("In 60 seconds"), `docs/M4_CASE_STUDY.md` §6 (a dedicated section),
and the results visual (a red panel).

### F-2 — README pinned Isaac Sim 4.5.0 while all evidence came from 6.0.1-rc.7 — **FIXED**

**Severity: high.** The front-door version table read `NVIDIA Isaac Sim | 4.5.0`,
and the architecture diagram was labelled `Isaac Sim 4.5.0`. No result in this
repository was produced on 4.5.0. A reader taking the pin table at face value
would attribute every number to the wrong simulator build.

**Fix:** the table now pins the exact RC build and scopes each version to what it
applies to (campaign runtime vs. DevContainer build path vs. evidence
verification), with a historical note on the retired 4.5.0 pin. The diagram label
is corrected.

### F-3 — README lede implied a recorded demo exists — **FIXED**

**Severity: medium.** The opening sentence read "One recorded closed-loop demo
with certification-style evidence". No video is published from this repository,
and `README.md` says so 140 lines later.

**Fix:** the lede now describes the system rather than asserting a demo artifact.

### F-4 — MASTER_PLAN.md promised a demo beat that the evidence contradicts — **FIXED**

**Severity: medium.** `MASTER_PLAN.md:19` specifies the demo as:

> "noisy run failing checks → filtered run passing → evidence packet"

**No filtered run passes.** Filtered runs pass only the attenuation check (20/20)
and fail tracking, settling and overshoot. Recording the demo as written in the
plan of record would produce a false public claim.

**Fix:** goal 3 in `MASTER_PLAN.md` now describes the preregistered
filtered-vs-unfiltered **contrast**, carries an explicit correction note recording
that 0 of 40 runs passed, and points at `docs/DEMO_OUTLINE.md`. The demo script
must present the contrast, never a pass.

### F-5 — Governing pins contradicted the corrected front door — **FIXED**

**Severity: high.** `AGENTS.md:33` and `MASTER_PLAN.md:35,69` prescribed the old
4.5.0 / Humble contract as though it governed the empirical campaign.

`AGENTS.md` is the binding operating guide and `MASTER_PLAN.md` repeats it, so
between them they prescribed ROS 2 Humble / Isaac Sim 4.5.0 as the supported
configuration while the README declared 6.0.1-rc.7 — the front door and the
mandatory build instructions specified incompatible environments.

**Fix:** `AGENTS.md` §2 now splits the pin into two explicitly-scoped entries —
the **empirical runtime** that governs all M4 evidence (Isaac Sim 6.0.1-rc.7 with
Isaac's own ROS 2 Jazzy) and the **legacy DevContainer / `scripts/` path** (Humble
/ 4.5.0), with the statement that no empirical result came from the latter.
`MASTER_PLAN.md` carries the same scoping note above its architecture diagram, the
diagram label is corrected, and REQ-S2R-300 names both pins.

`docs/RUN_ON_EDGEXPERT.md` still references 4.5.0 throughout; it is an operational
runbook for the legacy `scripts/` path, which is exactly the scope the corrected
pins assign to 4.5.0, so it is left as-is and is no longer contradictory.

### F-6 — Settling-time interval rests on half the pairs — **DISCLOSED**

**Severity: low.** 10 of 20 settling pairs are non-finite (the run never settled)
and are excluded from the interval while being retained in the win fraction. The
CI is therefore computed on 10 pairs. Disclosed inline in
`docs/M4_CASE_STUDY.md` §5, the visual, and the demo statement table (S7). The
README 60-second table deliberately omits settling time rather than present the
weakest number without its caveat.

### F-7 — Two different "tracking error" metrics — **DISCLOSED**

**Severity: medium if conflated.** `tracking_rms_error` scores the *post-filter
signal the controller consumes*; `true_tracking_rms_error_rad` scores the
*articulation's actual position*. The improvement on the true metric (−0.1196 rad)
is roughly **half** the improvement on the consumed signal (−0.2288 rad).
Reporting only the latter would overstate the filter's benefit ~2×.

Both are published in the README table, the case study §5, the visual, and demo
statements S3 and S6.

### F-8 — the documented verification command mutated committed evidence — **FIXED**

**Severity: low (process), medium (optics).** Found by executing the Path A
verification exactly as documented in `docs/REPRODUCE_CAMPAIGN.md`:

```bash
python scripts/build_results.py --logs-root … --manifest … --out RESULTS.md
```

`RESULTS.md` regenerated **byte-identical** (empty `git diff` — the reproducibility
claim holds). But the same invocation rewrote all 40 evidence packets plus
`campaign_results.json`, setting `"generated_at": "2026-08-14T21:00:00Z"` to
`"generated_at": null`, because `--timestamp` was not supplied and defaults to
`None`.

A reader following the documented steps will see 41 modified files in
`git status` immediately after a "verification" step, which looks like evidence
tampering and undercuts the immutability framing. The content that matters is
unaffected — only the timestamp field changes.

**Fix:** `scripts/build_results.py` gained an explicit `--check` mode. It routes
every write — all 40 gauntlet packets, `campaign_results.json` and `RESULTS.md` —
into a temporary directory, reproduces the committed `generated_at` so the
comparison is a true byte comparison, compares all 42 artifacts byte-for-byte,
and exits non-zero on any mismatch. The scratch directory is removed on exit.
Nothing inside the repository is written, so this is read-only by construction
rather than by cleanup after mutation.

All public verification instructions (`README.md`, `docs/M4_CASE_STUDY.md` §8,
`docs/REPRODUCE_CAMPAIGN.md` A2) now use `--check` and assert
`git status --porcelain` is empty. The in-place mode is retained for regenerating
artifacts after a fresh campaign, documented with the `--timestamp` requirement.

**Verified:** on a clean worktree, `--check` reports `42/42 artifacts reproduced
byte-for-byte`, `CHECK PASSED`, exit 0, with `git status --porcelain` empty.
Negative test: forcing a wrong `--timestamp` produces 41 mismatch lines and
exit 1, still without modifying the repository.

### F-10 — `RESULTS.md` §10 still emitted the mutating command — **FIXED**

**Severity: high.** `RESULTS.md` is generated, and its own §10 Reproduction
section is emitted by `render()`. That text still told readers to run
`build_results.py` **without** `--check` or `--timestamp` — so the document
produced by the fix still published the instruction the fix exists to remove,
leaving 41 modified files for anyone who followed it.

**Fix:** `render()` now emits the `--check` form plus `git status --porcelain`
and describes the read-only semantics. `RESULTS.md` was regenerated with
`--timestamp 2026-08-14T21:00:00Z` (the committed value), so the only change is
the instruction text — **8 insertions, 4 deletions, no number altered and no
evidence packet touched**.

### F-11 — `--check` passed when raw integrity failed — **FIXED**

**Severity: high (fail-open).** The exit decision considered only byte equality
between rebuilt and committed derived artifacts. But `verify_integrity()` can
return `passed=False` while the derived artifacts *faithfully reproduce* that
failure — so a corrupted evidence tree committed together with its regenerated
outputs would print `CHECK PASSED` and exit 0. The advertised verifier failed
open on the exact case it exists to catch.

**Fix:** the raw-integrity verdict is now part of the failure condition.

**Verified** by reproducing the precise scenario: append a byte to a
hash-covered `truth.csv`, regenerate all derived artifacts so they match the
corrupted tree, then run `--check`. Result: `integrity_passed=False`,
`42/42 artifacts reproduced byte-for-byte`, and
`FAIL raw-artifact integrity: 1 mismatched, 0 missing`, `CHECK FAILED`, exit 1.
Before the fix this same input exited 0.

### F-12 — extra committed packets were never compared — **FIXED**

**Severity: medium.** The comparison loop iterated over files *rebuilt into the
scratch directory*, so a stale or extra packet present only in the committed
`evidence/` directory was never visited. `--check` could report `42/42` and exit
0 while the committed tree carried an unverified artifact.

**Fix:** the rebuilt and committed filename sets are compared before contents;
any committed packet not produced by this campaign is reported and fails the run.

**Verified:** planting `run-STALE-9999.json` yields
`FAIL evidence/run-STALE-9999.json: committed but not produced by this campaign
— unverified artifact`, `CHECK FAILED`, exit 1.

### F-9 — the 120-file integrity set was described as "evidence files" — **FIXED**

**Severity: medium.** The front door pointed readers at
`campaign/results/…/evidence/` for "the 40 raw packets" and described the
integrity check as "120/120 evidence files hash-verified". Both are wrong:

- `evidence/run-*.json` holds **regenerated gauntlet packets** — graded output,
  not source.
- The **raw** artifacts live per run in `filtered-<seed>/` and `unfiltered-<seed>/`:
  `raw_evidence.json` plus `run_meta.json`, `telemetry.csv`, `truth.csv`.
- The 120-file integrity set is exactly 40 runs × {`run_meta.json`,
  `telemetry.csv`, `truth.csv`} — verified directly against
  `campaign_summary.json.integrity_index.files`. It does **not** include the
  graded packets or `raw_evidence.json`.

Blurring these three sets would let a reader believe the graded output is
hash-pinned source, which it is not.

**Fix:** `README.md` now carries a three-row path table separating raw source,
regenerated packets, and aggregates, and states the exact composition of the
120-file set. `docs/M4_CASE_STUDY.md` §4 and its evidence index make the same
split.

## 3. Public claims introduced by this change

Every claim below is a restatement of a verified fact in §1. No new measurement
was created.

1. The campaign ran 40/40 valid runs (0 execution failures) with 120/120 hash-verified raw source artifacts.
2. Causal in-loop filtering improved tracking RMS error by 0.2288 rad
   (95% CI [−0.2484, −0.2123]), better in 20/20 pairs.
3. The filter delivered 48.115 dB attenuation at the 25 Hz band
   (95% CI [45.784, 50.478]) against a ≥20 dB spec, better in 20/20 pairs.
4. True articulation-position RMS improved by 0.1196 rad
   (95% CI [−0.1396, −0.1028]), better in 20/20 pairs.
5. Overshoot improved by 162.91 % (95% CI [−171.27, −156.37]), 20/20.
6. Settling improved by 3.436 s, better in 19/20, with 10/20 pairs non-finite.
7. **0 of 40 runs passed the certification gauntlet**; filtered passed
   attenuation 20/20, tracking RMS 3/20, settling 0/20, overshoot 0/20.
8. The design was preregistered and frozen (manifest hash + commit ordering).
9. Loop rate held at ~200 Hz across all 40 runs, within the frozen ±2% tolerance.
10. The evidence is verifiable without GPU, ROS or Isaac Sim.

## 4. Non-claims preserved

Carried verbatim from the frozen manifest and `RESULTS.md` §9 into `README.md`,
`docs/M4_CASE_STUDY.md` §7 and the visual:

- Simulation only; no physical hardware was involved.
- One Franka joint-space scenario; no generalization is claimed.
- No sim-to-real transfer is demonstrated or claimed.
- No robot safety claim.
- No certification or compliance claim.
- No production-readiness claim.
- No claim that these results transfer to any physical Franka or any other robot.

Additionally preserved and reinforced:

- **No GA equivalence.** All results are scoped to the `6.0.1-rc.7` release
  candidate. Isaac Sim 6.0.1 GA was not evaluated.
- **No certification claim from the "gauntlet" name.** 0/40 passed.
- **n=20; intervals are wide; no significance test is offered.**
- **Fresh runs are not bit-reproducible** (PhysX / ROS transport).
- **The disturbance is a software model**, not a measured real-robot profile.

## 5. Scope compliance

Confirmed **not** done by this change:

- No rerun of the 40-run campaign · no threshold changed · no scenario added
- No ROS/Isaac runtime behaviour changed · no evidence packet, manifest or
  `RESULTS.md` modified
- No hardware work · no sim-to-real, GA-equivalence, safety, certification or
  production-readiness claim introduced
- No VRTV condition executed · no seeded incorrect diagram merged
- Nothing published externally

## 6. Audit verdict

**PASS. No open findings.**

F-1 through F-5 and F-8 through F-12 are fixed; F-6 and F-7 are disclosed by
design. F-10, F-11 and F-12 were raised by independent review *against the fix
for F-8* — the read-only verifier itself had a fail-open path and an incomplete
comparison set, both now closed and covered by negative tests.

Validation on a clean worktree at the reviewed head:

- `python -m pytest dsp/ gauntlet/ campaign/ -q` → **209 passed**
- `python scripts/build_results.py --check …` → `valid 40/40
  integrity_passed=True`, `read-only check: 42/42 artifacts reproduced
  byte-for-byte`, `CHECK PASSED`, exit 0
- `git status --porcelain` after verification → **empty**
- Negative control: `--check --timestamp 1999-01-01T00:00:00Z` → 41 MISMATCH
  lines, exit 1, repository still unmodified

The public surface now states the strongest defensible version of the M4 result
and states its most important failure — 0/40 passed — with equal prominence. The
claim boundary is intact and no claim exceeds its evidence.
