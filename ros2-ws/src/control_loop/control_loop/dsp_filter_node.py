"""Thin rclpy wrapper: causal DSP filter node (REQ-S2R-003).

/joint_states_noisy (sensor_msgs/JointState) -> /joint_states_filtered.

All filtering logic lives in :mod:`control_loop.logic.filter_stage`, which
wraps the causal ``s2r_dsp.apply_filter_realtime`` path only (zero-phase
filtering is banned in-loop per AGENTS.md §2). This wrapper only does message
plumbing and is gated by ``python -m py_compile`` in CI; its runtime behavior
is NOT verified in the cloud environment — see EDGEXPERT-VERIFY notes.
"""

# EDGEXPERT-VERIFY: rclpy import + node runtime require a sourced ROS 2 Humble
# environment; nothing below this line has been executed in the cloud sandbox.
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

from control_loop.logic.filter_stage import FilterSpec, FilterStage


class DspFilterNode(Node):
    """Streams noisy joint states through the causal per-joint filter."""

    def __init__(self) -> None:
        super().__init__("dsp_filter")
        self.declare_parameter("filter_kind", "iir")  # "fir" | "iir"
        self.declare_parameter("sample_rate_hz", 200.0)
        self.declare_parameter("cutoff_hz", 5.0)
        self.declare_parameter("numtaps", 101)
        self.declare_parameter("order", 4)
        self.declare_parameter("input_topic", "/joint_states_noisy")
        self.declare_parameter("output_topic", "/joint_states_filtered")

        self._spec = FilterSpec(
            kind=str(self.get_parameter("filter_kind").value),
            sample_rate_hz=float(self.get_parameter("sample_rate_hz").value),
            cutoff_hz=float(self.get_parameter("cutoff_hz").value),
            numtaps=int(self.get_parameter("numtaps").value),
            order=int(self.get_parameter("order").value),
        )
        self._spec.validate()
        self._stage = None  # built lazily once the joint count is known

        # EDGEXPERT-VERIFY: sample_rate_hz must match the actual /joint_states
        # publish rate on the sim box (assumed 200 Hz per the DSP synthesizer;
        # confirm with `ros2 topic hz /joint_states_noisy`). A mismatch shifts
        # the filter's effective cutoff.
        self._sub = self.create_subscription(
            JointState,
            str(self.get_parameter("input_topic").value),
            self._on_joint_state,
            10,
        )
        self._pub = self.create_publisher(
            JointState, str(self.get_parameter("output_topic").value), 10
        )
        self.get_logger().info(
            f"dsp_filter up ({self._spec.kind}, fs={self._spec.sample_rate_hz} Hz, "
            f"cutoff={self._spec.cutoff_hz} Hz)"
        )

    def _on_joint_state(self, msg: JointState) -> None:
        n = len(msg.position)
        if n == 0:
            return
        if self._stage is None or self._stage.num_joints != n:
            self._stage = FilterStage(self._spec, n)
        filtered = self._stage.process(list(msg.position))

        out = JointState()
        # EDGEXPERT-VERIFY: header stamp is passed through unchanged, so the
        # filter's group delay appears as signal lag, not timestamp lag —
        # the gauntlet's settling/RMS checks assume this convention.
        out.header = msg.header
        out.name = list(msg.name)
        out.position = [float(p) for p in filtered]
        out.velocity = list(msg.velocity)  # velocities passed through unmodified
        out.effort = list(msg.effort)
        self._pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DspFilterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
