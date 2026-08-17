# M4 claim-boundary and public-surface audit

**Date:** 2026-08-16 · **Baseline:** `main` @ `f03c748`, plus the public-proof
changes on `docs/m4-public-proof`. **Method:** every public-facing claim traced
to a primary artifact under `campaign/`, re-derived from the committed JSON
rather than copied from prose.

## 1. Verified facts

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

**Severity: high.** The largest misreading risk on the public surface. `valid`
means *admitted under the preregistered exclusion rules* and says nothing about
acceptance thresholds; next to "certification gauntlet" a reader infers the runs
passed. **They did not — 0 of 40 passed.** Previously disclosed only as a prose
caveat in `RESULTS.md` §8, never as a count.

**Fix:** stated explicitly in `README.md` ("In 60 seconds"),
`docs/M4_CASE_STUDY.md` §6, and the results visual.

### F-2 — README pinned Isaac Sim 4.5.0 while all evidence came from 6.0.1-rc.7 — **FIXED**

**Severity: high.** The front-door version table and architecture diagram both
said `4.5.0`; no result here was produced on 4.5.0, so the pin table attributed
every number to the wrong build. **Fix:** the table pins the exact RC build and
scopes each version to what it applies to; the diagram label is corrected.

### F-3 — README lede implied a recorded demo exists — **FIXED**

**Severity: medium.** The lede read "One recorded closed-loop demo…" while no
video is published here. **Fix:** it now describes the system, not an artifact.

### F-4 — MASTER_PLAN.md promised a demo beat that the evidence contradicts — **FIXED**

**Severity: medium.** `MASTER_PLAN.md` goal 3 specified "noisy run failing
checks → filtered run passing". **No filtered run passes** — recording it as
written would produce a false public claim. **Fix:** goal 3 now describes the
preregistered contrast, notes that 0 of 40 passed, and points at
`docs/DEMO_OUTLINE.md`.

### F-5 — Governing pins contradicted the corrected front door — **FIXED**

**Severity: high.** `AGENTS.md` is the binding operating guide and
`MASTER_PLAN.md` repeats it; together they prescribed ROS 2 Humble / Isaac Sim
4.5.0 as the supported configuration while the README declared 6.0.1-rc.7 — the
front door and the mandatory build instructions specified incompatible
environments.

**Fix:** `AGENTS.md` §2 splits the pin into two explicitly-scoped entries — the
**empirical runtime** governing all M4 evidence (6.0.1-rc.7 + Isaac's ROS 2
Jazzy) and the **legacy DevContainer / `scripts/` path** (Humble / 4.5.0), which
produced no published result. `MASTER_PLAN.md` carries the same note and
REQ-S2R-300 names both. `docs/RUN_ON_EDGEXPERT.md` keeps 4.5.0 — it is the
runbook for exactly that legacy path, so it is no longer contradictory.

### F-6 — Settling-time interval rests on half the pairs — **DISCLOSED**

**Severity: low.** 10 of 20 settling pairs are non-finite (never settled),
excluded from the interval but retained in the win fraction, so the CI rests on
10 pairs. Disclosed in `docs/M4_CASE_STUDY.md` §5 and the visual; the README
60-second table omits settling rather than show the weakest number uncaveated.

### F-7 — Two different "tracking error" metrics — **DISCLOSED**

**Severity: medium if conflated.** `tracking_rms_error` scores the *post-filter
signal the controller consumes*; `true_tracking_rms_error_rad` scores the
*articulation's actual position*. The true-metric improvement (−0.1196 rad) is
roughly **half** the consumed-signal one (−0.2288 rad), so reporting only the
latter would overstate the filter ~2×. Both are published in the README table,
case study §5 and the visual.

### F-8 — the documented verification command mutated committed evidence — **FIXED**

**Severity: low (process), medium (optics).** Executing the documented Path A
verification regenerated `RESULTS.md` byte-identically, but the same invocation
rewrote all 40 evidence packets and `campaign_results.json`, setting
`generated_at` to `null` because `--timestamp` defaults to `None`. A reader
following the documented steps saw 41 modified files immediately after a
"verification" step — which reads as evidence tampering.

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

**Severity: high.** `RESULTS.md` is generated and its §10 is emitted by
`render()`, which still told readers to run `build_results.py` without `--check`
— the document produced by the fix published the instruction the fix exists to
remove.

**Fix:** `render()` emits the `--check` form plus a `git status --porcelain`
assertion. `RESULTS.md` regenerated with the committed timestamp
`2026-08-14T21:00:00Z`: **8 insertions, 4 deletions of instruction text, no
number altered, no evidence packet touched**.

### F-11 — `--check` passed when raw integrity failed — **FIXED**

**Severity: high (fail-open).** The exit decision considered only byte equality
of derived artifacts, but `verify_integrity()` can return `passed=False` while
those artifacts *faithfully reproduce* the failure — so a corrupted tree
committed with its regenerated outputs printed `CHECK PASSED` and exited 0. The
verifier failed open on the exact case it exists to catch.

**Fix:** the raw-integrity verdict is part of the failure condition.

**Verified** by reproducing it: append a byte to a hash-covered `truth.csv`,
regenerate derived artifacts to match, run `--check` → `integrity_passed=False`,
`42/42 artifacts reproduced byte-for-byte`, `FAIL raw-artifact integrity: 1
mismatched`, exit 1. Before the fix this input exited 0.

### F-12 — extra committed packets were never compared — **FIXED**

**Severity: medium.** The comparison loop iterated files *rebuilt into the
scratch dir*, so a packet present only in the committed `evidence/` directory
was never visited; `--check` could report `42/42` and exit 0 with an unverified
artifact in the tree.

**Fix:** rebuilt and committed filename sets are compared before contents.
**Verified:** planting `run-STALE-9999.json` → `FAIL … committed but not
produced by this campaign`, exit 1.

### F-9 — the 120-file integrity set was described as "evidence files" — **FIXED**

**Severity: medium.** The front door pointed at `evidence/` for "the 40 raw
packets" and called the integrity check "120/120 evidence files". Both wrong:
`evidence/run-*.json` is **regenerated graded output**; the **raw** artifacts
live per run (`raw_evidence.json`, `run_meta.json`, `telemetry.csv`,
`truth.csv`); and the 120-file set is exactly 40 × {`run_meta.json`,
`telemetry.csv`, `truth.csv`} per
`campaign_summary.json.integrity_index.files` — excluding both the graded
packets and `raw_evidence.json`. Blurring the three sets would imply the graded
output is hash-pinned source, which it is not.

**Fix:** `README.md` carries a three-row path table and states the exact
composition of the 120-file set; `docs/M4_CASE_STUDY.md` §4 and its evidence
index make the same split.

### F-13 — `--check` ignored unscheduled raw run directories — **FIXED**

**Severity: medium.** F-12 closed the extra-artifact hole for *generated*
packets but left the identical hole one level down, on the *primary* records.
The raw-loading loop iterates the manifest plan (`for entry in plan`), so a
stale `filtered-*`/`unfiltered-*` directory carrying its own `raw_evidence.json`
was never read and `--check` exited 0. `test_no_extra_run_directories_snuck_in`
already asserted this, but the standalone `--check` path does not run pytest.

**Fix:** `--check` applies the same rule — a directory containing
`raw_evidence.json` is a run, and every run must be scheduled by the frozen
manifest. Keying on `raw_evidence.json` is what stops `evidence/` and the
aggregate JSON files being misread as runs.

**Symmetry audit** of every set the verifier authenticates, against missing
*and* extra members (closure of the `--check` work, not a new framework):

| Set | Missing | Extra |
|---|---|---|
| Manifest-scheduled raw runs | `missing_runs` differs → `campaign_results.json` mismatch → fail | **F-13, now fixed** |
| Raw hash-covered artifacts | `integrity.passed=False` → fail (F-11) | n/a — the index defines coverage |
| Generated gauntlet packets | `compare()` reports missing → fail | F-12 → fail |
| `campaign_results.json` | `compare()` → fail | n/a — single fixed path |
| `RESULTS.md` | `compare()` → fail | n/a — single fixed path |

**Regression coverage:** `test_check_rejects_unscheduled_raw_run_directory`
copies the campaign to a tmp dir, asserts `--check` exits 0, plants
`filtered-9999/raw_evidence.json`, asserts non-zero exit naming the run, removes
it, asserts exit 0 again.

## 3. Public claims introduced by this change

Each is a restatement of a verified fact in §1 — no new measurement was created.

1. 40/40 valid runs (0 execution failures); 120/120 hash-verified raw source
   artifacts; loop rate ~200 Hz within the frozen ±2% tolerance.
2. Paired improvements: tracking RMS 0.2288 rad, attenuation 48.115 dB, true
   articulation RMS 0.1196 rad, overshoot 162.91 % (each 20/20); settling
   3.436 s (19/20, 10/20 pairs non-finite). Intervals in §1.
3. **0 of 40 runs passed the certification gauntlet**; filtered passed
   attenuation 20/20, tracking RMS 3/20, settling 0/20, overshoot 0/20.
4. The design was preregistered and frozen (manifest hash + commit ordering).
5. The evidence is verifiable without GPU, ROS or Isaac Sim.

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

- No campaign execution occurred · no threshold changed · no scenario added ·
  no manifest changed · no evidence packet or raw empirical record changed ·
  no numerical result changed
- `RESULTS.md` **was intentionally regenerated** (F-10) — it is a generated
  document, and its §10 was still emitting the mutating verification command.
  The regeneration used the committed timestamp, so the diff is 8 insertions
  and 4 deletions of instruction text only
- No ROS/Isaac runtime behaviour changed
- No hardware work · no sim-to-real, GA-equivalence, safety, certification or
  production-readiness claim introduced
- No VRTV condition executed · no seeded incorrect diagram merged
- Nothing published externally

## 6. Audit verdict

**PASS. No open findings.**

F-1..F-5 and F-8..F-13 are fixed; F-6 and F-7 are disclosed by design. F-10..F-13
were raised by independent review *against the fix for F-8* — the read-only
verifier itself had a fail-open path and two incomplete comparison sets, all now
closed and covered by negative tests.

Validation on a clean clone at the reviewed head:

- Tests → **210 passed** (dsp/gauntlet/campaign), 14 scenes, 74 control_loop
- `build_results.py --check …` → `valid 40/40 integrity_passed=True`,
  `42/42 artifacts reproduced byte-for-byte`, `CHECK PASSED`, exit 0
- `git status --porcelain` after verification → **empty**
- Negative controls, each exit 1, repository unmodified: corrupted hash-covered
  raw source; extra generated packet; extra raw run directory; wrong timestamp

The public surface states the strongest defensible version of the M4 result and
its most important failure — 0/40 passed — with equal prominence. The claim
boundary is intact and no claim exceeds its evidence.
