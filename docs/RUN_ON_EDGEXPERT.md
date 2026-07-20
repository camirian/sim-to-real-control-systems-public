# Run on the EdgeXpert — fresh box to recorded demo

The complete owner runbook for the parts of the sim-to-real demo that **cannot**
run in the cloud or in CI: the live Isaac Sim + ROS 2 closed loop, the seeded
campaign that produces the REQ-S2R-102 money table, and the 2–3 minute recorded
demo. Everything here runs **only on the EdgeXpert** (the local Isaac Sim 4.5.0
machine).

Read [MASTER_PLAN.md](../MASTER_PLAN.md) §5 (environment split) and
[AGENTS.md](../AGENTS.md) §2 (determinism, causal filter only, Isaac never in
CI) first. The cloud milestones M1–M3 are done; this doc closes M4.

> **Convention.** Every step below that has never been executed outside a sim
> box is tagged **`EDGEXPERT-VERIFY`** in the source and gathered into the
> single ordered checklist in [§7](#7-consolidated-edgexpert-verify-checklist).
> Do not report the demo as done until every box there is checked with the
> observed result recorded.

---

## 0. Pinned versions (never "latest")

| Component | Version | Notes |
|---|---|---|
| OS | Ubuntu 22.04 LTS | ROS 2 Humble tier-1 platform |
| ROS 2 | **Humble** | `source /opt/ros/humble/setup.bash` |
| NVIDIA Isaac Sim | **4.5.0** | new `isaacsim` Python entry point |
| Python (DSP/gauntlet/campaign) | 3.10 | matches Humble's Python |
| DSP deps | `numpy`, `scipy` | via `pip install -e "dsp/[test]"` |

RMW / domain: pick one RMW (e.g. `rmw_cyclonedds_cpp`) and one
`ROS_DOMAIN_ID`, and export the **same** values in every shell (Isaac,
launch, logging). A domain-id mismatch is the most common "topics silent"
cause.

---

## 1. Fresh-box setup

```bash
# 1a. ROS 2 Humble (once per box) — see docs.ros.org for the apt steps, then:
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp   # match in ALL shells
export ROS_DOMAIN_ID=17                         # any fixed value, match everywhere

# 1b. This repo + the DSP package (provides s2r_dsp for the filter node,
#     the gauntlet, and the campaign aggregator).
git clone <this-repo> && cd sim-to-real-control-systems-public
python3 -m venv .venv && source .venv/bin/activate
pip install -e "dsp/[test]"

# 1c. Sanity: the no-sim tests must be green before touching Isaac.
python -m pytest dsp/ gauntlet/ campaign/ -q      # expect 118 passed

# 1d. Build the ROS 2 workspace (control_loop nodes).
cd ros2-ws && colcon build --packages-select control_loop
source install/setup.bash
cd ..
```

---

## 2. Bring up Isaac Sim with the Franka scene

The scene `scenes/franka_ros2_bridge_scene.usd` carries a Franka articulation
plus an OmniGraph ROS 2 **joint-state publisher**.

```bash
cd ~/isaac-sim                     # your Isaac Sim 4.5.0 root
./python.sh /path/to/repo/scripts/run_franka_headless.py --steps 600
```

In a second shell (ROS 2 + same RMW/domain sourced) confirm the publisher:

```bash
ros2 topic list                    # expect /joint_states
ros2 topic echo /joint_states      # expect a stream of sensor_msgs/JointState
ros2 topic hz /joint_states        # expect ~200 Hz (the filter assumes this)
ros2 topic info -v /joint_states   # note QoS + joint names + joint count
```

`EDGEXPERT-VERIFY` items in `scripts/run_franka_headless.py` (headless boot,
the ROS 2 bridge extension id, graph survival on `open_stage`, publisher
ticking with `render=False`, clean `close()`) all gate this step — see
[§7](#7-consolidated-edgexpert-verify-checklist).

---

## 3. THE KNOWN GAP — the scene has no `/joint_command` subscriber (blocking)

**The loop cannot close until this is fixed on the sim box.** The committed
`franka_ros2_bridge_scene.usd` only **PUBLISHES** `/joint_states`. The
`waypoint_controller` node publishes position commands on `/joint_command`, but
**nothing in the scene subscribes to them**, so the arm never moves in response
to the controller.

You must add an OmniGraph **`ROS2SubscribeJointState`** node wired into an
**Articulation Controller** for the Franka, listening on `/joint_command`
(`sensor_msgs/JointState` positions). The exact assumption is documented at the
controller's publisher:

- `ros2-ws/src/control_loop/control_loop/waypoint_controller_node.py:77–82`
  — *"The current franka_ros2_bridge_scene.usd only PUBLISHES joint states; the
  subscriber graph node must be added (or the scene extended) on the sim box
  before closed-loop runs."*
- `ros2-ws/src/control_loop/README.md` "Build & launch" section — same note.

How to add it (Isaac Sim 4.5.0, in the scene, then re-save the USD):

1. Open `scenes/franka_ros2_bridge_scene.usd` in Isaac Sim.
2. In the existing OmniGraph (or a new Action Graph), add
   `ROS2SubscribeJointState`, topic `/joint_command`.
3. Feed its `positionCommand`/`jointNames` outputs into an
   `ArticulationController` (or `IsaacArticulationController`) targeting the
   Franka articulation root.
4. Confirm the joint **names** the subscriber expects match
   `DEFAULT_JOINT_NAMES` in `waypoint_controller_node.py:26` (the 7 `panda_jointN`);
   fingers are excluded from commands.
5. Re-save the USD. **Regenerate**, never edit in place, if you keep evidence
   from an earlier scene revision.

Verify before closing the loop:

```bash
# With Isaac up and the loop NOT yet launched, hand-publish one command and
# confirm the arm twitches / the subscriber receives it:
ros2 topic pub --once /joint_command sensor_msgs/msg/JointState \
  '{name: [panda_joint1], position: [0.1]}'
ros2 topic info -v /joint_command   # expect 1 subscriber (the scene)
```

---

## 4. Run the closed loop

With Isaac up (§2) and the `/joint_command` subscriber added (§3):

```bash
source /opt/ros/humble/setup.bash && source ros2-ws/install/setup.bash
ros2 launch control_loop closed_loop.launch.py seed:=42 filter_kind:=iir cutoff_hz:=5.0
```

Topology (all three nodes are pure-logic + thin rclpy wrappers, unit-tested
without ROS; only their runtime wiring is `EDGEXPERT-VERIFY`):

```
/joint_states -> noise_injector -> /joint_states_noisy
              -> dsp_filter      -> /joint_states_filtered   (causal path only)
              -> waypoint_controller -> /joint_command
```

Launch args: `seed, awgn_sigma, vibration_amplitude, vibration_freq_hz`
(noise); `filter_kind, sample_rate_hz, cutoff_hz, numtaps, order` (filter);
`kp, tolerance_rad, max_step_rad, waypoint_timeout_s` (controller). Full list:
`ros2-ws/src/control_loop/README.md`.

**Filtered vs. unfiltered.** A filtered run uses `filter_kind:=iir`. An
unfiltered run must bypass the filter. Two options — pick one and record it:
- add a `passthrough` `filter_kind` to `dsp_filter_node.py` (copies input to
  output), then run `filter_kind:=passthrough`; **or**
- point the controller's `input_topic` at `/joint_states_noisy` and don't start
  the filter node.
The campaign runner (`campaign/run_campaign.py`) assumes the `passthrough`
kind; if you take the second option, pass the controller override via
`--` extra args. This is an `EDGEXPERT-VERIFY` item.

---

## 5. Collect run-logs the gauntlet can grade

Each run must land as one directory in the gauntlet's run-log layout
(`gauntlet/run_log.py`):

```
logs/<run_id>/
    run_meta.json     {"run_id": "filtered-0042", "scenario": "franka-joint-tracking", "seed": 42}
    telemetry.csv     header: t,reference,measured[,noisy]
```

- `t` strictly increasing seconds; `reference` the commanded joint position;
  `measured` the stream under test (post-filter for filtered runs, raw
  `/joint_states_noisy` for unfiltered runs); `noisy` (optional) the pre-filter
  stream — **include it** so the filter-attenuation check runs.
- Record **one representative joint** (e.g. `panda_joint1`) per run — the
  checks are single-signal.
- Export from a rosbag (`ros2 bag record` the loop topics, then a CSV export)
  or write the CSV directly from a small logging node. The exact
  rosbag→CSV convention is `EDGEXPERT-VERIFY` (see `campaign/run_campaign.py`
  `run_one`).

Grade one run to smoke-test the pipeline before the full sweep:

```bash
python -m gauntlet.cli logs/filtered-0042 --evidence-dir evidence \
  --timestamp "$(date -u +%FT%TZ)"          # writes evidence/run-filtered-0042.json + .md
```

---

## 6. Run the campaign and build the money table (REQ-S2R-102)

The campaign is a paired sweep: **≥ 20 seeds, each run filtered and
unfiltered**, all graded, then aggregated into `results_table.md` +
`results.json`.

One command drives the whole thing on the sim box (the seeded-sweep + grading +
aggregation glue is real and tested; the `ros2 launch` execution inside it is
`EDGEXPERT-VERIFY`):

```bash
python -m campaign.run_campaign --seeds $(seq 1 20) \
    --logs-root logs --evidence-dir evidence \
    --timestamp "$(date -u +%FT%TZ)"
```

That expands to, for each seed, an unfiltered then a filtered run
(`unfiltered-0001`, `filtered-0001`, …), grades every log with
`python -m gauntlet.cli`, then runs the aggregator. If you prefer to run the
stages by hand, the last stage is just:

```bash
python -m campaign.cli evidence --out-dir evidence --timestamp "$(date -u +%FT%TZ)"
# -> evidence/results_table.md  (commit this — it is the money artifact)
# -> evidence/results.json
```

Exit codes: `0` filtered beats unfiltered on tracking RMS · `1` it does **not**
(the harness reports the regression honestly — investigate, do not massage) ·
`2` invalid input.

**Commit the evidence packets and `results_table.md`.** Packets are immutable
records (AGENTS.md §2) — regenerate under new run ids, never edit.

### 6a. Dry run the aggregator anywhere (no sim) — the cloud/CI smoke test

This is the only part of §6 runnable off the sim box; CI runs exactly this. Use
it to confirm the aggregator before you have real logs:

```bash
python -c "from campaign.synth import write_campaign; \
  write_campaign('/tmp/demo_evidence', n_filtered=20, n_unfiltered=20, \
  generated_at='2026-07-19T00:00:00Z')"
python -m campaign.cli /tmp/demo_evidence --out-dir /tmp/demo_out \
  --timestamp 2026-07-19T00:00:00Z
```

A committed rendering of this synthetic demo lives in `campaign/example/`
(scenario `franka-joint-tracking-synthetic` — the `-synthetic` suffix marks it
as **not** a real run).

---

## 7. Consolidated EDGEXPERT-VERIFY checklist

Every runtime assumption from the M1/M2 sim work plus M4's runner, in execution
order. Check each box and record the observed result (a topic echo, an `hz`
reading, an exit code) — that record is what turns "authored in the cloud" into
"verified on the sim box" (AGENTS.md §5).

### A. Isaac scene brings up the publisher

- [ ] `scripts/franka_wave.py:12` — script still launches and the arm waves
      under Isaac 4.5.0 after the `isaacsim` import swap.
- [ ] `scripts/run_franka_headless.py:58` — `headless=True` boots without a
      display (no X/GL for a physics-only run).
- [ ] `scripts/run_franka_headless.py:71` — ROS 2 bridge extension id:
      expected `isaacsim.ros2.bridge`; fall back to `omni.isaac.ros2_bridge` if
      the install ships the legacy id. ROS 2 Humble env (RMW, `ROS_DOMAIN_ID`)
      sourced first.
- [ ] `scripts/run_franka_headless.py:78` — `open_stage` loads the scene and the
      OmniGraph survives being opened headless.
- [ ] `scripts/run_franka_headless.py:84` — `stage_units_in_meters` matches how
      the USD was authored.
- [ ] `scripts/run_franka_headless.py:93` — the OmniGraph publisher ticks on
      physics steps with `render=False`; if `/joint_states` stays silent, step
      with `render=True` and record which works.
- [ ] `scripts/run_franka_headless.py:103` — `close()` exits code 0 headless
      (no hang).

### B. THE GAP — add the `/joint_command` subscriber (blocking; see §3)

- [ ] `waypoint_controller_node.py:77–82` — add an OmniGraph
      `ROS2SubscribeJointState` on `/joint_command` feeding an articulation
      controller; the scene currently only publishes. Loop cannot close without
      this. (`ros2-ws/src/control_loop/README.md` carries the same note.)
- [ ] `waypoint_controller_node.py:92` — joint ordering/names from the
      publisher match `DEFAULT_JOINT_NAMES` (7 `panda_jointN`); extras/fingers
      ignored.

### C. Topic wiring & QoS

- [ ] `noise_injector_node.py:40` — input topic name + QoS match the OmniGraph
      publisher (`/joint_states`, depth-10). Confirm with
      `ros2 topic info -v /joint_states`.
- [ ] `noise_injector_node.py:64` — the Franka scene publishes a fixed joint
      count (expected 9: 7 arm + 2 fingers).
- [ ] `noise_injector_node.py:68` — vibration phase is driven by the message
      header stamp; the publisher stamps with sim time.
- [ ] `dsp_filter_node.py:44` — `sample_rate_hz` matches the real
      `/joint_states` publish rate (assumed 200 Hz). Confirm with
      `ros2 topic hz /joint_states_noisy`; a mismatch shifts the cutoff.
- [ ] `dsp_filter_node.py:71` — header stamp passed through unchanged, so the
      filter's group delay shows as signal lag, not timestamp lag (the
      gauntlet's settling/RMS checks assume this).

### D. Launch & control loop

- [ ] `noise_injector_node.py:11`, `dsp_filter_node.py:12`,
      `waypoint_controller_node.py:13` — `rclpy` import + node runtime under a
      sourced ROS 2 Humble env (nothing below these lines has run in the cloud).
- [ ] `closed_loop.launch.py:17` — `ros2 launch`, node discovery, and parameter
      wiring work end to end.
- [ ] `waypoint_controller_node.py:103` — control update runs per incoming
      sample (loop rate = `/joint_states_filtered` publish rate); timing taken
      from the header stamp.

### E. Campaign runner (M4)

- [ ] `campaign/run_campaign.py` `launch_command` — the unfiltered condition's
      filter bypass (`filter_kind:=passthrough`, or controller `input_topic`
      override) exists and behaves as chosen in §4.
- [ ] `campaign/run_campaign.py` `run_one` — `ros2 launch` execution, run
      bounding (fixed steps vs. controller `DONE`), and the rosbag→CSV export
      producing `telemetry.csv` (`t,reference,measured[,noisy]`).

---

## 8. Record the 2–3 minute demo (REQ-S2R-300 / M4)

Once the loop closes and the campaign produces a table, capture the story
"noisy fails → filtered passes → the receipts":

1. **Setup shot (~20 s):** the block diagram (README) and one line —
   "Franka joint tracking, seeded noise, causal DSP filter, auto-graded."
2. **Unfiltered run (~45 s):** launch with the filter bypassed; show the arm
   jittering and `python -m gauntlet.cli` printing **FAILED** (RMS/settling/
   overshoot/attenuation red).
3. **Filtered run (~45 s):** same seed, `filter_kind:=iir`; show smooth
   tracking and the gauntlet printing **PASSED**.
4. **The receipts (~30 s):** scroll `evidence/results_table.md` — the pass-rate
   and RMS deltas over the 20+20 sweep — and open one `run-*.md` compliance
   report.

Record at 1080p, keep it under 3 minutes, save to `media/`, and link it from the
README "Public demos" section. Note the exact commands on screen so a viewer
could reproduce them.
