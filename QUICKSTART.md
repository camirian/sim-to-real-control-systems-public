# Quickstart

This repository contains examples for multiple environments. Run only the parts that match your local setup.

## DSP Scripts (runs standalone — no ROS 2 or Isaac Sim needed)

The DSP examples run with a normal Python scientific stack. They are the only
part of this repo that runs in a plain environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r dsp/requirements.txt

cd dsp
python3 filter_design.py     # writes bode_plot.png and filter_comparison.png
python3 visualizer.py        # writes assets/{fir_bode,iir_bode,time_domain_comparison}.png
pytest test_filters.py       # runs the filter unit tests
```

Run the scripts from inside `dsp/` so the generated plots are written next to
the source (and into `dsp/assets/`). The synthesized telemetry is seeded, so
output is reproducible across runs. Expected output:

```
Files 'filter_comparison.png' and 'bode_plot.png' generated successfully.
Visualizations successfully generated and saved to .../dsp/assets/
```

See [dsp/FILTER_DESIGN_WALKTHROUGH.md](dsp/FILTER_DESIGN_WALKTHROUGH.md) for the
filter-design rationale and annotated plots.

## ROS 2 Workspace

Run inside a prepared ROS 2 Humble environment or compatible DevContainer.

```bash
cd ros2-ws
colcon build
source install/setup.bash
```

Example package entry points:

```bash
ros2 run core_robotics_package simple_publisher.py
ros2 run cpp_pubsub talker
ros2 run cpp_pubsub listener
```

The Python node installs with its `.py` extension (see
`ros2-ws/src/core_robotics_package/CMakeLists.txt`), so it is launched as
`simple_publisher.py`.

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
