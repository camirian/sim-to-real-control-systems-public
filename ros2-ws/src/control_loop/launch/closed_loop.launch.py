"""Launch the full noisy -> filtered -> controlled loop (REQ-S2R-005 partial).

Brings up the three control_loop nodes against an already-running Isaac scene
(started separately via scripts/run_franka_headless.py on the sim box):

    /joint_states -> noise_injector -> /joint_states_noisy
                  -> dsp_filter     -> /joint_states_filtered
                  -> waypoint_controller -> /joint_command

Example:

    ros2 launch control_loop closed_loop.launch.py seed:=42 filter_kind:=iir

This file is authored in the cloud sandbox and gated by py_compile only.
"""

# EDGEXPERT-VERIFY: launch runtime (ros2 launch, node discovery, parameter
# wiring) has not been executed anywhere yet — walk through on the sim box.
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _int_param(name: str) -> ParameterValue:
    return ParameterValue(LaunchConfiguration(name), value_type=int)


def _float_param(name: str) -> ParameterValue:
    return ParameterValue(LaunchConfiguration(name), value_type=float)


def generate_launch_description() -> LaunchDescription:
    args = [
        # Noise profile (REQ-S2R-002)
        DeclareLaunchArgument("seed", default_value="0", description="Noise seed"),
        DeclareLaunchArgument("awgn_sigma", default_value="0.1"),
        DeclareLaunchArgument("vibration_amplitude", default_value="0.3"),
        DeclareLaunchArgument("vibration_freq_hz", default_value="25.0"),
        # Filter spec (REQ-S2R-003)
        # "iir" | "fir" | "passthrough"; the campaign's unfiltered condition
        # passes "passthrough" (identity filter, unchanged topology).
        DeclareLaunchArgument("filter_kind", default_value="iir"),
        DeclareLaunchArgument("sample_rate_hz", default_value="200.0"),
        DeclareLaunchArgument("cutoff_hz", default_value="5.0"),
        DeclareLaunchArgument("numtaps", default_value="101"),
        DeclareLaunchArgument("order", default_value="4"),
        # Controller (REQ-S2R-004)
        DeclareLaunchArgument("kp", default_value="0.8"),
        DeclareLaunchArgument("tolerance_rad", default_value="0.01"),
        DeclareLaunchArgument("max_step_rad", default_value="0.05"),
        DeclareLaunchArgument("waypoint_timeout_s", default_value="10.0"),
    ]

    noise_injector = Node(
        package="control_loop",
        executable="noise_injector",
        name="noise_injector",
        output="screen",
        parameters=[
            {
                "seed": _int_param("seed"),
                "awgn_sigma": _float_param("awgn_sigma"),
                "vibration_amplitude": _float_param("vibration_amplitude"),
                "vibration_freq_hz": _float_param("vibration_freq_hz"),
            }
        ],
    )

    dsp_filter = Node(
        package="control_loop",
        executable="dsp_filter",
        name="dsp_filter",
        output="screen",
        parameters=[
            {
                "filter_kind": LaunchConfiguration("filter_kind"),
                "sample_rate_hz": _float_param("sample_rate_hz"),
                "cutoff_hz": _float_param("cutoff_hz"),
                "numtaps": _int_param("numtaps"),
                "order": _int_param("order"),
            }
        ],
    )

    # Waypoint plan uses the node's parameter defaults; override with a params
    # file for campaign runs (waypoints_flat is a flat float array).
    waypoint_controller = Node(
        package="control_loop",
        executable="waypoint_controller",
        name="waypoint_controller",
        output="screen",
        parameters=[
            {
                "kp": _float_param("kp"),
                "tolerance_rad": _float_param("tolerance_rad"),
                "max_step_rad": _float_param("max_step_rad"),
                "waypoint_timeout_s": _float_param("waypoint_timeout_s"),
            }
        ],
    )

    return LaunchDescription(args + [noise_injector, dsp_filter, waypoint_controller])
