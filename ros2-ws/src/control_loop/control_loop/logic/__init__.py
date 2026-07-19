"""Pure-Python control-loop logic (no ROS imports allowed in this package).

Modules:

- :mod:`control_loop.logic.noise_model` — seeded joint-state noise (REQ-S2R-002)
- :mod:`control_loop.logic.filter_stage` — causal streaming filter (REQ-S2R-003)
- :mod:`control_loop.logic.waypoint_tracker` — waypoint sequencing + position
  controller (REQ-S2R-004)
"""
