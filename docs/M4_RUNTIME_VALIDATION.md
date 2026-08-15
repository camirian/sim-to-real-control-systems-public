# M4 runtime validation — Isaac Sim 6.0.1 on GB10

The project control boundary, observed rather than assumed. Every number below
came from `scripts/validate_isaac6_runtime.py` running against the committed
project scene on a live simulator.

**Verdict: `M4_RUNTIME_GATE_PASS`** — with one measured result that materially
changes the experimental contract and blocks the campaign pending review (§6).

## 1. Runtime configuration

| Field | Value |
|---|---|
| Isaac Sim build | `6.0.1-rc.7+release.42383.32955d8d.gl` |
| OS | Ubuntu 24.04.4 LTS / DGX OS 7.5.0 (NVIDIA DGX Spark) |
| Architecture | `aarch64` |
| GPU | NVIDIA GB10 (122 GiB unified, `sm_121`) |
| Driver | 580.173.02 (Isaac minimum 535.161) |
| ROS distro | **jazzy**, from Isaac's *internal* libraries — no system ROS |
| ROS library source | `exts/isaacsim.ros2.core/jazzy/lib` (via `setup_ros_env.sh`) |
| `rclpy` | `exts/isaacsim.ros2.core/jazzy/rclpy/rclpy/__init__.py` (Omniverse build) |
| RMW | `rmw_fastrtps_cpp` |
| Extension enabled | `isaacsim.ros2.bridge` (5.1.2) |
| Project commit | `94b56c9` + this branch |
| Scene graph fingerprint | `graph_fingerprint()`, see `python -m scenes.scene_contract` |

**No system ROS 2 installation exists on this machine.** The bridge working
does not imply otherwise: no `apt`, no `sudo`, no Docker group change, no
system package was modified. Isaac Sim lives entirely in `~/isaacsim-6.0.1`.

Commands:

```bash
source ~/isaacsim-6.0.1/setup_ros_env.sh     # ROS_DISTRO=jazzy, RMW, LD_LIBRARY_PATH
cd ~/isaacsim-6.0.1
./python.sh <repo>/scripts/validate_isaac6_runtime.py \
    --scene <repo>/scenes/franka_ros2_bridge_scene.usd \
    --repo  <repo> --observe-s 30
```

## 2. Graph migration to 6.0.1

Node type tokens were established by instantiating each one against the live
registry, not read off a doc page. All five 4.5.0 tokens survived unchanged.
One new node is required:

| Node | Type | Ver |
|---|---|---|
| `read_joint_state` | `isaacsim.sensors.physics.IsaacReadJointState` | 1 |
| `read_sim_time` | `isaacsim.core.nodes.IsaacReadSimulationTime` | 1 |
| `ros2_publish_joint_state` | `isaacsim.ros2.bridge.ROS2PublishJointState` | 1 |
| `ros2_subscribe_joint_command` | `isaacsim.ros2.bridge.ROS2SubscribeJointState` | 2 |
| `articulation_controller` | `isaacsim.core.nodes.IsaacArticulationController` | 1 |
| `on_playback_tick` | `omni.graph.action.OnPlaybackTick` | 2 |

Two things the documentation did not give us, both found by running it:

1. The extension segment is **`isaacsim.sensors.physics`**, not
   `isaacsim.sensors.physics.nodes`. The `.nodes.` form does not resolve.
2. `stageMetersPerUnit` **must** be wired from the reader to the publisher.
   Leaving it unwired produces
   `Joint state from sensor: stageMetersPerUnit must be a positive finite value`
   and **zero messages on `/joint_states`** — a scene that looks healthy and
   publishes nothing. This is now a contract clause so it cannot recur.

The `/joint_command` → articulation path is unchanged from PR #10, and
`jointNames` remains wired so 7 arm commands cannot smear across the 9-DOF
articulation (proven in §4).

## 3. `/joint_states` proven live — and D6 resolved

Observation: **1434 messages over 29.866 s**.

| Measure | Value |
|---|---|
| Wall-clock rate | 47.98 Hz (mean Δ 20.8 ms, stdev 14.8 ms) |
| **Sim-time stamp rate** | **30.02 Hz** (mean Δ **33.31 ms**, stdev 0.62 ms) |
| Stamp range | 2.050 s → 49.783 s, monotonic, non-degenerate |
| Joint names | `panda_joint1..7`, `panda_finger_joint1/2` (9 DOF) |

The wall-clock rate is an artifact of headless stepping faster than real time
and is **not** the sampling boundary. The DSP-relevant rate is the sim-time
stamp spacing: **30 Hz**, and it is metronomic (stdev 0.62 ms).

This also settles the D4 question left open in PR #10: header stamps advance
and are non-degenerate, so the `ReadSimulationTime` wiring works and
`waypoint_timeout_s` can fire. The earlier "unwired publisher may stamp 0.0"
inference is retired — it was never asserted, and is now moot.

`positions_update: false` during this phase is **correct**: the arm is
uncommanded and at rest, and a resting articulation should not drift. Evidence
that positions track is §4 and §5.

## 4. `/joint_command` proven consumed

A single conservative in-limits command on `panda_joint4`:

| | value |
|---|---|
| Limits (from PR #10's asset-derived table) | `[-3.0718, -0.0698]` |
| Before | `-2.81` |
| Commanded | `-2.66` |
| After | `-2.66` (Δ `+0.15`, toward command) |
| Within limits | yes |
| Finger drift | `+0.0001` rad on both — undriven |

The subscriber receives, the articulation controller consumes, the correct
joint moves, and the fingers do not. That last one is the check that would
have caught a `jointNames` mis-wire.

## 5. Closed loop proven

The loop was closed through the project's **own** shipped logic —
`WaypointTracker` and `franka_limits` imported from `ros2-ws/src/control_loop`,
not reimplemented — computing each command from the measured feedback:

| | value |
|---|---|
| Cycles | 409 |
| Tracker status | `done` |
| Tracking error | `1.237` → `0.000` rad |
| Waypoints reached | `[0 @ 5.133 s, 1 @ 1.667 s]` (sim time) |
| Limit clamping during run | none |

This is a loop, not two independent endpoints: the command published each
cycle is a function of the `/joint_states` sample received that cycle, and the
error collapses to zero with both waypoints reaching their tolerance.

## 6. D6 disposition — measured, and it breaks the contract

**Assumed: `sample_rate_hz = 200.0`. Measured: `30.02 Hz`.** A factor of 6.67.

Classification: **`CONFIG_DEFECT`, observed.** Two consequences follow by
arithmetic, not opinion:

1. **The filter cutoff is wrong by 6.67×.** A 5 Hz cutoff specified at
   fs = 200 Hz is a normalized `Wn = 5/100 = 0.05`. Applied to a 30 Hz stream
   that is an effective cutoff of `0.05 × 15 = ` **0.75 Hz**, not 5 Hz.
2. **The injected vibration is above Nyquist.** Nyquist for 30 Hz sampling is
   15 Hz. The launch injects `vibration_freq_hz = 25.0`, which cannot be
   represented: it **aliases to `|30 − 25| = 5 Hz`** — landing exactly on the
   intended cutoff. The filtered-vs-unfiltered contrast the entire campaign
   rests on would be measuring an aliasing artifact.

Consequence (2) is why the campaign is **not** started. This is not a filter
that needs tuning; it is a sampling boundary that invalidates the stimulus
design. Tuning the filter to make the numbers look better would be exactly the
wrong move.

**The campaign contract must be frozen/reviewed before any seeded run.** The
two coherent resolutions are genuinely different experiments:

- **(a) Adopt the measured 30 Hz.** Set `sample_rate_hz = 30.0` and move the
  vibration below Nyquist (e.g. 10–12 Hz, preserving "well above a 5 Hz
  cutoff"). Honest, but it changes the stimulus the DSP work was designed and
  documented around.
- **(b) Raise the simulation's publish rate to 200 Hz.** Change the sampling
  boundary instead of the experiment, so the existing 5 Hz / 25 Hz / 200 Hz
  design holds as written. Preserves the documented contract; costs sim
  configuration work and needs re-measurement to confirm.

Choosing between these is an experimental-design decision, not an
implementation detail, so it is escalated rather than taken.

## 7. Limitations that survive this document

- Simulation only. **No physical hardware was involved and no sim-to-real
  transfer is demonstrated or claimed.**
- No safety, certification, compliance, or production-readiness claim. The
  joint-limit bound is a simulated articulation's command bound.
- **GPU-vs-CPU PhysX execution remains `UNKNOWN`** — not directly measured. No
  CPU-fallback warning was emitted, but absence of a warning is not a
  measurement.
- The compatibility check reported `GPU 0: VRAM [cannot be identified]` on this
  unified-memory GB10, so the 10 GB VRAM minimum was never actually evaluated.
- The scene still references the Isaac **4.5** Franka asset URL. It resolves
  and loads under 6.0.1, but the 6.0 asset root differs; this is unreconciled.
- One benign repeated warning: a DOF-type mismatch between USD and the physics
  tensor on the 9th DOF (gripper mimic joint). It does not affect the 7 arm
  joints.
- The 40-run campaign has **not** been started. No seeded runs, no evidence
  packets, no partial table.
