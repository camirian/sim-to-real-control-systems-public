#!/usr/bin/env python3
# File: scripts/run_franka_headless.py
# REQ-S2R-300 (partial); groundwork for REQ-S2R-005 (documented headless
# Isaac launch with the Franka scene). M1 Lane B.
#
# Loads scenes/franka_ros2_bridge_scene.usd (Franka + OmniGraph ROS 2
# joint-state publisher), steps physics headless for a fixed number of
# steps, then shuts down cleanly. Modeled on franka_wave.py.
#
# How to run (EdgeXpert only — Isaac Sim 4.5.0):
# 1. cd to your Isaac Sim root directory (e.g., ~/isaac-sim)
# 2. Run: ./python.sh /path/to/repo/scripts/run_franka_headless.py --steps 600
# 3. In a sourced ROS 2 Humble shell, verify:  ros2 topic echo /joint_states
#
# NOTE: this file has only been syntax-checked (python -m py_compile) in a
# cloud environment without Isaac Sim. Every runtime assumption is marked
# EDGEXPERT-VERIFY and must be confirmed on the EdgeXpert before this
# counts as done.

import argparse
from pathlib import Path

# Unified new-style entry point (Isaac Sim 4.5.0) — same as simple_scene.py,
# add_prims.py, and franka_wave.py after REQ-S2R-300 unification.
from isaacsim import SimulationApp

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENE_USD = REPO_ROOT / "scenes" / "franka_ros2_bridge_scene.usd"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Headless physics run of the Franka ROS 2 bridge scene."
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=600,
        help="Number of physics steps to run before shutting down "
        "(default: 600, i.e. 10 s at the default 60 Hz physics rate).",
    )
    parser.add_argument(
        "--scene",
        type=str,
        default=str(SCENE_USD),
        help="Path to the USD scene to load (default: %(default)s).",
    )
    return parser.parse_args()


args = parse_args()

scene_path = Path(args.scene)
if not scene_path.is_file():
    raise SystemExit(f"Scene file not found: {scene_path}")

# SimulationApp must be created before ANY omni.* / isaac import.
# EDGEXPERT-VERIFY: headless=True boots without a display on the EdgeXpert
# (no X/GL requirement for a physics-only run).
CONFIG = {"headless": True}
simulation_app = SimulationApp(CONFIG)

# Imports below must stay after SimulationApp() — omni.* modules only
# resolve once the app is initialized.
from omni.isaac.core import World  # noqa: E402
from omni.isaac.core.utils.extensions import enable_extension  # noqa: E402
from omni.isaac.core.utils.stage import open_stage  # noqa: E402

# The scene's OmniGraph publishes /joint_states through the ROS 2 bridge,
# which is not loaded by default in a headless app.
# EDGEXPERT-VERIFY: extension id for Isaac Sim 4.5.0 — expected
# "isaacsim.ros2.bridge" under the renamed extension scheme; if the 4.5
# install still ships the legacy id, use "omni.isaac.ros2_bridge".
# Also verify ROS 2 Humble env (RMW, ROS_DOMAIN_ID) is sourced before launch.
enable_extension("isaacsim.ros2.bridge")
simulation_app.update()

# EDGEXPERT-VERIFY: open_stage loads the saved scene (Franka articulation +
# OmniGraph publisher) and the graph survives being opened headless.
print(f"Loading scene: {scene_path}")
open_stage(str(scene_path))

# World wraps the opened stage; reset() initializes physics.
# EDGEXPERT-VERIFY: stage_units_in_meters matches how the USD was authored.
world = World(stage_units_in_meters=1.0)
world.reset()
print("Scene loaded and physics initialized. Stepping headless...")

step_count = 0
try:
    while simulation_app.is_running() and step_count < args.steps:
        # render=False: pure physics stepping, no viewport rendering.
        # EDGEXPERT-VERIFY: the OmniGraph ROS 2 joint-state publisher still
        # ticks on physics steps with render=False (some graph pipelines
        # tick on render events; if /joint_states stays silent, step with
        # render=True as a fallback and record which one works).
        world.step(render=False)
        step_count += 1
        if step_count % 120 == 0:
            print(f"  step {step_count}/{args.steps}")
finally:
    # Clean shutdown so a follow-up launch does not inherit a stale app.
    # EDGEXPERT-VERIFY: close() exits with code 0 headless (no hang).
    print(f"Completed {step_count} physics steps. Shutting down.")
    simulation_app.close()
