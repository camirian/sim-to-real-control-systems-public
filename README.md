# Sim-to-Real Control Systems

Public robotics examples for ROS 2 publisher/subscriber patterns, NVIDIA Isaac Sim scripting, OmniGraph bridge concepts, and digital signal processing for noisy joint-state telemetry.

This repository is a portfolio-oriented export. It keeps runnable examples and explanatory assets while excluding internal build logs, planning docs, and machine-specific operating notes.

## What This Shows

- Isaac Sim to ROS 2 bridge patterns for simulator-driven control workflows
- Mixed Python and C++ ROS 2 examples for message flow and node structure
- Joint-state filtering and telemetry analysis for noisy robotic signals
- Public-safe examples that connect robotics software and simulation

## What It Demonstrates

- ROS 2 Python and C++ publisher/subscriber packages.
- Isaac Sim scripts for simple scene setup and Franka robot motion.
- OmniGraph bridge concepts for simulator-to-ROS data flow.
- FIR and IIR filter design for noisy ROS 2-style joint telemetry.
- Engineering trade-offs around real-time filtering, latency, and phase response.

## Repository Layout

- `ros2-ws/`: ROS 2 workspace with Python and C++ packages.
- `scripts/`: Isaac Sim-oriented Python scripts.
- `dsp/`: signal-generation, filtering, visualization, and walkthrough material.
- `notebooks/`: exploratory engineering notebooks.
- `media/`: screenshots and supporting images.
- `scenes/`: Isaac Sim scene assets.

## Public Demos

- Isaac Sim robot motion: https://youtu.be/MKuvEEEHLwQ
- Isaac Sim to ROS 2 data stream: https://youtu.be/2jHL1TsLq30

## Related Public Reference

Robotics terminology and SysML v2 examples: https://github.com/camirian/robotics-ontology-public

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
