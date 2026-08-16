# M4 case study — measuring whether an in-loop DSP filter helps, and proving it

**Scope of this document.** One completed simulation experiment on one Franka
joint-space scenario, executed on one Isaac Sim build. Every number below is
copied from committed evidence and is reproducible from this repository without a
GPU. Read [§7 Limitations and non-claims](#7-limitations-and-non-claims) before
citing anything here.

| | |
|---|---|
| Campaign | `m4-franka-filtered-vs-unfiltered` v1 |
| Manifest SHA-256 | `1d227e437317bac11df209d39ac264d7b4ffe9d5f9b5d4bf8c805f266b238052` |
| Simulator | Isaac Sim `6.0.1-rc.7+release.42383.32955d8d.gl` (release candidate; **GA not evaluated**) |
| Design | 20 seeds × 2 conditions, paired, preregistered and frozen before any run |
| Outcome | **40 scheduled, 40 valid, 0 invalid, 0 failed, 0 missing** |
| Evidence integrity | **120/120 files hash-verified, 0 mismatched** |

---

## 1. Problem

A control loop reads joint positions from a sensor, computes a command, and
drives an actuator. Real sensors are noisy. The standard answer is to filter the
feedback signal — but filtering costs phase lag, and phase lag in a closed loop
can hurt more than the noise it removes.

So "add a filter" is not self-evidently correct. It is an empirical claim, and it
is usually asserted rather than measured.

**The question this campaign answers:** in a closed loop with a known injected
disturbance, does causal in-loop filtering measurably improve trajectory tracking
compared to passing the noisy signal through unchanged — and by how much, with
what uncertainty?

**The question it deliberately does not answer:** whether this controller is
*good*. See §7.

## 2. System architecture

A Franka Panda arm in Isaac Sim, with the control loop closed through ROS 2:

```
Isaac Sim articulation
  │  /joint_states            (200 Hz, clean)
  ▼
noise_injector      ── injects AWGN + 25 Hz vibration, seeded
  │  /joint_states_noisy
  ▼
dsp_filter          ── 4th-order Butterworth IIR, 5 Hz cutoff, CAUSAL only
  │  /joint_states_filtered
  ▼
waypoint_controller ── proportional tracker, kp = 0.8
  │  /joint_command
  ▼
Isaac Sim articulation controller  → arm motion
```

Three ROS 2 nodes in `ros2-ws/src/control_loop/control_loop/`, wired by
`launch/closed_loop.launch.py`. Each node is a thin `rclpy` wrapper around a pure
Python logic module, so the logic is unit-testable with no ROS and no simulator.

**Disturbance** (injected on the feedback path, pre-filter): Gaussian noise
σ = 0.1 rad plus a 25 Hz vibration of amplitude 0.3 rad, drawn from
`numpy.random.default_rng(seed)`.

**Filter:** 4th-order Butterworth IIR, 5 Hz cutoff, applied through
`s2r_dsp.apply_filter_realtime`. The zero-phase `filtfilt` path is **banned
in-loop** — it is non-causal and would leak future samples into a real-time
control decision. The unfiltered arm is an explicit passthrough
(`b=[1], a=[1]`, flat 0 dB), not a missing node, so both arms run identical code
paths.

**Rate:** the loop publishes at 200 Hz. Measured across all 40 runs: mean
199.99999999899944 Hz, all within the frozen ±2% tolerance.

## 3. Experimental contract

The manifest was written, hashed, and committed **before any run executed**. It
fixes, in advance:

- **Pairing.** The same 20 seeds run in both conditions. Analysis is paired.
- **Arm order.** Even seed → filtered first; odd seed → unfiltered first. Frozen
  pre-run so ordering cannot drift with results.
- **No replacement.** A failed or invalid run stays in the denominator. It is
  never re-rolled onto a fresh seed and never silently dropped.
- **Exclusion rules,** enumerated in advance: reset failure, sample rate outside
  ±2%, insufficient samples, harness error.
- **Reference signal is exogenous** — time-parameterized, independent of
  controller progress. An earlier endogenous reference was caught by a pilot run
  and fixed *before* the design was frozen (§8).

The freeze is auditable: `git log --follow campaign/manifests/` predates
`git log campaign/results/`.

## 4. The campaign

40 runs, ~24 minutes wall clock (`wall_elapsed_s: 1456.5`).

**40 scheduled · 40 valid · 0 invalid · 0 failed · 0 missing.**

"Valid" means *admitted under the preregistered exclusion rules* — no run hit the
rate tolerance, the sample floor, the reset check, or a harness error. It does
**not** mean the run passed the acceptance thresholds. That distinction is the
subject of §6.

Every run emits an immutable JSON evidence packet containing its seed, scenario,
per-check verdicts, the thresholds it was graded against, and the full
environment fingerprint. All 120 evidence files re-hash clean: **120 checked,
120 ok, 0 mismatched, 0 missing.**

## 5. Key measured result

Paired differences (filtered − unfiltered), n = 20 pairs, 95% bootstrap CI:

| Metric | Mean difference | 95% CI | Filtered better |
|---|---:|---|---:|
| Tracking RMS error (rad) | **−0.2288** | [−0.2484, −0.2123] | **20/20** |
| Filter attenuation @ 25 Hz (dB) | **+48.115** | [45.784, 50.478] | **20/20** |
| Overshoot (%) | **−162.91** | [−171.27, −156.37] | **20/20** |
| Settling time (s) | **−3.436** | [−4.639, −2.127] | 19/20 |
| *True* tracking RMS error (rad) † | **−0.1196** | [−0.1396, −0.1028] | **20/20** |

† Secondary metric. `tracking_rms_error` scores the signal the **controller
consumes** (post-filter). `true_tracking_rms_error_rad` scores the
**articulation's actual position**. These are different claims, and the true-position
improvement is roughly half the size of the consumed-signal improvement. Both are
reported; only reporting the first would flatter the filter.

**Headline:** causal in-loop filtering improved trajectory tracking on every
metric, and the improvement was consistent rather than average-driven — filtered
won in 20 of 20 seed pairs on four of the five metrics. The confidence interval
on the primary metric excludes zero by a wide margin.

**Settling-time caveat:** 10 of 20 pairs contain a non-finite value, because the
run never settled at all. Those pairs are excluded from the interval but retained
in the win fraction. The interval is therefore computed on the 10 finite pairs
only, and is the weakest number in this table.

## 6. What the gauntlet actually returned

**Zero of the 40 runs passed the certification gauntlet.** Not the filtered runs
either.

Per-check verdicts, filtered arm (20 runs):

| Check | Threshold | Passed |
|---|---|---:|
| `filter_attenuation_db` | ≥ 20 dB @ 25±2 Hz | **20/20** |
| `tracking_rms_error` | ≤ 0.15 rad | 3/20 |
| `settling_time_s` | ≤ 2.0 s | 0/20 |
| `overshoot_pct` | ≤ 25 % | 0/20 |

Unfiltered arm: 0/20 on all four checks.

This is stated prominently because it is the most misreadable fact in the
project. "40/40 valid" plus the phrase "certification gauntlet" invites a reader
to conclude the system passed. It did not.

**Why the runs are graded against thresholds they mostly fail:** the gauntlet's
absolute thresholds were tuned against the open-loop synthetic profile in
`s2r_dsp`, not against this closed loop. They were retained for consistency with
the certification path and, deliberately, **were not adjusted to make any arm
pass**. The campaign's question is the filtered-vs-unfiltered *contrast*, which
the paired design answers; it is not a pass/fail certification of the controller,
which would require thresholds derived from this loop's own requirements.

The honest summary: **the filter does its job (20/20 on attenuation); the
controller does not meet its tracking targets.** Both facts come from the same
evidence packets.

## 7. Limitations and non-claims

**Non-claims, verbatim from the frozen manifest and `RESULTS.md` §9:**

- **Simulation only; no physical hardware was involved.**
- **One Franka joint-space scenario; no generalization is claimed.**
- **No sim-to-real transfer is demonstrated or claimed.**
- **No robot safety claim.**
- **No certification or compliance claim.**
- **No production-readiness claim.**
- **No claim that these results transfer to any physical Franka or any other
  robot.**

**Additional limitations:**

- **Release candidate, not GA.** Every number here was observed on
  `6.0.1-rc.7+release.42383.32955d8d.gl`. Isaac Sim 6.0.1 GA is a distinct, later
  release that this project has **not** evaluated. No GA equivalence is claimed.
- **No run passed the acceptance thresholds** (§6).
- **n = 20 pairs.** Intervals are wide; no significance test is offered.
- **One machine, one Isaac build, one robot model, one scenario.**
- **The disturbance is a software model** of sensor noise, not a measured noise
  profile from a real robot.
- **PhysX ran on CPU** (`gpu_dynamics: false`) — observed and recorded, not
  chosen. GPU-vs-CPU PhysX behaviour was not benchmarked.
- **Fresh runs are not bit-reproducible.** PhysX and ROS transport are not
  bit-deterministic. Derived analysis *is* bit-reproducible from committed
  evidence.

## 8. Reproducibility path

**Path A — verify the committed evidence. No GPU, no ROS, no Isaac Sim.**

```bash
git clone https://github.com/camirian/sim-to-real-control-systems-public
cd sim-to-real-control-systems-public
python -m venv .venv && . .venv/bin/activate
pip install -e dsp/ && pip install numpy scipy pytest usd-core

python -m pytest dsp/ gauntlet/ campaign/ -q

# Regenerate the results document from raw evidence and prove it matches.
python scripts/build_results.py \
  --logs-root campaign/results/m4-franka-filtered-vs-unfiltered-v1 \
  --manifest campaign/manifests/m4-franka-filtered-vs-unfiltered-v1.json \
  --out RESULTS.md
git diff --exit-code RESULTS.md
```

An empty diff proves every published figure derives from the raw evidence.
Nothing in `RESULTS.md` is hand-entered.

**Path B — re-run the campaign.** Requires an Isaac Sim 6.x host with an NVIDIA
GPU, ~45 minutes. Full procedure, including the mandatory runtime gate, in
[REPRODUCE_CAMPAIGN.md](REPRODUCE_CAMPAIGN.md).

**Evidence index:**

| Artifact | Path |
|---|---|
| Frozen design | `campaign/manifests/m4-franka-filtered-vs-unfiltered-v1.json` |
| Aggregated results | `campaign/results/m4-franka-filtered-vs-unfiltered-v1/campaign_results.json` |
| Run counts + integrity | `campaign/results/m4-franka-filtered-vs-unfiltered-v1/campaign_summary.json` |
| 40 evidence packets | `campaign/results/m4-franka-filtered-vs-unfiltered-v1/evidence/` |
| Narrative results | [`RESULTS.md`](../RESULTS.md) |
| Runtime validation | [`M4_RUNTIME_VALIDATION.md`](M4_RUNTIME_VALIDATION.md) |

## 9. Lessons learned

**1. A static check that passes while the system emits nothing.** The scene
contract validated the OmniGraph against the `.usd` file and exited 0. On the
real host, the joint-state publisher required `stageMetersPerUnit` wired from the
reader; without it, it errored and published **zero messages**. The contract still
passed. Runtime validation exists precisely for the gap between "the file is
correct" and "the system works."

**2. The default graph sampled at 30.02 Hz.** That is below the Nyquist rate for
the 25 Hz disturbance. Had the campaign run on it, the disturbance would have
aliased down onto the 5 Hz filter cutoff and the experiment would have measured
an artifact while looking entirely healthy. Caught by measuring the rate instead
of assuming it.

**3. The reference signal was initially endogenous** — derived from controller
progress, so a worse controller would face an easier target. Caught by a pilot run
*before* the design was frozen, which is the only reason it could be fixed
without compromising the preregistration.

**4. Grade the signal the actuator produced, not just the one the controller
read.** Reporting only `tracking_rms_error` would have overstated the filter's
benefit by roughly 2×. The secondary true-position metric exists to prevent that.

**5. Don't tune thresholds to produce a pass.** The thresholds were wrong for
this loop, and were left wrong, and the failure was reported. A gauntlet that gets
relaxed until it goes green measures nothing.

**6. Preregistration is what makes the result citable.** The manifest hash and the
commit ordering are what separate "we measured a 0.229 rad improvement" from "we
looked at the data and then decided what to measure."

---

*All figures in this document trace to committed artifacts under `campaign/`.
No measurement was created for this write-up.*
