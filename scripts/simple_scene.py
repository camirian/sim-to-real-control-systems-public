#!/usr/bin/env python3
# File: scripts/simple_scene.py

import numpy as np
# The isaacsim.SimulationApp class is the top-level entry point for the simulator.
from isaacsim import SimulationApp

# Configuration for the simulation app. 'headless: False' ensures the UI is visible.
CONFIG = {"headless": False}

# Instantiate the SimulationApp. This must be done before any other Isaac Sim imports.
simulation_app = SimulationApp(CONFIG)

# Import core Isaac Sim APIs. For this version, we use the 'omni.isaac.core' path.
from omni.isaac.core import World
from omni.isaac.core.objects import DynamicCuboid

# Create a World object, which manages the simulation stage, physics, and assets.
world = World(stage_units_in_meters=1.0)

# Add a default ground plane to provide a surface for our cube to rest on.
world.scene.add_default_ground_plane()

# Add a dynamic cube to the scene using the correct DynamicCuboid class.
# This single object includes visuals (a mesh) and physics (rigid body, collision).
world.scene.add(
    DynamicCuboid(
        prim_path="/World/MyCube",          # A unique path in the simulation stage.
        name="my_red_cube",                 # A name to reference the object by.
        position=np.array([0, 0, 1.0]),     # Initial position in meters.
        scale=np.array([0.5, 0.5, 0.5]),    # Size in meters (length, width, height).
        color=np.array([1.0, 0.0, 0.0]),    # Set color to red (R, G, B).
    )
)

# Reset the world. This is crucial for initializing physics and object states.
world.reset()

# This is the main simulation loop. It will run continuously until you close the window.
while simulation_app.is_running():
    # The world.step() function performs one step of the physics simulation
    # and renders a new frame to the viewport.
    world.step(render=True)

# This line is reached when the simulation window is closed.
# It ensures a clean shutdown of the simulator.
simulation_app.close()
