"""Thin rclpy wrapper: seeded noise injector node (REQ-S2R-002).

/joint_states (sensor_msgs/JointState) -> /joint_states_noisy.

All noise logic lives in :mod:`control_loop.logic.noise_model` (unit-tested
without ROS). This wrapper only does message plumbing and is gated by
``python -m py_compile`` in CI; its runtime behavior is NOT verified in the
cloud environment — see the EDGEXPERT-VERIFY notes below.
"""

# EDGEXPERT-VERIFY: rclpy import + node runtime require a sourced ROS 2 Humble
# environment; nothing below this line has been executed in the cloud sandbox.
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

from control_loop.logic.noise_model import JointStateNoiseModel, NoiseProfile


class NoiseInjectorNode(Node):
    """Subscribes clean joint states, republishes them with seeded noise."""

    def __init__(self) -> None:
        super().__init__("noise_injector")
        self.declare_parameter("seed", 0)
        self.declare_parameter("awgn_sigma", 0.1)
        self.declare_parameter("vibration_amplitude", 0.3)
        self.declare_parameter("vibration_freq_hz", 25.0)
        self.declare_parameter("input_topic", "/joint_states")
        self.declare_parameter("output_topic", "/joint_states_noisy")

        self._profile = NoiseProfile(
            seed=int(self.get_parameter("seed").value),
            awgn_sigma=float(self.get_parameter("awgn_sigma").value),
            vibration_amplitude=float(self.get_parameter("vibration_amplitude").value),
            vibration_freq_hz=float(self.get_parameter("vibration_freq_hz").value),
        )
        self._model = None  # built lazily once the joint count is known

        # EDGEXPERT-VERIFY: input topic name and QoS must match the OmniGraph
        # ROS 2 joint-state publisher in scenes/franka_ros2_bridge_scene.usd
        # (assumed: "/joint_states", default sensor-data-compatible depth-10
        # QoS). Confirm with `ros2 topic info -v /joint_states` on the sim box.
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
            f"noise_injector up (seed={self._profile.seed}, "
            f"sigma={self._profile.awgn_sigma}, "
            f"vib={self._profile.vibration_amplitude}@{self._profile.vibration_freq_hz}Hz)"
        )

    def _on_joint_state(self, msg: JointState) -> None:
        n = len(msg.position)
        if n == 0:
            return
        if self._model is None or self._model.num_joints != n:
            # EDGEXPERT-VERIFY: the Franka scene publishes a fixed joint count
            # (expected 9: 7 arm + 2 fingers). A mid-run joint-count change
            # rebuilds the model and restarts the seed's AWGN stream.
            self._model = JointStateNoiseModel(self._profile, n)
        # EDGEXPERT-VERIFY: vibration phase is driven by the message header
        # stamp; assumes the OmniGraph publisher stamps messages with sim time.
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        noisy = self._model.apply(list(msg.position), t)

        out = JointState()
        out.header = msg.header
        out.name = list(msg.name)
        out.position = [float(p) for p in noisy]
        out.velocity = list(msg.velocity)  # velocities passed through unmodified
        out.effort = list(msg.effort)
        self._pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = NoiseInjectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
