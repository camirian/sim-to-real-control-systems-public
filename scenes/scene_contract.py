"""The ROS 2 graph contract for the Franka scene (REQ-S2R-005 / M4).

Plain Python + ``usd-core`` (``pxr``). **No Isaac Sim, no ROS, no GPU** — this
module opens ``franka_ros2_bridge_scene.usd`` as data and asserts that the
OmniGraph wiring the closed loop depends on is actually present and connected.
It is the automated boundary check for the defect that kept M4 open: the scene
published joint states but nothing consumed ``/joint_command``, so
``waypoint_controller`` shouted into the void and the arm never moved.

What it can and cannot do
-------------------------
It checks the *scene-side* half of the contract — node types, topic names,
prim targets, and connections — statically. It cannot check that Isaac
instantiates those nodes, that the ROS 2 bridge extension loads, or that the
arm physically moves; those stay ``EDGEXPERT-VERIFY`` (docs/RUN_ON_EDGEXPERT.md
§7). What it does buy: the scene can never again silently regress to
publish-only, and the topic/joint-name contract with
``control_loop.waypoint_controller_node`` is pinned from both sides.

Node specifications are taken from the Isaac Sim **4.5.0** OGN reference (the
pinned version, README "Pinned versions"):

* ``ROS2PublishJointState`` — https://docs.isaacsim.omniverse.nvidia.com/4.5.0/py/source/extensions/isaacsim.ros2.bridge/docs/ogn/OgnROS2PublishJointState.html
* ``ROS2SubscribeJointState`` — https://docs.isaacsim.omniverse.nvidia.com/4.5.0/py/source/extensions/isaacsim.ros2.bridge/docs/ogn/OgnROS2SubscribeJointState.html
* ``IsaacArticulationController`` — https://docs.isaacsim.omniverse.nvidia.com/4.5.0/py/source/extensions/isaacsim.core.nodes/docs/ogn/OgnIsaacArticulationController.html
* canonical wiring — https://docs.isaacsim.omniverse.nvidia.com/4.5.0/ros2_tutorials/tutorial_ros2_manipulation.html

Units. ROS ``sensor_msgs/JointState.position`` is **radians** for revolute
joints, which is what the articulation controller consumes. USD's
``PhysicsRevoluteJoint`` limits in the referenced Franka asset are authored in
**degrees** — see :mod:`control_loop.logic.franka_limits`, which does the
conversion once and cites the asset.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

SCENE_FILENAME = "franka_ros2_bridge_scene.usd"

# --- Prim paths (authored by scripts/author_joint_command_graph.py) --------- #
GRAPH_PATH = "/World/ActionGraph"
TICK_PATH = f"{GRAPH_PATH}/on_playback_tick"
PUBLISHER_PATH = f"{GRAPH_PATH}/ros2_publish_joint_state"
SUBSCRIBER_PATH = f"{GRAPH_PATH}/ros2_subscribe_joint_command"
CONTROLLER_PATH = f"{GRAPH_PATH}/articulation_controller"
READ_SIM_TIME_PATH = f"{GRAPH_PATH}/read_sim_time"
READ_JOINT_STATE_PATH = f"{GRAPH_PATH}/read_joint_state"

# --- Node type tokens (Isaac Sim 6.0.1) ------------------------------------ #
# Verified against the LIVE 6.0.1 runtime by instantiating each type and
# dumping its ports, not read off a doc page. All five tokens carried over from
# 4.5.0 unchanged; the extension providing the ROS 2 ones was renamed
# (isaacsim.ros2.bridge -> isaacsim.ros2.nodes) but the node:type strings were
# not.
TICK_TYPE = "omni.graph.action.OnPlaybackTick"
PUBLISHER_TYPE = "isaacsim.ros2.bridge.ROS2PublishJointState"
SUBSCRIBER_TYPE = "isaacsim.ros2.bridge.ROS2SubscribeJointState"
CONTROLLER_TYPE = "isaacsim.core.nodes.IsaacArticulationController"
READ_SIM_TIME_TYPE = "isaacsim.core.nodes.IsaacReadSimulationTime"
# NOTE the extension segment: `isaacsim.sensors.physics`, NOT
# `isaacsim.sensors.physics.nodes`. The `.nodes.` form does not resolve —
# established by a failed instantiation against the live registry, which is
# why this constant is worth a comment.
READ_JOINT_STATE_TYPE = "isaacsim.sensors.physics.IsaacReadJointState"

# Isaac Sim 6.0 breaking change: the ROS 2 publishers no longer resolve USD
# prims internally. The joint-state publisher is fed by an upstream Isaac Read
# Joint State node instead of reading `inputs:targetPrim`. Each name below is
# an `outputs:<name>` on the reader wired to `inputs:<name>` on the publisher.
READ_JOINT_STATE_TO_PUBLISHER = (
    "jointNames",
    "jointPositions",
    "jointVelocities",
    "jointEfforts",
    "jointDofTypes",
    # Not optional, and not obvious. Leaving this unwired makes the publisher
    # fail at runtime with "stageMetersPerUnit must be a positive finite
    # value" and emit NOTHING on /joint_states — a silent-looking scene that
    # produces zero messages. Found by running it; it is in the contract so
    # nobody has to find it twice.
    "stageMetersPerUnit",
)

# --- The ROS 2 boundary the control_loop nodes bind to --------------------- #
# Both are authored EXPLICITLY rather than left to the node defaults
# ("joint_states" / "joint_command"). The defaults happen to be right, but an
# unauthored attribute is an invisible contract: this check would be asserting
# a default it does not control. Authored values are the contract.
STATE_TOPIC = "joint_states"  # -> /joint_states, consumed by noise_injector
COMMAND_TOPIC = "joint_command"  # <- /joint_command, from waypoint_controller

# The articulation the graph drives. The scene's /Franka prim references the
# Isaac 4.5 Franka asset; its 7 revolute arm joints are panda_joint1..7.
ROBOT_PRIM_PATH = "/Franka"


@dataclass(frozen=True)
class Violation:
    """One broken clause of the contract, with the fix that satisfies it."""

    where: str
    problem: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.where}: {self.problem}"


def _open_layer(scene_path):
    """Open the scene's root layer WITHOUT composing the stage.

    Deliberately ``Sdf.Layer``, not ``Usd.Stage``: the scene references the
    Franka asset over https, and composing a stage makes USD try to resolve
    that URL. On a machine without network access it emits resolver errors, and
    a check that behaves differently online and offline is not a check. Layer
    inspection is also the semantically correct question — the contract is
    about what *this repo's layer* authors, not what composition happens to
    yield from a remote asset that could change underneath it.

    A fresh clone can therefore validate the scene with no network at all.
    """
    from pxr import Sdf

    scene_path = Path(scene_path)
    if not scene_path.is_file():
        raise FileNotFoundError(f"scene not found: {scene_path}")
    layer = Sdf.Layer.FindOrOpen(str(scene_path))
    if layer is None:
        raise ValueError(f"not a readable USD layer: {scene_path}")
    return layer


def _attr(prim, name):
    """Fetch an attribute spec off an ``Sdf.PrimSpec`` (None if unauthored)."""
    if prim is None:
        return None
    return prim.attributes.get(name)


def _value(attr):
    """Authored value of an attribute spec, or None when it has none."""
    if attr is None or not attr.HasDefaultValue():
        return None
    return attr.default


def _connected_from(prim, input_name: str) -> List[str]:
    a = _attr(prim, input_name)
    if a is None:
        return []
    return [str(p) for p in a.connectionPathList.GetAddedOrExplicitItems()]


def check_scene(scene_path) -> List[Violation]:
    """Return every violated clause of the graph contract (empty == healthy)."""
    layer = _open_layer(scene_path)
    out: List[Violation] = []

    def prim_of(path: str, expected_type: str) -> Optional[object]:
        p = layer.GetPrimAtPath(path)
        if p is None:
            out.append(Violation(path, f"missing; expected {expected_type}"))
            return None
        actual_v = _value(_attr(p, "node:type"))
        if actual_v != expected_type:
            out.append(
                Violation(path, f"node:type is {actual_v!r}, expected {expected_type!r}")
            )
            return None
        return p

    def require_topic(prim, path: str, expected: str) -> None:
        value = _value(_attr(prim, "inputs:topicName"))
        if value != expected:
            out.append(
                Violation(
                    f"{path}.inputs:topicName",
                    f"is {value!r}, expected {expected!r} (unauthored means the "
                    "node default, which is not a contract this repo controls)",
                )
            )

    def require_connection(prim, path: str, input_name: str, source: str) -> None:
        if prim is None:
            return
        conns = _connected_from(prim, input_name)
        if source not in conns:
            out.append(
                Violation(
                    f"{path}.{input_name}",
                    f"not connected to {source} (connections: {conns or 'none'})",
                )
            )

    tick = prim_of(TICK_PATH, TICK_TYPE)
    pub = prim_of(PUBLISHER_PATH, PUBLISHER_TYPE)
    sub = prim_of(SUBSCRIBER_PATH, SUBSCRIBER_TYPE)
    ctrl = prim_of(CONTROLLER_PATH, CONTROLLER_TYPE)
    clock = prim_of(READ_SIM_TIME_PATH, READ_SIM_TIME_TYPE)

    tick_out = f"{TICK_PATH}.outputs:tick"

    # --- Feedback path: the arm's state reaches ROS 2 ---------------------- #
    reader = prim_of(READ_JOINT_STATE_PATH, READ_JOINT_STATE_TYPE)

    # --- The 6.0 joint-state read path ------------------------------------- #
    if reader is not None:
        require_connection(reader, READ_JOINT_STATE_PATH, "inputs:execIn", tick_out)
        rel = reader.relationships.get("inputs:prim")
        targets = (
            [str(t) for t in rel.targetPathList.GetAddedOrExplicitItems()]
            if rel is not None
            else []
        )
        if ROBOT_PRIM_PATH not in targets:
            out.append(
                Violation(
                    f"{READ_JOINT_STATE_PATH}.inputs:prim",
                    f"does not target {ROBOT_PRIM_PATH} (targets: {targets or 'none'})",
                )
            )

    if pub is not None:
        require_topic(pub, PUBLISHER_PATH, STATE_TOPIC)
        require_connection(pub, PUBLISHER_PATH, "inputs:execIn", tick_out)
        # 6.0: every joint-state field arrives from the reader. Wiring only
        # jointPositions and leaving jointNames unconnected would publish
        # positions with no names — the noise injector and controller both
        # index by name, so that fails silently downstream rather than here.
        for field in READ_JOINT_STATE_TO_PUBLISHER:
            require_connection(
                pub,
                PUBLISHER_PATH,
                f"inputs:{field}",
                f"{READ_JOINT_STATE_PATH}.outputs:{field}",
            )
        # Without a simulation-time source the published header.stamp stays at
        # the node default 0.0 for every message. waypoint_controller derives
        # its clock from that stamp, so a constant stamp means elapsed time is
        # always 0 and waypoint_timeout_s can never fire.
        require_connection(
            pub,
            PUBLISHER_PATH,
            "inputs:timeStamp",
            f"{READ_SIM_TIME_PATH}.outputs:simulationTime",
        )

    # --- Command path: ROS 2 drives the arm (the M4 gap) ------------------- #
    if sub is not None:
        require_topic(sub, SUBSCRIBER_PATH, COMMAND_TOPIC)
        require_connection(sub, SUBSCRIBER_PATH, "inputs:execIn", tick_out)

    if ctrl is not None:
        require_connection(ctrl, CONTROLLER_PATH, "inputs:execIn", tick_out)
        # jointNames must be wired, not just positionCommand: the controller
        # falls back to "all joints in articulation order" when names are
        # absent, which silently misdrives the arm (the 7 commanded arm joints
        # would be applied across all 9 including the fingers).
        for input_name, output_name in (
            ("inputs:jointNames", "outputs:jointNames"),
            ("inputs:positionCommand", "outputs:positionCommand"),
        ):
            require_connection(
                ctrl, CONTROLLER_PATH, input_name, f"{SUBSCRIBER_PATH}.{output_name}"
            )
        value = _value(_attr(ctrl, "inputs:robotPath"))
        if value != ROBOT_PRIM_PATH:
            out.append(
                Violation(
                    f"{CONTROLLER_PATH}.inputs:robotPath",
                    f"is {value!r}, expected {ROBOT_PRIM_PATH!r}",
                )
            )

    if clock is not None and tick is None:
        out.append(Violation(TICK_PATH, "graph has no playback tick to drive it"))

    return out


def graph_structure(scene_path) -> List[str]:
    """Normalized, ordered description of every OmniGraph node in the layer.

    One line per authored port, sorted, so the result is independent of USD
    crate byte layout. This exists because re-saving a ``.usd`` crate is NOT
    byte-reproducible: authoring the same graph twice yields two different file
    hashes. A file hash therefore cannot answer "is the committed scene the
    graph this script produces?" — this can.
    """
    layer = _open_layer(scene_path)
    lines: List[str] = []

    def walk(prim) -> None:
        if prim.typeName == "OmniGraphNode":
            path = str(prim.path)
            lines.append(f"node {path} type={_value(_attr(prim, 'node:type'))!r} "
                         f"version={_value(_attr(prim, 'node:typeVersion'))!r}")
            for name, attr in prim.attributes.items():
                if not (name.startswith("inputs:") or name.startswith("outputs:")):
                    continue
                conns = [
                    str(p) for p in attr.connectionPathList.GetAddedOrExplicitItems()
                ]
                lines.append(
                    f"port {path}.{name} type={attr.typeName} "
                    f"value={_value(attr)!r} connections={sorted(conns)}"
                )
            for name, rel in prim.relationships.items():
                targets = [
                    str(t) for t in rel.targetPathList.GetAddedOrExplicitItems()
                ]
                lines.append(f"rel  {path}.{name} targets={sorted(targets)}")
        for child in prim.nameChildren:
            walk(child)

    for root in layer.rootPrims:
        walk(root)
    return sorted(lines)


def graph_fingerprint(scene_path) -> str:
    """Stable sha256 over :func:`graph_structure` — the scene's real identity.

    Cite THIS in run manifests, not the ``.usd`` file hash: it is reproducible
    across re-saves and across USD versions that shuffle crate layout, and it
    changes if and only if the graph actually changes.
    """
    import hashlib

    payload = "\n".join(graph_structure(scene_path)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def describe_graph(scene_path) -> List[str]:
    """Human-readable dump of the scene's OmniGraph nodes (for run evidence)."""
    layer = _open_layer(scene_path)
    lines: List[str] = []

    def walk(prim) -> None:
        if prim.typeName == "OmniGraphNode":
            node_type = _value(_attr(prim, "node:type")) or "<untyped>"
            lines.append(f"{prim.path}  {node_type}")
        for child in prim.nameChildren:
            walk(child)

    for root in layer.rootPrims:
        walk(root)
    return sorted(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: ``python -m scenes.scene_contract [scene.usd]`` -> exit 0 if healthy."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m scenes.scene_contract",
        description="Statically verify the Franka scene's ROS 2 graph contract "
        "(no Isaac Sim required).",
    )
    parser.add_argument(
        "scene", nargs="?", default=str(Path(__file__).parent / SCENE_FILENAME)
    )
    args = parser.parse_args(argv)

    print(f"scene: {args.scene}")
    for line in describe_graph(args.scene):
        print(f"  {line}")
    violations = check_scene(args.scene)
    if not violations:
        print("OK: ROS 2 graph contract satisfied (scene-side; runtime is "
              "EDGEXPERT-VERIFY)")
        return 0
    print(f"FAILED: {len(violations)} contract violation(s)")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
