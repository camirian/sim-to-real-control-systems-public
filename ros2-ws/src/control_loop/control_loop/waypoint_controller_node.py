"""Thin rclpy wrapper: joint-space waypoint controller node (REQ-S2R-004/005).

/joint_states_filtered (sensor_msgs/JointState) -> /joint_command
(sensor_msgs/JointState position commands, Isaac Sim ROS 2 bridge convention).

All sequencing/control logic lives in
:mod:`control_loop.logic.waypoint_tracker` (unit-tested without ROS,
including the unreachable-waypoint timeout). This wrapper only does message
plumbing and is gated by ``python -m py_compile`` in CI; its runtime behavior
is NOT verified in the cloud environment — see EDGEXPERT-VERIFY notes.
"""

# EDGEXPERT-VERIFY: rclpy import + node runtime require a sourced ROS 2 Humble
# environment; nothing below this line has been executed in the cloud sandbox.
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

from control_loop.logic.franka_limits import ARM_JOINT_NAMES, limits_for
from control_loop.logic.waypoint_tracker import (
    DEFAULT_WAYPOINTS_FLAT,
    TrackerStatus,
    WaypointTracker,
    waypoints_from_flat,
)

# Franka Panda arm joints (fingers excluded from tracking commands). Defined in
# the ROS-free logic layer so tests and CI can reach them without rclpy; kept
# under the historical name here because it is this node's parameter default.
DEFAULT_JOINT_NAMES = list(ARM_JOINT_NAMES)


class WaypointControllerNode(Node):
    """Drives the arm through parameterized joint-space waypoints."""

    def __init__(self) -> None:
        super().__init__("waypoint_controller")
        self.declare_parameter("joint_names", DEFAULT_JOINT_NAMES)
        self.declare_parameter("waypoints_flat", DEFAULT_WAYPOINTS_FLAT)
        self.declare_parameter("tolerance_rad", 0.01)
        self.declare_parameter("kp", 0.8)
        self.declare_parameter("max_step_rad", 0.05)
        self.declare_parameter("waypoint_timeout_s", 10.0)
        self.declare_parameter("input_topic", "/joint_states_filtered")
        self.declare_parameter("command_topic", "/joint_command")
        self.declare_parameter("enforce_joint_limits", True)

        self._joint_names = [str(n) for n in self.get_parameter("joint_names").value]
        waypoints = waypoints_from_flat(
            [float(x) for x in self.get_parameter("waypoints_flat").value],
            num_joints=len(self._joint_names),
            tolerance_rad=float(self.get_parameter("tolerance_rad").value),
        )
        # Joint limits come from the Isaac Franka asset the scene references
        # (see logic.franka_limits for the extraction provenance). Bounding the
        # commanded position keeps a run from producing physically meaningless
        # evidence; it is not a safety function and says nothing about hardware.
        joint_limits = (
            limits_for(self._joint_names)
            if bool(self.get_parameter("enforce_joint_limits").value)
            else None
        )
        self._tracker = WaypointTracker(
            waypoints,
            kp=float(self.get_parameter("kp").value),
            max_step_rad=float(self.get_parameter("max_step_rad").value),
            waypoint_timeout_s=float(self.get_parameter("waypoint_timeout_s").value),
            joint_limits=joint_limits,
        )
        self._terminal_logged = False
        self._clamp_logged = False

        self._sub = self.create_subscription(
            JointState,
            str(self.get_parameter("input_topic").value),
            self._on_joint_state,
            10,
        )
        # EDGEXPERT-VERIFY: command topic/message convention assumed to be the
        # Isaac Sim ROS 2 bridge default — sensor_msgs/JointState positions on
        # /joint_command consumed by an OmniGraph ROS2SubscribeJointState +
        # articulation controller. The current franka_ros2_bridge_scene.usd
        # only PUBLISHES joint states; the subscriber graph node must be added
        # (or the scene extended) on the sim box before closed-loop runs.
        self._pub = self.create_publisher(
            JointState, str(self.get_parameter("command_topic").value), 10
        )
        self.get_logger().info(
            f"waypoint_controller up ({len(waypoints)} waypoints, "
            f"{len(self._joint_names)} joints)"
        )

    def _on_joint_state(self, msg: JointState) -> None:
        # EDGEXPERT-VERIFY: joint ordering in /joint_states from the OmniGraph
        # publisher is assumed stable; we reorder by name and ignore extras
        # (e.g. finger joints), so only presence of all controlled joints is
        # required. Confirm names match DEFAULT_JOINT_NAMES on the sim box.
        try:
            index = {name: i for i, name in enumerate(msg.name)}
            measured = [float(msg.position[index[n]]) for n in self._joint_names]
        except KeyError as e:
            self.get_logger().warn(f"controlled joint missing from joint state: {e}")
            return

        # EDGEXPERT-VERIFY: control update runs per incoming sample in the
        # subscription callback (single-threaded default executor) — i.e. the
        # loop rate equals the /joint_states_filtered publish rate. Timing is
        # taken from the message header stamp (sim time).
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        out = self._tracker.update(measured, t)

        if out.status in (TrackerStatus.DONE, TrackerStatus.TIMED_OUT):
            if not self._terminal_logged:
                self._terminal_logged = True
                self.get_logger().info(
                    f"tracker terminal: {out.status.value}; results="
                    f"{[(r.index, r.reached, round(r.elapsed_s, 3)) for r in self._tracker.results]}"
                )
            # Terminal: hold position (command = measured) so the arm stops.

        if out.limit_clamped and not self._clamp_logged:
            # Once, not per sample: at loop rate this would flood the log. A
            # clamped command means the plan or the gains are driving the arm
            # into a limit — worth seeing in the run's stdout evidence.
            self._clamp_logged = True
            self.get_logger().warn(
                "command clamped to Franka joint limits (logged once per run)"
            )

        cmd = JointState()
        cmd.header.stamp = msg.header.stamp
        cmd.name = list(self._joint_names)
        cmd.position = [float(p) for p in out.command]
        self._pub.publish(cmd)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = WaypointControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
