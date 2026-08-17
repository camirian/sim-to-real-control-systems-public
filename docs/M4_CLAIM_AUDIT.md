# M4 claim-boundary and public-surface audit

**Date:** 2026-08-16 · **Baseline:** `main` @ `f03c748`, plus the public-proof
changes on `docs/m4-public-proof`. **Method:** every public-facing claim traced to a
primary artifact under `campaign/`, re-derived from the committed JSON.

## 1. Verified facts

| Fact | Value | Source |
|---|---|---|
| Run counts | attempted 40, valid 40, invalid 0, **execution** failures 0, missing 0 | `campaign_summary.json`, `campaign_results.json.counts` |
| Raw-artifact integrity | checked 120, ok 120, mismatched 0, missing 0 — composition: 40 runs × {run_meta.json, telemetry.csv, truth.csv} | `campaign_results.json.integrity`, `campaign_summary.json.integrity_index` |
| Loop rate | mean 199.99999999899944 Hz, n=40, all within tolerance | `campaign_results.json.rate` |
| Tracking RMS diff | −0.22884766390016834 rad, CI [−0.24835462992253976, −0.2122944430180847], 20/20 | `paired.tracking_rms_error` |
| Attenuation diff | +48.11513753981959 dB, CI [45.783948768227255, 50.47822417129975], 20/20 | `paired.filter_attenuation_db` |
| Overshoot / settling diff | −162.9113539936193 % (20/20); −3.4355 s (19/20, **10/20 pairs non-finite**) | `paired.overshoot_pct`, `paired.settling_time_s` |
| True-position RMS diff | −0.11963329154837872 rad, CI [−0.13959854697590873, −0.10283181224689561], 20/20 | `secondary.true_tracking_rms_error_rad` |
| **Gauntlet verdict** | **0 of 40 runs `overall_passed: true`** | all 40 evidence packets |
| Per-check | filtered: attenuation 20/20 · tracking 3/20 · settling 0/20 · overshoot 0/20. unfiltered: 0/20 on all four | evidence packets |
| Simulator / manifest hash | `6.0.1-rc.7+release.42383.32955d8d.gl` · `1d227e43…238052` | manifest, `campaign_summary.json` |

## 2. Findings

### F-1 — "40/40 valid" is readily misread as "40/40 passed" — **FIXED**

**Severity: high.** `valid` means *admitted under the preregistered exclusion
rules* and says nothing about thresholds; next to "certification gauntlet" a
reader infers the runs passed. **They did not — 0 of 40 passed.** Previously
disclosed only as prose in `RESULTS.md` §8, never as a count. **Fix:** stated
explicitly in `README.md`, `docs/M4_CASE_STUDY.md` §6 and the visual.

### F-2 — README pinned Isaac Sim 4.5.0 while all evidence came from 6.0.1-rc.7 — **FIXED**

**Severity: high.** The front-door version table and architecture diagram both
said `4.5.0`; no result here was produced on 4.5.0, so the pin table attributed
every number to the wrong build. **Fix:** the table pins the exact RC build and
scopes each version to what it applies to; the diagram label is corrected.

### F-3 — README lede implied a recorded demo exists — **FIXED**

**Severity: medium.** The lede read "One recorded closed-loop demo…" while no
video is published here. **Fix:** it describes the system, not an artifact.

### F-4 — MASTER_PLAN.md promised a demo beat that the evidence contradicts — **FIXED**

**Severity: medium.** `MASTER_PLAN.md` goal 3 specified "noisy run failing checks
→ filtered run passing". **No filtered run passes** — recording it as written
would produce a false public claim. **Fix:** goal 3 now describes the
preregistered contrast, notes 0 of 40 passed, and points at `DEMO_OUTLINE.md`.

### F-5 — Governing pins contradicted the corrected front door — **FIXED**

**Severity: high.** `AGENTS.md` (binding) and `MASTER_PLAN.md` prescribed ROS 2
Humble / Isaac Sim 4.5.0 as the supported configuration while the README declared
6.0.1-rc.7 — front door and mandatory build instructions specified incompatible
environments. **Fix:** `AGENTS.md` §2 splits the pin into the **empirical
runtime** governing all M4 evidence (6.0.1-rc.7 + Isaac's ROS 2 Jazzy) and the
**legacy DevContainer / `scripts/` path** (Humble / 4.5.0), which produced no
published result. `MASTER_PLAN.md` carries the same note; REQ-S2R-300 names both.
`docs/RUN_ON_EDGEXPERT.md` keeps 4.5.0 — it is the runbook for exactly that
legacy path, so it is no longer contradictory.

### F-6 — Settling-time interval rests on half the pairs — **DISCLOSED**

**Severity: low.** 10 of 20 settling pairs are non-finite (never settled),
excluded from the interval but retained in the win fraction, so the CI rests on
10 pairs. Disclosed in `docs/M4_CASE_STUDY.md` §5 and the visual; the README
table omits settling rather than show the weakest number uncaveated.

### F-7 — Two different "tracking error" metrics — **DISCLOSED**

**Severity: medium if conflated.** `tracking_rms_error` scores the *post-filter
signal the controller consumes*; `true_tracking_rms_error_rad` scores the
*articulation's actual position*. The true-metric improvement (−0.1196 rad) is
roughly **half** the consumed-signal one (−0.2288 rad), so reporting only the
latter would overstate the filter ~2×. Both are published.

### F-8 — the documented regeneration command rewrites evidence timestamps — **DEFERRED**

**Severity: low (process), medium (optics).** `scripts/build_results.py` is a
*generation* command: run without `--timestamp` it rewrites all 40 evidence
packets and `campaign_results.json`, setting `generated_at` to `null` — 41
modified files, which reads as tampering when the step is described as
"verification".

**Not fixed in this PR.** A read-only verification mode was prototyped and then
**removed from this PR** as scope expansion: it accumulated its own defects
across successive review rounds while blocking a proof that does not depend on
it. `docs/REPRODUCE_CAMPAIGN.md` §A2 therefore describes `build_results.py` as
regeneration, and integrity checking is the pre-existing
`campaign/test/test_committed_campaign.py`, which re-hashes every evidence file
against the digest in its own packet and asserts every scheduled run is present.
`build_results.py` is byte-identical to `main` on this branch.

### F-9 — the 120-file integrity set was described as "evidence files" — **FIXED**

**Severity: medium.** The front door pointed at `evidence/` for "the 40 raw
packets" and called the integrity check "120/120 evidence files". Both wrong:
`evidence/run-*.json` is **regenerated graded output**; the **raw** artifacts
live per run; and the 120-file set is exactly 40 × {`run_meta.json`,
`telemetry.csv`, `truth.csv`} per `integrity_index.files` — excluding the graded
packets and `raw_evidence.json`. Blurring them would imply the graded output is
hash-pinned source. **Fix:** `README.md` carries a three-row path table and the
exact composition; `docs/M4_CASE_STUDY.md` §4 makes the same split.

## 3. Public claims introduced by this change

Each restates a verified fact in §1 — no new measurement was created.

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
`docs/M4_CASE_STUDY.md` §7 and the visual —

- Simulation only; no physical hardware was involved.
- One Franka joint-space scenario; no generalization is claimed.
- No sim-to-real transfer is demonstrated or claimed.
- No robot safety claim.
- No certification or compliance claim.
- No production-readiness claim.
- No claim that these results transfer to any physical Franka or any other robot.

Additionally preserved:

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
- No generated document changed: `RESULTS.md` is byte-identical to `main`
- No ROS/Isaac runtime behaviour changed
- No hardware work · no sim-to-real, GA-equivalence, safety, certification or
  production-readiness claim introduced
- No seeded incorrect diagram merged · nothing published externally

## 6. Audit verdict

**PASS. No open findings.**

F-1..F-5 and F-9 are fixed; F-6 and F-7 are disclosed by design; F-8 is deferred
(above) and its subject is unchanged from `main`.

This PR is documentation-only: no code, test, CI, campaign evidence, manifest,
threshold or generated document changes.

Validation on a clean clone at the reviewed head: **297 tests passed** — 209
dsp/gauntlet/campaign, 14 scenes, 74 control_loop.

The public surface states the strongest defensible version of the M4 result and
its most important failure — 0/40 passed — with equal prominence. No claim
exceeds its evidence.
