#!/usr/bin/env python3
# File: franka_wave_final.py
# How to run:
# 1. cd to your Isaac Sim root directory (e.g., ~/isaac-sim)
# 2. Run: ./python.sh /path/to/this/script/franka_wave_final.py

import numpy as np
import math
from omni.isaac.kit import SimulationApp

CONFIG = {"headless": False}
simulation_app = SimulationApp(CONFIG)

from omni.isaac.core import World
from omni.isaac.franka import Franka
# THIS IS THE CORRECT IMPORT PATH for Isaac Sim 4.5.0
from omni.isaac.core.utils.types import ArticulationAction

world = World(stage_units_in_meters=1.0)
world.scene.add_default_ground_plane()

franka_robot = world.scene.add(
    Franka(
        prim_path="/World/Franka",
        name="franka_robot",
        position=np.array([0.0, 0.0, 0.0])
    )
)

world.reset()
print("Franka Robot added to the stage and physics is initialized.")

articulation_controller = franka_robot.get_articulation_controller()
step_count = 0

while simulation_app.is_running():
    world.step(render=True)

    if step_count > 120:
        joint_positions = franka_robot.get_joint_positions()
        
        if joint_positions is not None:
            frequency = 0.5
            amplitude = 0.8
            joint_positions[3] = math.sin(step_count * frequency * 0.02) * amplitude
            action = ArticulationAction(joint_positions=joint_positions)
            articulation_controller.apply_action(action)
    
    step_count += 1

simulation_app.close()