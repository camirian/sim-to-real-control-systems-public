# M4 demo package — 2 to 4 minute cut

**Status: NOT PUBLISHED. Requires owner approval before recording or upload.**

This is the short public cut. The longer 3–6 minute engineering walkthrough is
[DEMO_OUTLINE.md](DEMO_OUTLINE.md) and remains the reference for the defect
narrative; this document is the tightened version for a public front door.

Every spoken number below is quoted verbatim from committed evidence and is
listed with its source in [§3 Exact statements](#3-exact-statements). **Do not
ad-lib numbers while recording.**

---

## 1. Script (target 3:10, hard ceiling 4:00)

### Beat 1 — The question (0:00–0:25)

> Adding a filter to a control loop is usually asserted, not measured. Filtering
> removes sensor noise, but it costs phase lag, and lag in a closed loop can hurt
> more than the noise it removes. So: does causal in-loop filtering actually
> improve tracking? I ran a preregistered experiment to find out.

**On screen:** the closed-loop diagram,
`docs/assets/m4_architecture_results.svg` (left half).

### Beat 2 — The system (0:25–1:00)

> A Franka arm in Isaac Sim. Joint states publish at 200 Hz. A noise injector
> adds Gaussian noise and a 25 Hz vibration on the feedback path. A DSP node
> filters it — 4th-order Butterworth, 5 Hz cutoff, causal only. A waypoint
> controller closes the loop back into the articulation.
>
> The control arm isn't a missing filter node — it's an explicit passthrough, so
> both conditions run identical code paths.

**On screen:** `closed_loop.launch.py`, then the three node files; then the arm
moving in Isaac Sim.

### Beat 3 — Why you can trust it (1:00–1:45)

> The design was frozen before any run. The manifest is hashed and committed, and
> git history shows it predates every result. Twenty seeds, both conditions,
> paired. Arm order fixed in advance. Exclusion rules written in advance. A failed
> run stays in the denominator — it's never re-rolled onto a fresh seed.
>
> Forty runs scheduled, forty valid, zero invalid, zero execution failures — and
> "zero execution failures" means they ran cleanly, not that they passed. All 120
> hashed raw source files re-hash clean.

**On screen:** the manifest hash; `git log --follow campaign/manifests/` beside
`git log campaign/results/`; the integrity block.

### Beat 4 — Runtime caught what static checks could not (1:45–2:25)

> Three defects showed up only when it actually ran.
>
> The scene contract passed against the USD file — and the publisher emitted zero
> messages, because `stageMetersPerUnit` wasn't wired.
>
> The default graph sampled at 30 hertz. That's below Nyquist for a 25 hertz
> disturbance — it would have aliased the noise straight onto the 5 hertz filter
> cutoff and I'd have measured an artifact that looked completely healthy.
>
> And the reference signal was initially derived from controller progress, which
> would have handed a worse controller an easier target. A pilot run caught it
> before the design was frozen.

**On screen:** the `stageMetersPerUnit` error and message count 0; the 30.02 Hz
measurement; the pilot-run note.

### Beat 5 — The result (2:25–2:55)

> Filtering improved tracking RMS error by 0.229 radians, 95% confidence interval
> −0.248 to −0.212, and filtered won in twenty out of twenty seed pairs. The
> filter delivered 48 dB of attenuation at the disturbance band against a 20 dB
> spec.
>
> Measured at the arm's *actual* position rather than the signal the controller
> reads, the improvement is about half that — 0.120 radians. Both numbers are
> published, because reporting only the first would flatter the filter.

**On screen:** the results table, `docs/assets/m4_architecture_results.svg`
(right half).

### Beat 6 — What failed (2:55–3:10) — **do not cut this beat**

> And zero of the forty runs passed the certification gauntlet. Not the filtered
> ones either. The filter passed its attenuation check twenty out of twenty, but
> the controller missed its tracking, settling and overshoot targets.
>
> Those thresholds were tuned for an open-loop synthetic profile, not this loop.
> I left them wrong and reported the failure, because a gauntlet you relax until
> it goes green measures nothing.
>
> This is simulation only. No hardware, no transfer claim, no safety or
> certification claim.

**On screen:** the per-check pass/fail table; then the claim-boundary panel.

---

## 2. Shot list

| # | Shot | Source | Capture |
|---|---|---|---|
| 1 | Closed-loop diagram | `docs/assets/m4_architecture_results.svg` | Still, slow zoom on left half |
| 2 | Launch file + 3 node files | `ros2-ws/src/control_loop/` | Editor, syntax highlighted |
| 3 | Franka arm tracking trajectory | Isaac Sim `6.0.1-rc.7` | Screen capture, ~15 s loop |
| 4 | Manifest hash | `campaign/manifests/…v1.json` | Terminal `sha256sum` |
| 5 | Freeze proof | `git log --follow campaign/manifests/` vs `git log campaign/results/` | Split terminal |
| 6 | Integrity + counts | `campaign_summary.json` | Terminal, `jq` |
| 7 | `stageMetersPerUnit` error, msg count 0 | `docs/M4_RUNTIME_VALIDATION.md` | Terminal replay or doc still |
| 8 | 30.02 Hz measurement | `docs/M4_RUNTIME_VALIDATION.md` | Doc still |
| 9 | Results table | `docs/assets/m4_architecture_results.svg` | Still, right half |
| 10 | Per-check pass/fail | `docs/M4_CASE_STUDY.md` §6 | Doc still |
| 11 | Claim boundary panel | `docs/assets/m4_architecture_results.svg` | Still, bottom |
| 12 | Read-only repro + clean tree | Terminal | Live: `build_results.py --check` (42/42 byte-for-byte) then `git status --porcelain` empty |

Shot 12 is the strongest single shot in the demo — 42 derived artifacts rebuilt
from raw evidence, all byte-matching the committed copies, with the working tree
still clean afterwards. If time forces a cut, cut shot 3
before shot 12.

---

## 3. Exact statements

Approved sentences. Each traces to an artifact. Nothing else may be stated as a
result.

| # | Statement | Source |
|---|---|---|
| S1 | "40 scheduled, 40 valid, 0 invalid, 0 execution failures, 0 missing." — never shorten to "0 failed" | `campaign_summary.json` |
| S2 | "120 of 120 hashed raw source artifacts verified, 0 mismatched" (40 runs × run_meta.json + telemetry.csv + truth.csv). The 40 graded packets are separate and are verified by byte-for-byte rebuild. | `campaign_results.json` → `integrity` |
| S3 | "Tracking RMS error improved by 0.2288 rad, 95% CI [−0.2484, −0.2123]." | `campaign_results.json` → `paired.tracking_rms_error` |
| S4 | "Filtered better in 20 of 20 seed pairs." (tracking RMS, attenuation, overshoot, true RMS) | same, `n_filtered_better` |
| S5 | "48.115 dB attenuation at the 25 Hz band, 95% CI [45.784, 50.478], against a ≥20 dB spec." | `paired.filter_attenuation_db` |
| S6 | "True articulation-position RMS improved by 0.1196 rad, 95% CI [−0.1396, −0.1028]." | `secondary.true_tracking_rms_error_rad` |
| S7 | "Settling improved by 3.436 s, better in 19 of 20 pairs; 10 of 20 pairs never settled." | `paired.settling_time_s` |
| S8 | "Loop rate 199.99999999 Hz, all 40 runs within ±2%." | `campaign_results.json` → `rate` |
| S9 | "Zero of 40 runs passed the certification gauntlet." | 40 evidence packets, `overall_passed: false` |
| S10 | "Filtered arm: attenuation 20/20 pass, tracking RMS 3/20, settling 0/20, overshoot 0/20." | per-check verdicts across evidence packets |
| S11 | "Isaac Sim 6.0.1-rc.7+release.42383.32955d8d.gl — a release candidate. GA was not evaluated." | manifest `environment` |

**Banned phrasings.** Do not say, in any form:

- "passed the gauntlet" / "all runs passed" / "certified" / "validated for use"
- bare **"0 failed"** — always "0 execution failures", so it cannot be heard as a
  passing grade next to "0 of 40 passed"
- "120 evidence packets verified" — the 120-file integrity set is the *raw source*
  artifacts; the graded packets are a separate, smaller set
- "sim-to-real" as an achieved result (it is the repo's *subject*, not a claim)
- "production ready", "safe", "compliant"
- "works on Isaac Sim 6" without the `-rc.7` qualifier
- "proves filtering is better" — say *measured*, in this scenario, on this build
- any number not in the table above

---

## 4. Repository / video-link integration plan

**Nothing here executes without owner approval.**

1. **Record** shots 1–12. Reuse existing stills where possible; only shots 3, 5,
   6 and 12 need live capture.
2. **Owner reviews** the cut against §3. Every spoken number checked against the
   table.
3. **Publish** to the same channel as the existing demo links in `README.md`.
4. **Link it** in exactly two places:
   - `README.md` → the "Demo" line in the front-door block.
   - `docs/M4_CASE_STUDY.md` → a one-line pointer under §1.
5. **Video description** carries the claim boundary verbatim:
   > Simulation only (Isaac Sim 6.0.1-rc.7). No physical hardware, no sim-to-real
   > transfer, no safety or certification claim. 0 of 40 runs passed the
   > acceptance thresholds; the measured result is the filtered-vs-unfiltered
   > contrast. Evidence and reproduction: <repo URL>
6. **Do not** update `RESULTS.md`, the manifest, or any evidence file. This is
   distribution only.

---

## 5. Human actions required

- [ ] Approve this script and the §3 statement table
- [ ] Record shots (needs an Isaac Sim 6.0.1-rc.7 host for shot 3)
- [ ] Review the cut against §3
- [ ] Approve publication and provide the video URL
- [ ] Approve the two README/case-study link edits

*No video is published from this repository.*
