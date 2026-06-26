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

## What Runs Where

- **DSP examples (`dsp/`)** run standalone with a plain Python scientific
  stack. No ROS 2 or Isaac Sim required. This is the part a stranger can run and
  verify in minutes.
- **ROS 2 workspace (`ros2-ws/`)** requires a ROS 2 Humble environment
  (`colcon`, `rclcpp`/`rclpy`, `std_msgs`). It does not run in a plain shell.
- **Isaac Sim scripts (`scripts/`) and scenes (`scenes/`)** require an NVIDIA
  Isaac Sim Python environment and are not runnable outside it.

See [QUICKSTART.md](QUICKSTART.md) for the full per-environment commands.

## DSP Quickstart (standalone)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r dsp/requirements.txt

cd dsp
python3 filter_design.py     # writes bode_plot.png and filter_comparison.png
python3 visualizer.py        # writes assets/{fir_bode,iir_bode,time_domain_comparison}.png
pytest test_filters.py       # runs the filter unit tests
```

Synthesized telemetry is seeded, so the plots and metrics are reproducible
across runs. For the design rationale and annotated Bode/time-domain plots, see
[dsp/FILTER_DESIGN_WALKTHROUGH.md](dsp/FILTER_DESIGN_WALKTHROUGH.md).

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
