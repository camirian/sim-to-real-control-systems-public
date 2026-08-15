# Demo outline — 3 to 6 minutes

Script and shot list only. **No video is published from this repository.**

The spine of this demo is not "the filter works". It is *how you find out whether
it works, and what you had to catch first*. Three of the seven beats are defects
the system found before it was allowed to produce a result — that is the point,
not an apology.

---

## Beat 1 — The static check passes (~30 s)

**Show:** `python -m scenes.scene_contract` exiting 0; the six OmniGraph nodes it
verifies.

**Say:** The scene declares a ROS 2 control graph: read joint state, publish it,
subscribe to commands, drive the articulation. The contract check passes against
the `.usd` without Isaac running. Everything looks correct.

**Land:** "Looks correct" is a claim about the file, not about the system.

---

## Beat 2 — Runtime exposes a zero-publication defect (~45 s)

**Show:** the publisher error `stageMetersPerUnit must be a positive finite
value`; `/joint_states` message count = 0.

**Say:** First run on the real Isaac Sim 6.0.1 host: the graph loads, the
contract still passes, and **zero messages are published**. The joint-state
publisher requires `stageMetersPerUnit` wired from the reader; without it, it
errors out and emits nothing.

**Land:** A static check that passes while the system emits nothing is exactly
what runtime validation is for. It is now a contract clause with a test.

---

## Beat 3 — The default graph runs at 30 Hz, and that invalidates the experiment (~60 s)

**Show:** measured 30.02 Hz next to the configured `sample_rate_hz = 200.0`; a
quick sketch of 25 Hz folding below a 15 Hz Nyquist.

**Say:** Messages now flow. The rate is 30.02 Hz. The DSP path was designed for
200. That is not just a slow loop — the Nyquist frequency is 15 Hz, and the
injected disturbance is at 25 Hz. It **aliases to about 5 Hz**, which is exactly
the filter's cutoff. A filtered-vs-unfiltered campaign in that state would have
been comparing an aliasing artifact, and both arms would have been contaminated
identically, so the comparison itself could never have revealed it.

**Land:** This is the beat that matters. The campaign was stopped here, before
run 1.

---

## Beat 4 — Fix the boundary, not the experiment (~45 s)

**Show:** `dt = 1/400 -> 200.498 Hz observed`; the two-physics-steps-per-tick
finding; final 200.492 Hz over 1833 messages.

**Say:** Two ways out: adopt 30 Hz and change the stimulus, or make the simulator
actually deliver the documented 200 Hz. We changed the sampling boundary and
left the 5 Hz cutoff and 25 Hz disturbance exactly as specified. One thing had to
be measured rather than reasoned: the graph ticks once every *two* physics steps,
so the delivered rate is half the configured rate.

**Land:** Nothing about the filter was tuned to make the numbers better. A guard
now fails the gate if the measured rate misses the target by more than 2%.

---

## Beat 5 — Close the actual loop (~45 s)

**Show:** the phase-D trace — 527 cycles, tracking error 1.237 -> 0.000 rad, both
waypoints reached, no limit clamping.

**Say:** The loop closes through the project's own `WaypointTracker`, not a
lookalike written for the demo: joint states in, command out, articulation
responds, error collapses. `/joint_command` is provably consumed — the commanded
joint moves toward its target while the undriven fingers stay put.

**Land:** That check on the fingers is deliberate. It is how you catch a
`jointNames` mis-wire that would otherwise look like success.

---

## Beat 6 — 40 preregistered trials (~45 s)

**Show:** the frozen manifest and its sha256; the 20-seed schedule; the balanced
arm order; the no-replacement rule.

**Say:** Twenty seeds, each run filtered and unfiltered, forty runs total. The
design was hashed and committed **before the first run**: seed list, arm order,
run length, reset contract, rate tolerance, exclusion rules. Paired seeds mean
both arms see the identical disturbance. A failed run stays in the denominator —
it is never replaced by another seed.

**Land:** Preregistration is only worth anything if changing it afterwards is
visible. Editing any frozen value fails validation.

---

## Beat 7 — The measured result, and its limits (~60 s)

**Show:** the RESULTS.md paired table — mean differences, bootstrap intervals,
the per-seed distribution, and the counts.

**Say:** [State the measured filtered-vs-unfiltered result directly from
RESULTS.md, including any metric where filtered did not win.] Every number is
regenerated from the raw per-run evidence by a script; nothing is hand-entered,
and every evidence file is hash-verified.

**Then state the limits, without softening them:**

- Simulation only. No physical hardware was involved.
- One Franka joint-space scenario, one machine, one Isaac build.
- No sim-to-real transfer claim. No safety claim. No certification claim. No
  production-readiness claim.
- n=20 pairs, and **no statistical significance is claimed** — intervals and the
  raw distribution are shown instead.

**Land:** The interesting artifact here is not the filter. It is that three
separate defects were caught before any of them could turn into a result, and
that the record makes it possible to check that claim rather than take it.

---

## Shot list

| # | Shot | Source |
|---|---|---|
| 1 | `scene_contract` passing | terminal |
| 2 | `stageMetersPerUnit` error + 0 messages | `docs/M4_RUNTIME_VALIDATION.md` |
| 3 | 30.02 Hz vs 200 Hz; aliasing sketch | `docs/M4_RUNTIME_VALIDATION.md` |
| 4 | rate correction to 200.492 Hz | `docs/m4-evidence/isaac6-runtime-validation.txt` |
| 5 | closed-loop trace | same |
| 6 | frozen manifest + hash | `campaign/manifests/` |
| 7 | paired results table | `RESULTS.md` |

## Rules for this recording

- Show terminal output and committed files. Do not re-narrate numbers from
  memory — read them off the artifact on screen.
- If a metric went the wrong way, show it. A demo that only shows wins is the
  same failure mode as a campaign that only reports successful runs.
- No usernames, hostnames, absolute home paths, or private IPs in any frame.
  Hardware is described only as "NVIDIA GB10 / DGX Spark class".
