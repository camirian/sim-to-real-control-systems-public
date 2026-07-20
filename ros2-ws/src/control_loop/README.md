# control_loop — closed-loop nodes (M2, REQ-S2R-002..005)

ROS 2 Humble `ament_python` package with the three loop nodes:

| Node (executable) | Subscribes | Publishes | Logic module (no ROS) |
|---|---|---|---|
| `noise_injector` | `/joint_states` | `/joint_states_noisy` | `control_loop/logic/noise_model.py` |
| `dsp_filter` | `/joint_states_noisy` | `/joint_states_filtered` | `control_loop/logic/filter_stage.py` |
| `waypoint_controller` | `/joint_states_filtered` | `/joint_command` | `control_loop/logic/waypoint_tracker.py` |

## Architecture rule

Every node = pure-Python logic module (fully unit-tested anywhere) + thin
rclpy wrapper (syntax-gated via `py_compile` only). Only wrappers import
`rclpy`. Runtime assumptions in the wrappers are marked `EDGEXPERT-VERIFY`
and must be walked through on the sim box before being claimed as working.
The filter stage wraps only the causal `s2r_dsp.apply_filter_realtime` path
(AGENTS.md §2); zero-phase filtering never enters the loop.

## Test without ROS (anywhere)

```bash
pip install -e "dsp/[test]"           # provides s2r_dsp
PYTHONPATH=ros2-ws/src/control_loop python -m pytest ros2-ws/src/control_loop/test
```

Note: `pip install -e ros2-ws/src/control_loop` is intentionally not the test
path — the ament-style `setup.cfg` script-dir overrides trip pip's legacy
develop command on some setuptools builds; colcon installs the package
properly in the ROS workspace.

## Build & launch (ROS 2 Humble box only — EDGEXPERT-VERIFY)

```bash
cd ros2-ws && colcon build --packages-select control_loop
source install/setup.bash
ros2 launch control_loop closed_loop.launch.py seed:=42 filter_kind:=iir cutoff_hz:=5.0
```

Launch arguments: `seed`, `awgn_sigma`, `vibration_amplitude`,
`vibration_freq_hz` (noise); `filter_kind` (`fir`|`iir`), `sample_rate_hz`,
`cutoff_hz`, `numtaps`, `order` (filter); `kp`, `tolerance_rad`,
`max_step_rad`, `waypoint_timeout_s` (controller). Waypoints are set via the
`waypoints_flat` + `joint_names` node parameters (params file for campaigns).

Isaac must already be up with the Franka scene
(`scripts/run_franka_headless.py`). The scene currently only publishes
`/joint_states`; the `/joint_command` OmniGraph subscriber must be added on
the sim box before the loop closes (tracked for M2 integration).
