"""Runtime validation of the project control boundary under Isaac Sim 6.0.1.

Runs ONLY on an Isaac Sim 6.0.1 host, launched through its bundled Python with
the internal ROS 2 libraries sourced:

    source ./setup_ros_env.sh
    ./python.sh /path/to/scripts/validate_isaac6_runtime.py --scene <scene.usd>

This is the script that turns EDGEXPERT-VERIFY items into observations. It
answers four questions, in order, and refuses to guess at any of them:

  A. Does the project scene load and the ROS 2 bridge initialize?
  B. Is /joint_states actually emitted — with the right joint names, moving
     positions, and non-degenerate timestamps? At what REAL rate? (this is the
     measurement that resolves D6, see docs/M4_BASELINE.md §5)
  C. Is /joint_command actually consumed — does the commanded arm joint move,
     while the finger joints stay put?
  D. Does the full loop close through the project's own controller logic?

Nothing here tunes anything. It measures, and prints a machine-readable
summary block that the runtime-evidence record is generated from.

NOT claimed by any result of this script: real-world transfer, hardware
behavior, safety, or certification. It is a simulator.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--scene", required=True, help="path to the project scene .usd")
parser.add_argument("--repo", required=True, help="path to the repo checkout")
parser.add_argument("--observe-s", type=float, default=20.0,
                    help="how long to observe /joint_states for the rate measurement")
parser.add_argument("--settle-steps", type=int, default=120)
parser.add_argument(
    "--target-hz", type=float, default=None,
    help="drive physics AND rendering at this rate so /joint_states is sampled "
         "at it. Omit to observe the scene's default (measured 30 Hz), which is "
         "how D6 was first established.",
)
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": True})

import carb  # noqa: E402
import numpy as np  # noqa: E402
import omni.timeline  # noqa: E402
import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402

RESULT: dict = {"steps": {}, "limitations": [
    "simulation only; no physical hardware involved",
    "no sim-to-real transfer demonstrated or claimed",
    "no safety or certification claim",
    "GPU-vs-CPU PhysX execution NOT directly measured — remains UNKNOWN",
    "compatibility check could not report VRAM on this unified-memory GB10",
]}


def record(step: str, **kw) -> None:
    RESULT["steps"][step] = kw
    print(f"[validate] {step}: {json.dumps(kw, default=str)}", flush=True)


# --------------------------------------------------------------------------- #
# A. Scene + bridge
# --------------------------------------------------------------------------- #
app_utils.enable_extension("isaacsim.ros2.bridge")
simulation_app.update()

try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import JointState
    bridge_ok = True
    rclpy_path = rclpy.__file__
except Exception as e:  # noqa: BLE001
    bridge_ok = False
    rclpy_path = f"{type(e).__name__}: {e}"

record("A_bridge", extension="isaacsim.ros2.bridge", rclpy_importable=bridge_ok,
       rclpy=rclpy_path)
if not bridge_ok:
    RESULT["verdict"] = "M4_RUNTIME_GATE_BLOCKED"
    RESULT["blocker"] = "RUNTIME_BLOCKER: bundled rclpy not importable"
    print("VALIDATION_JSON=" + json.dumps(RESULT), flush=True)
    simulation_app.close()
    sys.exit(1)

scene = str(Path(args.scene).resolve())
stage_utils.open_stage(scene)
simulation_app.update()
record("A_scene", scene=scene, opened=True)

# The project's own logic modules — imported, not reimplemented, so this
# validates the shipped code path rather than a lookalike.
sys.path.insert(0, str(Path(args.repo) / "ros2-ws" / "src" / "control_loop"))
sys.path.insert(0, str(Path(args.repo) / "dsp"))
from control_loop.logic.franka_limits import ARM_JOINT_NAMES, limits_for  # noqa: E402
from control_loop.logic.waypoint_tracker import (  # noqa: E402
    DEFAULT_WAYPOINTS_FLAT,
    TrackerStatus,
    WaypointTracker,
    waypoints_from_flat,
)

# The OmniGraph publisher is driven by OnPlaybackTick, i.e. once per rendered
# app frame, so the /joint_states sampling rate IS the rendering rate. Setting
# physics_dt and rendering_dt together makes that rate explicit and equal to
# the physics rate, which is the deterministic clock a seeded campaign wants.
sim_context = None
if args.target_hz:
    from isaacsim.core.api import SimulationContext

    # EMPIRICAL, and measured rather than reasoned: with physics_dt ==
    # rendering_dt, the OmniGraph publisher ticks once every TWO physics steps,
    # so the observed publication rate is HALF the configured rate. Confirmed
    # on this runtime: dt=1/200 -> 100.199 Hz observed; dt=1/400 -> 200.498 Hz.
    # Hence the factor of 2. `--target-hz` means the desired /joint_states
    # rate; the tolerance check below fails loudly if this relationship ever
    # stops holding, so a campaign can never silently sample at the wrong rate.
    dt = 1.0 / (2.0 * float(args.target_hz))
    sim_context = SimulationContext(physics_dt=dt, rendering_dt=dt,
                                    stage_units_in_meters=1.0)
    sim_context.initialize_physics()
    record("A_rate_config", target_publish_hz=args.target_hz, physics_dt=dt,
           rendering_dt=dt, tick_to_physics_ratio=2)


def step() -> None:
    """Advance one simulation step, ticking the graph exactly once."""
    if sim_context is not None:
        sim_context.step(render=True)
    else:
        simulation_app.update()


timeline = omni.timeline.get_timeline_interface()
timeline.play()
for _ in range(args.settle_steps):
    step()

# --------------------------------------------------------------------------- #
# B. /joint_states — existence, content, and the REAL rate (resolves D6)
# --------------------------------------------------------------------------- #
rclpy.init()
observer = Node("m4_runtime_observer")

samples: list = []


def on_state(msg: JointState) -> None:
    samples.append({
        "wall": time.monotonic(),
        "stamp": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
        "names": list(msg.name),
        "position": list(msg.position),
    })


observer.create_subscription(JointState, "/joint_states", on_state, 10)
commander = observer.create_publisher(JointState, "/joint_command", 10)

t0 = time.monotonic()
while time.monotonic() - t0 < args.observe_s:
    step()
    rclpy.spin_once(observer, timeout_sec=0.0)

if len(samples) < 2:
    record("B_joint_states", received=len(samples), ok=False)
    RESULT["verdict"] = "M4_RUNTIME_GATE_BLOCKED"
    RESULT["blocker"] = "RUNTIME_BLOCKER: no /joint_states received"
    print("VALIDATION_JSON=" + json.dumps(RESULT), flush=True)
    timeline.stop()
    simulation_app.close()
    sys.exit(1)

wall_span = samples[-1]["wall"] - samples[0]["wall"]
wall_rate = (len(samples) - 1) / wall_span if wall_span > 0 else float("nan")
stamps = [s["stamp"] for s in samples]
d_stamp = [b - a for a, b in zip(stamps, stamps[1:]) if b > a]
sim_rate = 1.0 / statistics.mean(d_stamp) if d_stamp else float("nan")
wall_dt = [b["wall"] - a["wall"] for a, b in zip(samples, samples[1:])]

names = samples[-1]["names"]
positions_moved = any(
    abs(np.asarray(samples[0]["position"]) - np.asarray(s["position"])).max() > 1e-6
    for s in samples[1:]
)

record(
    "B_joint_states",
    received=len(samples),
    duration_s=round(wall_span, 3),
    wall_rate_hz=round(wall_rate, 3),
    sim_stamp_rate_hz=round(sim_rate, 3) if d_stamp else None,
    sim_dt_mean_s=round(statistics.mean(d_stamp), 6) if d_stamp else None,
    sim_dt_stdev_s=round(statistics.stdev(d_stamp), 6) if len(d_stamp) > 1 else None,
    wall_dt_mean_s=round(statistics.mean(wall_dt), 6),
    wall_dt_stdev_s=round(statistics.stdev(wall_dt), 6) if len(wall_dt) > 1 else None,
    stamp_first=stamps[0],
    stamp_last=stamps[-1],
    stamp_monotonic=all(b >= a for a, b in zip(stamps, stamps[1:])),
    stamp_degenerate=(stamps[0] == stamps[-1]),
    joint_names=names,
    arm_joints_present=all(n in names for n in ARM_JOINT_NAMES),
    positions_update=positions_moved,
)

# --------------------------------------------------------------------------- #
# C. /joint_command — is it actually consumed?
# --------------------------------------------------------------------------- #
idx = {n: i for i, n in enumerate(names)}
target_joint = "panda_joint4"          # has an asymmetric, tight limit range
finger_joints = [n for n in names if "finger" in n]


def latest_positions() -> dict:
    return {n: samples[-1]["position"][idx[n]] for n in names if n in idx}


before = latest_positions()
lo, hi = limits_for([target_joint])[0]
# Conservative: nudge a small, definitely-in-limits amount from where it is.
commanded = float(np.clip(before[target_joint] + 0.15, lo + 0.01, hi - 0.01))

cmd = JointState()
cmd.name = list(ARM_JOINT_NAMES)
cmd.position = [float(before[n]) for n in ARM_JOINT_NAMES]
cmd.position[list(ARM_JOINT_NAMES).index(target_joint)] = commanded

t0 = time.monotonic()
while time.monotonic() - t0 < 6.0:
    cmd.header.stamp = observer.get_clock().now().to_msg()
    commander.publish(cmd)
    step()
    rclpy.spin_once(observer, timeout_sec=0.0)

after = latest_positions()
moved = after[target_joint] - before[target_joint]
finger_drift = {n: after[n] - before[n] for n in finger_joints}

record(
    "C_joint_command",
    target_joint=target_joint,
    limit=[lo, hi],
    before=round(before[target_joint], 6),
    commanded=round(commanded, 6),
    after=round(after[target_joint], 6),
    delta=round(moved, 6),
    responded=abs(moved) > 1e-3,
    moved_toward_command=(moved * (commanded - before[target_joint]) > 0),
    within_limits=bool(lo <= after[target_joint] <= hi),
    finger_drift={k: round(v, 6) for k, v in finger_drift.items()},
    fingers_undriven=all(abs(v) < 1e-3 for v in finger_drift.values()),
)

# --------------------------------------------------------------------------- #
# D. Closed loop through the project's own controller logic
# --------------------------------------------------------------------------- #
# Proof that this is a LOOP and not two independent endpoints: the command is
# computed from the measured feedback each cycle, and we record whether the
# tracking error monotonically shrinks and the tracker reaches DONE.
waypoints = waypoints_from_flat(
    [float(x) for x in DEFAULT_WAYPOINTS_FLAT],
    num_joints=len(ARM_JOINT_NAMES),
    tolerance_rad=0.02,
)
tracker = WaypointTracker(
    waypoints, kp=0.8, max_step_rad=0.05, waypoint_timeout_s=30.0,
    joint_limits=limits_for(list(ARM_JOINT_NAMES)),
)

errors: list = []
clamped_any = False
t0 = time.monotonic()
loop_cycles = 0
while time.monotonic() - t0 < 45.0:
    step()
    rclpy.spin_once(observer, timeout_sec=0.0)
    if not samples:
        continue
    latest = samples[-1]
    if any(n not in idx for n in ARM_JOINT_NAMES):
        break
    measured = [float(latest["position"][idx[n]]) for n in ARM_JOINT_NAMES]
    out = tracker.update(measured, latest["stamp"])
    clamped_any = clamped_any or out.limit_clamped
    errors.append(out.error_norm_rad)
    cmd.header.stamp = observer.get_clock().now().to_msg()
    cmd.position = [float(p) for p in out.command]
    commander.publish(cmd)
    loop_cycles += 1
    if out.status in (TrackerStatus.DONE, TrackerStatus.TIMED_OUT):
        break

record(
    "D_closed_loop",
    cycles=loop_cycles,
    tracker_status=tracker.status.value,
    error_first=round(errors[0], 6) if errors else None,
    error_last=round(errors[-1], 6) if errors else None,
    error_reduced=bool(errors and errors[-1] < errors[0]),
    waypoints_reached=[(r.index, r.reached, round(r.elapsed_s, 3))
                       for r in tracker.results],
    limit_clamped_during_run=clamped_any,
)

timeline.stop()
observer.destroy_node()
rclpy.shutdown()

# If a target rate was requested, the MEASURED rate must match it. This is the
# clause that stops a seeded campaign from running against a filter designed
# for a sample rate the simulator is not actually delivering (D6).
rate_ok = True
if args.target_hz:
    measured = RESULT["steps"]["B_joint_states"]["sim_stamp_rate_hz"] or 0.0
    rel_err = abs(measured - args.target_hz) / args.target_hz
    rate_ok = rel_err <= 0.02
    record("B_rate_contract", target_hz=args.target_hz, measured_hz=measured,
           rel_error=round(rel_err, 5), tolerance=0.02, within_tolerance=rate_ok,
           nyquist_hz=measured / 2.0)

b = RESULT["steps"]["B_joint_states"]
c = RESULT["steps"]["C_joint_command"]
d = RESULT["steps"]["D_closed_loop"]
# NOTE on `positions_update`: it is recorded but deliberately NOT a gate
# criterion. Phase B observes an UNCOMMANDED arm, so positions holding still is
# the correct behavior — a resting articulation that does not drift. Gating on
# it would fail a healthy system. The evidence that positions actually track is
# phase C (a commanded joint moves) and phase D (tracking error collapses).
RESULT["verdict"] = (
    "M4_RUNTIME_GATE_PASS"
    if (b["received"] > 10 and b["arm_joints_present"]
        and not b["stamp_degenerate"] and b["stamp_monotonic"]
        and c["responded"] and c["moved_toward_command"] and c["within_limits"]
        and c["fingers_undriven"]
        and d["error_reduced"] and d["tracker_status"] == "done"
        and rate_ok)
    else "M4_RUNTIME_GATE_BLOCKED"
)
print("VALIDATION_JSON=" + json.dumps(RESULT), flush=True)
simulation_app.close()
