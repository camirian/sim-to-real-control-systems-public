"""Author the missing `/joint_command` path into the Franka scene (REQ-S2R-005).

Closes the M4 blocking gap recorded in docs/RUN_ON_EDGEXPERT.md §3: the
committed `scenes/franka_ros2_bridge_scene.usd` only PUBLISHES `/joint_states`,
so `waypoint_controller`'s commands on `/joint_command` had no consumer and the
arm never moved.

Unlike the runbook's original instructions ("open the scene in Isaac Sim, add
the node by hand, re-save"), this authors the graph as **data**, with
`usd-core` — no Isaac Sim, no GUI, no manual step. That matters for three
reasons: the change is reviewable as a diff-able script rather than an opaque
binary re-save, it is reproducible by anyone with `pip install usd-core`, and
it is verifiable in CI by `scenes/scene_contract.py`.

    python scripts/author_joint_command_graph.py            # in place
    python scripts/author_joint_command_graph.py --check    # verify only

Determinism, measured rather than assumed. Run against the *pristine* scene the
output is byte-reproducible (sha256 ``142c8025…`` both times it was produced
here). Run against its own output it is idempotent at the **graph** level — the
structure is identical — but NOT at the byte level: re-saving an
already-authored crate layer yields different bytes (``e0ffb938…``) for the
same graph. So: author once from the committed scene, and cite
``scenes.scene_contract.graph_fingerprint()`` — a hash over the normalized
graph structure, stable across re-saves — in run manifests rather than the
``.usd`` file hash. Do not re-run this script casually against a scene that
already satisfies the contract.

What it adds, mirroring the serialization of the publisher node already in the
scene (OmniGraphNode prim + `NodeGraphNodeAPI` + custom `inputs:`/`outputs:`
attributes, execution ports as `uint`):

1. `ros2_subscribe_joint_command` — `ROS2SubscribeJointState` on
   `/joint_command`, ticked by the existing `on_playback_tick`.
2. `articulation_controller` — `IsaacArticulationController` bound to `/Franka`,
   fed the subscriber's `jointNames` AND `positionCommand`. Wiring the names
   (not just the positions) is what makes the ordering self-describing; without
   them the controller falls back to all joints in articulation order, which
   silently misdrives the arm.
3. `read_sim_time` — `IsaacReadSimulationTime` feeding the publisher's
   `inputs:timeStamp`, which the committed scene left unauthored (default
   `0.0`). This matches the canonical 4.5.0 wiring; see the CAVEAT below.
4. Explicit `inputs:topicName` on both ROS 2 nodes. The node defaults are
   already `joint_states` / `joint_command`, but an unauthored attribute is a
   contract this repo does not control; authoring it makes the boundary
   explicit and lets the contract check assert a real value.

CAVEAT — one inference, not established. The OGN reference documents
`inputs:timeStamp` as "ROS2 Timestamp in seconds", default `0.0`, and the
official 4.5.0 manipulation tutorial always wires `ReadSimTime` into it. It
does NOT document what the outgoing `header.stamp` contains when nothing is
wired. `waypoint_controller_node` derives its clock from `header.stamp`
(`waypoint_controller_node.py:107`), so IF an unwired publisher stamps every
message `0.0`, elapsed time is always zero and `waypoint_timeout_s` can never
fire. That consequence is unverified inference. Settle it on the sim box with
`ros2 topic echo /joint_states --field header.stamp` and record the reading —
it is an EDGEXPERT-VERIFY item, not a claim.

Node specifications (Isaac Sim 4.5.0, the pinned version):
* https://docs.isaacsim.omniverse.nvidia.com/4.5.0/py/source/extensions/isaacsim.ros2.bridge/docs/ogn/OgnROS2SubscribeJointState.html
* https://docs.isaacsim.omniverse.nvidia.com/4.5.0/py/source/extensions/isaacsim.core.nodes/docs/ogn/OgnIsaacArticulationController.html
* https://docs.isaacsim.omniverse.nvidia.com/4.5.0/py/source/extensions/isaacsim.core.nodes/docs/ogn/OgnIsaacReadSimulationTime.html
* wiring: https://docs.isaacsim.omniverse.nvidia.com/4.5.0/ros2_tutorials/tutorial_ros2_manipulation.html
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # allow `python scripts/...` from anywhere
    sys.path.insert(0, str(REPO_ROOT))

from scenes.scene_contract import (  # noqa: E402
    COMMAND_TOPIC,
    CONTROLLER_PATH,
    CONTROLLER_TYPE,
    PUBLISHER_PATH,
    READ_SIM_TIME_PATH,
    READ_SIM_TIME_TYPE,
    ROBOT_PRIM_PATH,
    SCENE_FILENAME,
    STATE_TOPIC,
    SUBSCRIBER_PATH,
    SUBSCRIBER_TYPE,
    TICK_PATH,
    check_scene,
    describe_graph,
)

DEFAULT_SCENE = REPO_ROOT / "scenes" / SCENE_FILENAME

# typeVersion is per node, not per graph — do not normalize these. Values are
# from each node's 4.5.0 OGN reference page (see module docstring).
SUBSCRIBER_TYPE_VERSION = 2
CONTROLLER_TYPE_VERSION = 1
READ_SIM_TIME_TYPE_VERSION = 1


def _node(stage, path: str, node_type: str, type_version: int, pos):
    """Create (or fetch) an OmniGraphNode prim serialized like the existing ones."""
    from pxr import Gf, Sdf, Usd

    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        prim = stage.DefinePrim(path, "OmniGraphNode")
    # The publisher already in the scene carries exactly this API schema.
    prim.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NodeGraphNodeAPI"]))
    prim.CreateAttribute("node:type", Sdf.ValueTypeNames.Token, False).Set(node_type)
    prim.CreateAttribute("node:typeVersion", Sdf.ValueTypeNames.Int, False).Set(
        type_version
    )
    prim.CreateAttribute(
        "ui:nodegraph:node:pos",
        Sdf.ValueTypeNames.Float2,
        True,
        Sdf.VariabilityUniform,
    ).Set(Gf.Vec2f(*pos))
    prim.CreateAttribute(
        "ui:nodegraph:node:expansionState",
        Sdf.ValueTypeNames.Token,
        True,
        Sdf.VariabilityUniform,
    ).Set("open")
    return prim


def _port(prim, name: str, type_name, value=None):
    """Create a custom `inputs:`/`outputs:` port, matching the scene's style."""
    attr = prim.CreateAttribute(name, type_name, True)
    if value is not None:
        attr.Set(value)
    return attr


def author_graph(scene_path=DEFAULT_SCENE) -> None:
    """Author the command path into ``scene_path`` in place (idempotent)."""
    from pxr import Sdf, Usd

    scene_path = Path(scene_path)
    if not scene_path.is_file():
        raise FileNotFoundError(f"scene not found: {scene_path}")

    # LoadNone: the scene references the Franka asset over https, which the
    # plain USD resolver cannot fetch. Every prim authored here lives in the
    # local layer, so an unresolvable payload must not block authoring.
    stage = Usd.Stage.Open(str(scene_path), load=Usd.Stage.LoadNone)

    tick_out = f"{TICK_PATH}.outputs:tick"
    tick = stage.GetPrimAtPath(TICK_PATH)
    if not tick or not tick.IsValid():
        raise RuntimeError(
            f"{TICK_PATH} not found — this script extends the existing graph "
            "rather than rebuilding it; the scene is not the expected one."
        )

    # --- 1. The subscriber: /joint_command -> decoded joint arrays --------- #
    # No targetPrim/robotPath here by design: the subscriber is robot-agnostic
    # and only decodes a message. The robot binding lives on the controller.
    sub = _node(stage, SUBSCRIBER_PATH, SUBSCRIBER_TYPE, SUBSCRIBER_TYPE_VERSION,
                (318.0, 300.0))
    _port(sub, "inputs:context", Sdf.ValueTypeNames.UInt64)
    _port(sub, "inputs:execIn", Sdf.ValueTypeNames.UInt)
    _port(sub, "inputs:nodeNamespace", Sdf.ValueTypeNames.String)
    _port(sub, "inputs:qosProfile", Sdf.ValueTypeNames.String)
    _port(sub, "inputs:queueSize", Sdf.ValueTypeNames.UInt64)
    _port(sub, "inputs:topicName", Sdf.ValueTypeNames.String, COMMAND_TOPIC)
    _port(sub, "outputs:execOut", Sdf.ValueTypeNames.UInt)
    _port(sub, "outputs:jointNames", Sdf.ValueTypeNames.TokenArray)
    _port(sub, "outputs:positionCommand", Sdf.ValueTypeNames.DoubleArray)
    _port(sub, "outputs:velocityCommand", Sdf.ValueTypeNames.DoubleArray)
    _port(sub, "outputs:effortCommand", Sdf.ValueTypeNames.DoubleArray)
    _port(sub, "outputs:timeStamp", Sdf.ValueTypeNames.Double)
    sub.GetAttribute("inputs:execIn").SetConnections([Sdf.Path(tick_out)])

    # --- 2. The articulation controller: joint arrays -> the arm ----------- #
    ctrl = _node(stage, CONTROLLER_PATH, CONTROLLER_TYPE, CONTROLLER_TYPE_VERSION,
                 (702.0, 300.0))
    _port(ctrl, "inputs:execIn", Sdf.ValueTypeNames.UInt)
    # robotPath (plain string) rather than the targetPrim relationship: both
    # are supported and mutually exclusive, and the string sidesteps
    # relationship serialization when authoring outside Isaac Sim.
    _port(ctrl, "inputs:robotPath", Sdf.ValueTypeNames.String, ROBOT_PRIM_PATH)
    _port(ctrl, "inputs:jointNames", Sdf.ValueTypeNames.TokenArray)
    _port(ctrl, "inputs:jointIndices", Sdf.ValueTypeNames.IntArray)
    _port(ctrl, "inputs:positionCommand", Sdf.ValueTypeNames.DoubleArray)
    _port(ctrl, "inputs:velocityCommand", Sdf.ValueTypeNames.DoubleArray)
    _port(ctrl, "inputs:effortCommand", Sdf.ValueTypeNames.DoubleArray)
    # The tick drives the controller's execIn DIRECTLY — the canonical 4.5.0
    # tutorial does not chain the subscriber's execOut into it; all exec-driven
    # nodes hang off the same tick.
    ctrl.GetAttribute("inputs:execIn").SetConnections([Sdf.Path(tick_out)])
    ctrl.GetAttribute("inputs:jointNames").SetConnections(
        [Sdf.Path(f"{SUBSCRIBER_PATH}.outputs:jointNames")]
    )
    ctrl.GetAttribute("inputs:positionCommand").SetConnections(
        [Sdf.Path(f"{SUBSCRIBER_PATH}.outputs:positionCommand")]
    )

    # --- 3. Simulation clock into the publisher's timestamp ---------------- #
    # ReadSimulationTime has NO exec ports (it is a pure pull node) — wiring a
    # tick into it would author a connection to an attribute that does not
    # exist on the node.
    clock = _node(stage, READ_SIM_TIME_PATH, READ_SIM_TIME_TYPE,
                  READ_SIM_TIME_TYPE_VERSION, (318.0, 160.0))
    _port(clock, "inputs:resetOnStop", Sdf.ValueTypeNames.Bool, False)
    _port(clock, "outputs:simulationTime", Sdf.ValueTypeNames.Double)

    # --- 4. Pin the publisher's side of the contract ----------------------- #
    pub = stage.GetPrimAtPath(PUBLISHER_PATH)
    if not pub or not pub.IsValid():
        raise RuntimeError(f"{PUBLISHER_PATH} not found; unexpected scene")
    _port(pub, "inputs:topicName", Sdf.ValueTypeNames.String, STATE_TOPIC)
    _port(pub, "inputs:timeStamp", Sdf.ValueTypeNames.Double)
    pub.GetAttribute("inputs:timeStamp").SetConnections(
        [Sdf.Path(f"{READ_SIM_TIME_PATH}.outputs:simulationTime")]
    )

    stage.GetRootLayer().Save()


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python scripts/author_joint_command_graph.py",
        description="Author the /joint_command subscriber + articulation "
        "controller into the Franka scene (no Isaac Sim required).",
    )
    parser.add_argument("--scene", default=str(DEFAULT_SCENE))
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the contract without writing to the scene",
    )
    args = parser.parse_args(argv)

    if not args.check:
        author_graph(args.scene)
        print(f"authored command path into {args.scene}")

    print("graph nodes:")
    for line in describe_graph(args.scene):
        print(f"  {line}")

    violations = check_scene(args.scene)
    if violations:
        print(f"FAILED: {len(violations)} contract violation(s)")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("OK: ROS 2 graph contract satisfied (scene-side; runtime is "
          "EDGEXPERT-VERIFY)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
