# Quickstart

This repository contains examples for multiple environments. Run only the parts that match your local setup.

## DSP Scripts

The DSP examples run with a normal Python scientific stack.

```bash
python3 dsp/filter_design.py
python3 dsp/visualizer.py
```

## ROS 2 Workspace

Run inside a prepared ROS 2 Humble environment or compatible DevContainer.

```bash
cd ros2-ws
colcon build
source install/setup.bash
```

Example package entry points:

```bash
ros2 run core_robotics_package simple_publisher
ros2 run cpp_pubsub talker
ros2 run cpp_pubsub listener
```

## Isaac Sim Scripts

Run Isaac Sim scripts only inside an Isaac Sim Python environment.

```bash
python3 scripts/simple_scene.py
python3 scripts/franka_wave.py
```

## Notes

- ROS 2 and Isaac Sim require substantial environment setup outside this repository.
- The DSP examples are the lightest local verification path.
- The scene assets are examples and may require version-specific Isaac Sim review.
