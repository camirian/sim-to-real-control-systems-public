"""Execute the preregistered filtered-vs-unfiltered campaign on an Isaac Sim host.

The committed campaign evidence was produced by this script on exactly one
build: `6.0.1-rc.7+release.42383.32955d8d.gl`, a release candidate. Isaac Sim
6.0.1 GA is a distinct later release; running this script on GA is a new
reproduction attempt, not a replay of the recorded campaign.

REQ-S2R-102, Issue #9. Runs ONLY on an Isaac Sim 6.x host, through its
bundled Python, with the internal ROS 2 libraries sourced:

    source ~/isaacsim-6.0.1/setup_ros_env.sh
    cd ~/isaacsim-6.0.1
    ./python.sh <repo>/scripts/run_campaign_isaac.py \
        --scene <repo>/scenes/franka_ros2_bridge_scene.usd \
        --repo <repo> --manifest <repo>/campaign/manifests/<id>.json \
        --logs-root <out>

This is `scripts/validate_isaac6_runtime.py` phase D — the loop that was already
proven to close through the project's own WaypointTracker — extended with the
three things a campaign needs and a validation run does not: a seeded
disturbance on the feedback path, a filter stage in front of the controller, and
telemetry capture. The control path itself is unchanged and still runs the
shipped project modules rather than lookalikes:

    Isaac articulation
      -> /joint_states                        (Isaac OmniGraph publisher)
      -> JointStateNoiseModel.apply(seed)     (control_loop.logic.noise_model)
      -> FilterStage.process()                (control_loop.logic.filter_stage;
                                               iir | passthrough)
      -> WaypointTracker.update()             (control_loop.logic.waypoint_tracker)
      -> /joint_command                       (Isaac OmniGraph subscriber)
      -> Isaac articulation

Nothing here is synthesized. Every row of every telemetry.csv is produced by a
simulation step that actually happened. If a run cannot meet the frozen
contract it is written out as invalid with its exact reason — never dropped,
never replaced, never quietly retried.

NOT claimed by any result of this script: real-world transfer, hardware
behavior, safety, or certification. It is a simulator.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--scene", required=True)
parser.add_argument("--repo", required=True)
parser.add_argument("--manifest", required=True, help="frozen campaign manifest")
parser.add_argument("--logs-root", required=True)
parser.add_argument("--settle-steps", type=int, default=200)
parser.add_argument("--preflight-samples", type=int, default=600)
parser.add_argument(
    "--only", nargs="*", default=None,
    help="run only these run ids (smoke/pilot use; the full campaign passes none)",
)
parser.add_argument(
    "--pilot-seed", type=int, default=None,
    help="run a single throwaway PILOT pair at this seed instead of the "
         "campaign. Pilot seeds must not be campaign seeds; pilot output is "
         "written under logs-root/pilot and is never campaign evidence.",
)
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": True})

import numpy as np  # noqa: E402
import omni.timeline  # noqa: E402
import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
import isaacsim.core.experimental.utils.stage as stage_utils  # noqa: E402

app_utils.enable_extension("isaacsim.ros2.bridge")
simulation_app.update()

import rclpy  # noqa: E402
from sensor_msgs.msg import JointState  # noqa: E402

REPO = Path(args.repo).resolve()
sys.path.insert(0, str(REPO / "ros2-ws" / "src" / "control_loop"))
sys.path.insert(0, str(REPO / "dsp"))
sys.path.insert(0, str(REPO))

from control_loop.logic.franka_limits import ARM_JOINT_NAMES, limits_for  # noqa: E402
from control_loop.logic.filter_stage import FilterSpec, FilterStage  # noqa: E402
from control_loop.logic.noise_model import JointStateNoiseModel, NoiseProfile  # noqa: E402
from control_loop.logic.sampling import assert_campaign_sampling_valid  # noqa: E402
from control_loop.logic.waypoint_tracker import (  # noqa: E402
    TrackerStatus,
    WaypointTracker,
    waypoints_from_flat,
)
from campaign.manifest import (  # noqa: E402
    file_sha256,
    load_manifest,
    sampling_rate_valid,
)
from campaign.raw_evidence import (  # noqa: E402
    STATUS_FAILED,
    STATUS_INVALID,
    STATUS_VALID,
    build_raw_packet,
    integrity_index,
    rate_stats,
    summarize_signals,
    write_raw_packet,
)

MANIFEST = load_manifest(args.manifest)
LOGS_ROOT = Path(args.logs_root).resolve()
ARM = list(ARM_JOINT_NAMES)
N_ARM = len(ARM)

RC = MANIFEST["run_contract"]
START_POSE = [float(x) for x in RC["start_pose_rad"]]
RESET_TOL = float(RC["reset_tolerance_rad"])
RESET_MAX_STEPS = int(RC["reset_max_steps"])
SAMPLES_PER_RUN = int(RC["samples_per_run"])
STEP_CAP = int(RC["step_cap_per_run"])
REP_JOINT = RC["representative_joint"]
REP_IDX = ARM.index(REP_JOINT)

SAMPLING = MANIFEST["sampling"]
TARGET_HZ = float(SAMPLING["sample_rate_hz"])
RATE_TOL = float(SAMPLING["rate_tolerance_frac"])
DIST = MANIFEST["disturbance"]
FILT = MANIFEST["filter"]
CTRL = MANIFEST["controller"]

# The guard the runtime slice committed, applied to the FROZEN manifest before
# a single run executes. A manifest that would sample the 25 Hz disturbance
# below Nyquist only on paper never gets to produce numbers.
assert_campaign_sampling_valid(
    sample_rate_hz=TARGET_HZ,
    vibration_freq_hz=float(DIST["vibration_freq_hz"]),
    cutoff_hz=float(FILT["cutoff_hz"]),
)

LIMITS = limits_for(ARM)


def log(msg: str) -> None:
    print(f"[campaign] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# Simulation boot — physics and rendering driven together so the publication
# rate is the deterministic clock the campaign is preregistered against.
# --------------------------------------------------------------------------- #
stage_utils.open_stage(str(Path(args.scene).resolve()))
simulation_app.update()

from isaacsim.core.api import SimulationContext  # noqa: E402

# Measured, not reasoned: the OmniGraph publisher ticks once every TWO physics
# steps, so the delivered rate is half the configured rate (see D6 in
# docs/M4_RUNTIME_VALIDATION.md). Hence dt = 1/(2*target).
DT = 1.0 / (2.0 * TARGET_HZ)
sim_context = SimulationContext(physics_dt=DT, rendering_dt=DT,
                                stage_units_in_meters=1.0)
sim_context.initialize_physics()


def step() -> None:
    sim_context.step(render=True)


timeline = omni.timeline.get_timeline_interface()
timeline.play()
for _ in range(args.settle_steps):
    step()

rclpy.init()
node = rclpy.create_node("m4_campaign_driver")

_latest = {"stamp": None, "names": None, "position": None, "count": 0}


def on_state(msg: JointState) -> None:
    _latest["stamp"] = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
    _latest["names"] = list(msg.name)
    _latest["position"] = list(msg.position)
    _latest["count"] += 1


node.create_subscription(JointState, "/joint_states", on_state, 10)
commander = node.create_publisher(JointState, "/joint_command", 10)


def pump() -> None:
    step()
    rclpy.spin_once(node, timeout_sec=0.0)


def arm_positions():
    """Current arm joint positions, or None if no message has arrived yet."""
    names, pos = _latest["names"], _latest["position"]
    if not names or not pos:
        return None
    idx = {n: i for i, n in enumerate(names)}
    if any(n not in idx for n in ARM):
        return None
    return [float(pos[idx[n]]) for n in ARM]


def publish(positions) -> None:
    msg = JointState()
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.name = list(ARM)
    msg.position = [float(p) for p in positions]
    commander.publish(msg)


# --------------------------------------------------------------------------- #
# Preflight: prove the boundary before spending 40 runs against it.
# --------------------------------------------------------------------------- #
def preflight() -> dict:
    for _ in range(200):
        pump()
        if arm_positions() is not None:
            break
    if arm_positions() is None:
        raise RuntimeError("PREFLIGHT: no /joint_states received")

    stamps, seen = [], None
    guard = 0
    while len(stamps) < args.preflight_samples and guard < args.preflight_samples * 8:
        pump()
        guard += 1
        s = _latest["stamp"]
        if s is not None and (seen is None or s > seen):
            seen = s
            stamps.append(s)
    stats = rate_stats(stamps)
    ok = sampling_rate_valid(stats["measured_hz"], TARGET_HZ, RATE_TOL)

    # One cheap, non-blocking observation of the PhysX execution device. It is
    # recorded because it is part of the runtime identity, not tuned: changing
    # CPU/GPU dynamics to chase speed would change the experiment.
    physx = {"simulation_device": "unknown", "gpu_dynamics": "unknown"}
    try:
        from isaacsim.core.simulation_manager import SimulationManager
        physx["simulation_device"] = str(SimulationManager.get_physics_sim_device())
    except Exception as e:  # noqa: BLE001
        physx["simulation_device"] = f"unavailable: {type(e).__name__}: {e}"
    try:
        from pxr import PhysxSchema
        import isaacsim.core.experimental.utils.stage as _st
        stage = _st.get_current_stage()
        found = None
        for prim in stage.Traverse():
            if prim.HasAPI(PhysxSchema.PhysxSceneAPI):
                api = PhysxSchema.PhysxSceneAPI(prim)
                attr = api.GetEnableGPUDynamicsAttr()
                found = bool(attr.Get()) if attr and attr.HasAuthoredValue() else None
                physx["physx_scene_prim"] = str(prim.GetPath())
                break
        physx["gpu_dynamics"] = found if found is not None else "unauthored/default"
    except Exception as e:  # noqa: BLE001
        physx["gpu_dynamics"] = f"unavailable: {type(e).__name__}: {e}"

    log(f"preflight rate {stats['measured_hz']} Hz over {stats['n_samples']} "
        f"samples, within_tolerance={ok}")
    log(f"preflight physx {json.dumps(physx)}")
    return {"rate": stats, "within_tolerance": ok, "physx": physx,
            "joint_names": _latest["names"]}


# --------------------------------------------------------------------------- #
# Per-run reset: return the articulation to the declared initial state and
# PROVE it, rather than assuming the previous run left things tidy.
# --------------------------------------------------------------------------- #
def reset_to_start() -> dict:
    steps = 0
    err = float("inf")
    while steps < RESET_MAX_STEPS:
        publish(START_POSE)
        pump()
        steps += 1
        pos = arm_positions()
        if pos is None:
            continue
        err = max(abs(a - b) for a, b in zip(pos, START_POSE))
        if err <= RESET_TOL:
            # Hold at the start pose briefly so the articulation is at rest,
            # not merely passing through the tolerance band.
            for _ in range(100):
                publish(START_POSE)
                pump()
                steps += 1
            pos = arm_positions()
            err = max(abs(a - b) for a, b in zip(pos, START_POSE))
            break
    achieved = err <= RESET_TOL
    return {
        "target_pose_rad": START_POSE,
        "achieved": bool(achieved),
        "final_error_rad": float(err),
        "tolerance_rad": RESET_TOL,
        "steps_used": steps,
        "max_steps": RESET_MAX_STEPS,
        "final_pose_rad": arm_positions(),
    }


# --------------------------------------------------------------------------- #
# One campaign run.
# --------------------------------------------------------------------------- #
def run_one(run_id: str, condition: str, seed: int, position: int,
            out_root: Path) -> dict:
    log(f"--- {run_id} (position {position}, seed {seed}, {condition}) ---")
    out_dir = out_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Independence: every stateful object is CONSTRUCTED here, per run. Nothing
    # is carried across runs and re-zeroed, because "we remembered to reset it"
    # is a weaker guarantee than "it did not exist a moment ago".
    reset = reset_to_start()
    start_pose_actual = arm_positions()

    noise = JointStateNoiseModel(
        NoiseProfile(
            seed=int(seed),
            awgn_sigma=float(DIST["awgn_sigma_rad"]),
            vibration_amplitude=float(DIST["vibration_amplitude_rad"]),
            vibration_freq_hz=float(DIST["vibration_freq_hz"]),
            vibration_phase_rad=float(DIST["vibration_phase_rad"]),
        ),
        num_joints=N_ARM,
    )
    spec = FilterSpec(
        kind=FILT["filtered_kind"] if condition == "filtered" else FILT["unfiltered_kind"],
        sample_rate_hz=float(FILT["sample_rate_hz"]),
        cutoff_hz=float(FILT["cutoff_hz"]),
        order=int(FILT["filtered_order"]),
    )
    filt = FilterStage(spec, num_joints=N_ARM)
    plan_waypoints = waypoints_from_flat(
        [float(x) for x in CTRL["waypoints_flat"]],
        num_joints=N_ARM,
        tolerance_rad=float(CTRL["tolerance_rad"]),
    )
    waypoints = [list(w.positions) for w in plan_waypoints]  # frozen plan
    tracker = WaypointTracker(
        plan_waypoints,
        kp=float(CTRL["kp"]),
        max_step_rad=float(CTRL["max_step_rad"]),
        waypoint_timeout_s=float(CTRL["waypoint_timeout_s"]),
        joint_limits=LIMITS,
    )

    # Equal time slice per waypoint across the fixed-length run: with 2
    # waypoints over 10 s, waypoint 0 is the reference for [0, 5) s and
    # waypoint 1 for [5, 10) s. Frozen in the manifest, not chosen per run.
    REF_SEGMENT_S = float(RC["run_duration_sim_s"]) / len(waypoints)
    t_run_start = None

    rows = []
    t_col, ref_col, meas_col, noisy_col, true_col, cmd_col = [], [], [], [], [], []
    clamp_cycles = 0
    status_transitions = []
    last_status = None
    last_stamp = None
    steps_used = 0
    cycles = 0

    while len(rows) < SAMPLES_PER_RUN and steps_used < STEP_CAP:
        pump()
        steps_used += 1
        stamp = _latest["stamp"]
        if stamp is None or (last_stamp is not None and stamp <= last_stamp):
            continue  # one control cycle per NEW published sample, exactly
        pos = arm_positions()
        if pos is None:
            continue
        last_stamp = stamp
        if t_run_start is None:
            t_run_start = stamp

        noisy = noise.apply(pos, stamp)
        estimate = filt.process(noisy)
        out = tracker.update(estimate, stamp)
        publish(out.command)
        cycles += 1

        if out.limit_clamped:
            clamp_cycles += 1
        if out.status.value != last_status:
            status_transitions.append(
                {"t": stamp, "status": out.status.value,
                 "active_waypoint": out.active_index}
            )
            last_status = out.status.value

        # `reference` is EXOGENOUS: a pure function of elapsed simulated time,
        # identical in both arms and for every seed. It is deliberately NOT the
        # tracker's active waypoint. An active-waypoint reference depends on
        # controller progress, which depends on the condition — so the two arms
        # would be scored against DIFFERENT reference signals, and a condition
        # that never advances past waypoint 0 would present a zero-span
        # reference (making overshoot_pct fall back to a span of 1.0 while the
        # converging arm is divided by 0.4). That confound was observed in the
        # pilot and removed here, before the campaign was frozen.
        elapsed = stamp - t_run_start
        wp_idx = min(int(elapsed / REF_SEGMENT_S), len(waypoints) - 1)
        reference = waypoints[wp_idx][REP_IDX]

        t_col.append(stamp)
        ref_col.append(reference)
        meas_col.append(float(estimate[REP_IDX]))
        noisy_col.append(float(noisy[REP_IDX]))
        true_col.append(float(pos[REP_IDX]))
        cmd_col.append(float(out.command[REP_IDX]))
        rows.append(True)

    # --- classify -------------------------------------------------------- #
    stats = rate_stats(t_col)
    rate_ok = sampling_rate_valid(stats["measured_hz"], TARGET_HZ, RATE_TOL)
    status, reason = STATUS_VALID, None
    if not reset["achieved"]:
        status, reason = STATUS_INVALID, (
            f"reset_failed: start pose not reached within {RESET_MAX_STEPS} "
            f"steps (final error {reset['final_error_rad']:.4f} rad > "
            f"{RESET_TOL} rad)"
        )
    elif len(t_col) < SAMPLES_PER_RUN:
        status, reason = STATUS_INVALID, (
            f"insufficient_samples: {len(t_col)}/{SAMPLES_PER_RUN} rows before "
            f"the {STEP_CAP}-step cap"
        )
    elif not stats["monotonic"]:
        status, reason = STATUS_INVALID, "non_monotonic_timestamps"
    elif not rate_ok:
        status, reason = STATUS_INVALID, (
            f"rate_out_of_tolerance: measured {stats['measured_hz']:.3f} Hz vs "
            f"target {TARGET_HZ} Hz (tolerance ±{RATE_TOL:.0%})"
        )

    # --- write the gauntlet run log -------------------------------------- #
    meta_path = out_dir / "run_meta.json"
    meta_path.write_text(
        json.dumps(
            {"run_id": run_id, "scenario": MANIFEST["scenario"], "seed": int(seed)},
            indent=2, sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    csv_path = out_dir / "telemetry.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t", "reference", "measured", "noisy"])
        for r in zip(t_col, ref_col, meas_col, noisy_col):
            w.writerow([repr(float(x)) for x in r])

    # The truth stream and the command stream are not part of the gauntlet's
    # single-signal contract, so they ride alongside rather than inside it.
    truth_path = out_dir / "truth.csv"
    with truth_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t", "true_position", "command"])
        for r in zip(t_col, true_col, cmd_col):
            w.writerow([repr(float(x)) for x in r])

    packet = build_raw_packet(
        run_id=run_id,
        condition=condition,
        seed=int(seed),
        scenario=MANIFEST["scenario"],
        campaign_id=MANIFEST["campaign_id"],
        campaign_version=int(MANIFEST["campaign_version"]),
        manifest_sha256=MANIFEST["manifest_sha256"],
        execution_position=int(position),
        status=status,
        failure_reason=reason,
        start_state={
            "declared_start_pose_rad": START_POSE,
            "actual_start_pose_rad": start_pose_actual,
            "joint_names": ARM,
            "joint_limits": [list(map(float, p)) for p in LIMITS],
        },
        reset=reset,
        rate={
            **stats,
            "target_hz": TARGET_HZ,
            "tolerance_frac": RATE_TOL,
            "within_tolerance": bool(rate_ok),
        },
        controller={
            "implementation": CTRL["implementation"],
            "filter_kind": spec.kind,
            "cycles": cycles,
            "steps_used": steps_used,
            "tracker_status": tracker.status.value,
            "status_transitions": status_transitions,
            "waypoints": waypoints,
            "waypoint_results": [
                {"index": r.index, "reached": bool(r.reached),
                 "elapsed_s": float(r.elapsed_s),
                 "final_error_rad": float(r.final_error_rad)}
                for r in tracker.results
            ],
            "limit_clamp_cycles": clamp_cycles,
            "limit_clamped_any": clamp_cycles > 0,
            "completion_reason": (
                "sample_target_reached" if len(t_col) >= SAMPLES_PER_RUN
                else "step_cap_reached"
            ),
        },
        signals_summary=summarize_signals(ref_col, meas_col, noisy_col,
                                          true_col, cmd_col),
        runtime={
            "isaac_build": MANIFEST["runtime"]["isaac_build"],
            "rmw": MANIFEST["runtime"]["rmw_implementation"],
            "ros_distro": MANIFEST["runtime"]["ros_distro"],
            "platform": MANIFEST["runtime"]["platform"],
            "physics_dt_s": DT,
            "representative_joint": REP_JOINT,
        },
        files={
            "run_meta.json": file_sha256(meta_path),
            "telemetry.csv": file_sha256(csv_path),
            "truth.csv": file_sha256(truth_path),
        },
    )
    write_raw_packet(packet, out_dir / "raw_evidence.json")
    log(f"{run_id}: status={status} cycles={cycles} rows={len(t_col)} "
        f"rate={stats['measured_hz']} tracker={tracker.status.value} "
        f"clamped={clamp_cycles}"
        + (f" reason={reason}" if reason else ""))
    return packet


# --------------------------------------------------------------------------- #
# Campaign
# --------------------------------------------------------------------------- #
def main() -> int:
    pf = preflight()
    if not pf["within_tolerance"]:
        log("PREFLIGHT FAILED: sampling boundary is outside the frozen "
            "tolerance. Refusing to start the campaign.")
        (LOGS_ROOT).mkdir(parents=True, exist_ok=True)
        (LOGS_ROOT / "preflight.json").write_text(
            json.dumps({"preflight": pf, "verdict": "CAMPAIGN_BLOCKED_RATE"},
                       indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 3

    if args.pilot_seed is not None:
        seed = int(args.pilot_seed)
        if seed in MANIFEST["design"]["seeds"]:
            raise SystemExit(f"pilot seed {seed} is a campaign seed; pick another")
        out_root = LOGS_ROOT / "pilot"
        plan = [
            {"position": i, "run_id": f"{c}-{seed:04d}", "condition": c, "seed": seed}
            for i, c in enumerate(("filtered", "unfiltered"))
        ]
    else:
        out_root = LOGS_ROOT
        plan = list(MANIFEST["design"]["execution_plan"])
        if args.only:
            plan = [p for p in plan if p["run_id"] in set(args.only)]

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "preflight.json").write_text(
        json.dumps({"preflight": pf}, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    packets, hard_failures = [], []
    t0 = time.monotonic()
    for entry in plan:
        try:
            packets.append(
                run_one(entry["run_id"], entry["condition"], entry["seed"],
                        entry["position"], out_root)
            )
        except Exception as e:  # noqa: BLE001
            # A harness error is an OBSERVATION about this run, not a reason to
            # pretend the run was never scheduled.
            tb = traceback.format_exc()
            log(f"HARNESS ERROR on {entry['run_id']}: {e}")
            log(tb)
            hard_failures.append(
                {"run_id": entry["run_id"], "condition": entry["condition"],
                 "seed": entry["seed"], "position": entry["position"],
                 "status": STATUS_FAILED,
                 "failure_reason": f"harness_error: {type(e).__name__}: {e}",
                 "traceback": tb}
            )

    elapsed = time.monotonic() - t0
    summary = {
        "campaign_id": MANIFEST["campaign_id"],
        "campaign_version": MANIFEST["campaign_version"],
        "manifest_sha256": MANIFEST["manifest_sha256"],
        "scheduled": len(plan),
        "attempted": len(packets) + len(hard_failures),
        "valid": sum(1 for p in packets if p["status"] == STATUS_VALID),
        "invalid": sum(1 for p in packets if p["status"] == STATUS_INVALID),
        "failed": len(hard_failures),
        "by_condition": {
            c: {
                "scheduled": sum(1 for e in plan if e["condition"] == c),
                "valid": sum(1 for p in packets
                             if p["condition"] == c and p["status"] == STATUS_VALID),
                "invalid": sum(1 for p in packets
                               if p["condition"] == c and p["status"] == STATUS_INVALID),
            }
            for c in ("filtered", "unfiltered")
        },
        "hard_failures": hard_failures,
        "preflight": pf,
        "wall_elapsed_s": round(elapsed, 1),
        "integrity_index": integrity_index(packets),
    }
    (out_root / "campaign_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    log(f"DONE scheduled={summary['scheduled']} valid={summary['valid']} "
        f"invalid={summary['invalid']} failed={summary['failed']} "
        f"in {elapsed:.0f}s")
    return 0


try:
    rc = main()
finally:
    timeline.stop()
    try:
        node.destroy_node()
        rclpy.shutdown()
    except Exception:  # noqa: BLE001
        pass
    simulation_app.close()

sys.exit(rc)
