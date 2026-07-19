"""control_loop — closed-loop nodes for the sim-to-real Franka demo.

Architecture rule (AGENTS.md): every node is a pure-Python logic module in
:mod:`control_loop.logic` (fully unit-tested without ROS) plus a thin rclpy
wrapper module. Only the wrappers import rclpy.
"""

__version__ = "0.1.0"
