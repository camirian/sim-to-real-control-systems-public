"""Franka Panda arm joint limits, read out of the Isaac asset (REQ-S2R-004).

Pure Python/NumPy — no ROS, no Isaac, no network.

Provenance, not folklore. These bounds were extracted from the USD asset the
scene actually references:

    scenes/franka_ros2_bridge_scene.usd  ->  references  ->
    https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.5/Isaac/Robots/Franka/franka.usd

by reading ``physics:lowerLimit`` / ``physics:upperLimit`` off each
``PhysicsRevoluteJoint`` prim (``/panda/panda_linkN/panda_jointN+1``).
``scripts/extract_franka_limits.py`` re-derives this table from that asset and
is the check that this file has not drifted from it.

Units. USD authors revolute-joint limits in **degrees**; ROS
``sensor_msgs/JointState.position`` and this repo's controller work in
**radians**. The degree values are stored verbatim as they appear in the asset
and converted once, here, so the conversion happens in exactly one place.

Corroboration: converted to radians these reproduce the published Franka
Emika Panda limits (e.g. joint1 ±2.8973 rad, joint4 [-3.0718, -0.0698] rad),
which is independent evidence that the asset table is the real robot's and not
an Isaac-specific approximation.

Scope. These are the **simulated articulation's** position limits. Enforcing
them keeps the controller from commanding a pose the articulation cannot hold
and from generating physically meaningless evidence. That is all it is. It is
NOT a safety function, not a certified limit check, and says nothing about a
physical robot — this repo has no hardware in the loop (README non-goals).
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

# The 7 controlled arm joints, in command order. Lives here rather than in the
# rclpy wrapper so the joint identity is importable without ROS — CI has no
# rclpy by design (AGENTS.md §2), and tests need to reason about these names.
# The 2 finger joints (panda_finger_joint1/2) are deliberately excluded: the
# controller does not command the gripper.
ARM_JOINT_NAMES: Tuple[str, ...] = (
    "panda_joint1",
    "panda_joint2",
    "panda_joint3",
    "panda_joint4",
    "panda_joint5",
    "panda_joint6",
    "panda_joint7",
)

# joint name -> (lower_deg, upper_deg), verbatim from the referenced asset.
FRANKA_JOINT_LIMITS_DEG: Dict[str, Tuple[float, float]] = {
    "panda_joint1": (-166.00306701660156, 166.00306701660156),
    "panda_joint2": (-101.0009994506836, 101.0009994506836),
    "panda_joint3": (-166.00306701660156, 166.00306701660156),
    "panda_joint4": (-176.0011749267578, -3.9992451667785645),
    "panda_joint5": (-166.00306701660156, 166.00306701660156),
    "panda_joint6": (-1.0026761293411255, 215.00241088867188),
    "panda_joint7": (-166.00306701660156, 166.00306701660156),
}

FRANKA_JOINT_LIMITS_RAD: Dict[str, Tuple[float, float]] = {
    name: (math.radians(lo), math.radians(hi))
    for name, (lo, hi) in FRANKA_JOINT_LIMITS_DEG.items()
}


def limits_for(joint_names: Sequence[str]) -> List[Tuple[float, float]]:
    """Return ``(lower_rad, upper_rad)`` per name, in the order given.

    Raises for an unknown joint rather than silently returning an unbounded
    range: an unrecognized joint means the caller is driving something this
    table does not describe, and a permissive fallback would hide that.
    """
    out: List[Tuple[float, float]] = []
    for name in joint_names:
        if name not in FRANKA_JOINT_LIMITS_RAD:
            raise KeyError(
                f"no limit table entry for joint {name!r}; known joints: "
                f"{sorted(FRANKA_JOINT_LIMITS_RAD)}"
            )
        out.append(FRANKA_JOINT_LIMITS_RAD[name])
    return out


def within_limits(joint_names: Sequence[str], positions: Sequence[float]) -> bool:
    """True when every position lies inside its joint's limits (inclusive)."""
    if len(joint_names) != len(positions):
        raise ValueError(
            f"{len(joint_names)} joint names vs {len(positions)} positions"
        )
    return all(
        lo <= float(p) <= hi
        for (lo, hi), p in zip(limits_for(joint_names), positions)
    )
