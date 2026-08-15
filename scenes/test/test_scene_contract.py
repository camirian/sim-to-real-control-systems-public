"""The scene/ROS boundary check (REQ-S2R-005). No Isaac Sim, no ROS, no network.

This is the automated guard for the defect that kept M4 open: the Franka scene
published `/joint_states` but nothing subscribed to `/joint_command`, so the
closed loop was open and the arm never responded to the controller. Nothing in
the repo could detect that — the gap was recorded in prose in
`docs/RUN_ON_EDGEXPERT.md` §3 and in a code comment, and prose does not fail a
build.

What would this test have caught? Run it against commit `a69189e` and it fails
with five violations, including the missing subscriber. That is the whole
point: the check is written so that the *pre-fix* scene is a failing case.

The `TestCrossesTheBoundary` class is the part that keeps earning its keep: it
pins the scene's topic names against the ROS node defaults on the other side,
so the two halves cannot drift apart silently.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytest.importorskip("pxr", reason="scene contract checks need usd-core")

from scenes import scene_contract as sc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCENE = REPO_ROOT / "scenes" / sc.SCENE_FILENAME
CONTROL_LOOP = REPO_ROOT / "ros2-ws" / "src" / "control_loop" / "control_loop"


def _declared_default(source_path: Path, param_name: str):
    """Read a node's `declare_parameter(<name>, <default>)` default statically.

    Parsed with `ast` rather than imported: the node modules import `rclpy`,
    which is absent in CI by design (AGENTS.md §2 — no ROS runtime in CI).
    Static parsing lets the test pin the real value the node will use without
    standing up ROS.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "declare_parameter"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        if node.args[0].value != param_name or len(node.args) < 2:
            continue
        return ast.literal_eval(node.args[1])
    raise AssertionError(f"no declare_parameter({param_name!r}, ...) in {source_path}")


class TestCommittedSceneSatisfiesTheContract:
    def test_no_violations(self):
        violations = sc.check_scene(SCENE)
        assert violations == [], "\n".join(str(v) for v in violations)

    def test_all_six_graph_nodes_present(self):
        # Six under Isaac Sim 6.0.1-rc.7: the joint-state reader joined the graph
        # when 6.0 stopped letting ROS 2 publishers resolve USD prims directly.
        types = {line.split()[-1] for line in sc.describe_graph(SCENE)}
        assert types == {
            sc.TICK_TYPE,
            sc.PUBLISHER_TYPE,
            sc.SUBSCRIBER_TYPE,
            sc.CONTROLLER_TYPE,
            sc.READ_SIM_TIME_TYPE,
            sc.READ_JOINT_STATE_TYPE,
        }

    def test_fingerprint_is_stable_across_reads(self):
        # The fingerprint is what run manifests cite instead of the .usd file
        # hash (crate re-saves are not byte-reproducible). It must at minimum
        # be a pure function of the file.
        assert sc.graph_fingerprint(SCENE) == sc.graph_fingerprint(SCENE)

    def test_check_needs_no_network(self, monkeypatch):
        # The scene references the Franka asset over https. A fresh clone must
        # be able to validate it offline, so the check must never touch the
        # network: composing a Usd.Stage would, opening the Sdf.Layer does not.
        import socket

        def _blocked(*a, **k):  # pragma: no cover - only runs if violated
            raise AssertionError("scene contract check attempted network access")

        monkeypatch.setattr(socket, "socket", _blocked)
        monkeypatch.setattr(socket, "create_connection", _blocked)
        assert sc.check_scene(SCENE) == []


class TestCrossesTheBoundary:
    """Scene topic names vs. the ROS nodes on the other side of the bridge."""

    def test_command_topic_matches_the_controller_publisher(self):
        declared = _declared_default(
            CONTROL_LOOP / "waypoint_controller_node.py", "command_topic"
        )
        assert declared == f"/{sc.COMMAND_TOPIC}", (
            f"waypoint_controller publishes {declared!r} but the scene's "
            f"ROS2SubscribeJointState listens on '/{sc.COMMAND_TOPIC}' — the "
            "loop would be open again."
        )

    def test_state_topic_matches_the_noise_injector_subscriber(self):
        declared = _declared_default(
            CONTROL_LOOP / "noise_injector_node.py", "input_topic"
        )
        assert declared == f"/{sc.STATE_TOPIC}"

    def test_filter_and_controller_topics_chain(self):
        filt_out = _declared_default(CONTROL_LOOP / "dsp_filter_node.py", "output_topic")
        ctrl_in = _declared_default(
            CONTROL_LOOP / "waypoint_controller_node.py", "input_topic"
        )
        assert filt_out == ctrl_in, "filter output and controller input disagree"

    def test_noise_output_feeds_the_filter_input(self):
        noise_out = _declared_default(
            CONTROL_LOOP / "noise_injector_node.py", "output_topic"
        )
        filt_in = _declared_default(CONTROL_LOOP / "dsp_filter_node.py", "input_topic")
        assert noise_out == filt_in


class TestTheCheckHasTeeth:
    """A check that cannot fail is decoration. These break the scene on purpose."""

    @pytest.fixture
    def scratch_scene(self, tmp_path):
        from pxr import Sdf

        target = tmp_path / sc.SCENE_FILENAME
        Sdf.Layer.FindOrOpen(str(SCENE)).Export(str(target))
        assert sc.check_scene(target) == []  # the copy starts healthy
        return target

    def _mutate(self, path, fn):
        from pxr import Sdf

        layer = Sdf.Layer.FindOrOpen(str(path))
        fn(layer)
        layer.Save()
        Sdf.Layer.FindOrOpen(str(path)).Reload()

    def test_removing_the_subscriber_is_caught(self, scratch_scene):
        def drop(layer):
            graph = layer.GetPrimAtPath(sc.GRAPH_PATH)
            del graph.nameChildren[Sdf.Path(sc.SUBSCRIBER_PATH).name]

        from pxr import Sdf  # noqa: F811 - used inside drop

        self._mutate(scratch_scene, drop)
        problems = [str(v) for v in sc.check_scene(scratch_scene)]
        assert any(sc.SUBSCRIBER_PATH in p and "missing" in p for p in problems), problems

    def test_wrong_command_topic_is_caught(self, scratch_scene):
        def retopic(layer):
            prim = layer.GetPrimAtPath(sc.SUBSCRIBER_PATH)
            prim.attributes["inputs:topicName"].default = "/some_other_topic"

        self._mutate(scratch_scene, retopic)
        problems = [str(v) for v in sc.check_scene(scratch_scene)]
        assert any("topicName" in p for p in problems), problems

    def test_unwiring_joint_names_is_caught(self, scratch_scene):
        # The subtle one: positions still flow, but without joint names the
        # articulation controller falls back to all joints in articulation
        # order and silently misdrives the arm.
        def unwire(layer):
            prim = layer.GetPrimAtPath(sc.CONTROLLER_PATH)
            prim.attributes["inputs:jointNames"].connectionPathList.ClearEdits()

        self._mutate(scratch_scene, unwire)
        problems = [str(v) for v in sc.check_scene(scratch_scene)]
        assert any("jointNames" in p for p in problems), problems

    def test_unwiring_the_sim_clock_is_caught(self, scratch_scene):
        def unwire(layer):
            prim = layer.GetPrimAtPath(sc.PUBLISHER_PATH)
            prim.attributes["inputs:timeStamp"].connectionPathList.ClearEdits()

        self._mutate(scratch_scene, unwire)
        problems = [str(v) for v in sc.check_scene(scratch_scene)]
        assert any("timeStamp" in p for p in problems), problems

    def test_fingerprint_changes_when_the_graph_changes(self, scratch_scene):
        before = sc.graph_fingerprint(scratch_scene)

        def retopic(layer):
            layer.GetPrimAtPath(sc.SUBSCRIBER_PATH).attributes[
                "inputs:topicName"
            ].default = "/other"

        self._mutate(scratch_scene, retopic)
        assert sc.graph_fingerprint(scratch_scene) != before

    def test_missing_scene_file_is_an_error_not_a_pass(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            sc.check_scene(tmp_path / "nope.usd")
