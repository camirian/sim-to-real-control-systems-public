# add_prims.py
import numpy as np
from isaacsim import SimulationApp

# Configuration for the simulation app
CONFIG = {"headless": False}

# Instantiate the SimulationApp
# This must be done before any other omniverse imports
simulation_app = SimulationApp(CONFIG)

# Import core Isaac Sim APIs after the app has been initialized
from omni.isaac.core import World
from omni.isaac.core.objects import DynamicCuboid

# Create a World object
world = World(stage_units_in_meters=1.0)

# Add a ground plane to the scene
world.scene.add_default_ground_plane()

# Add a dynamic cube to the scene
# prim_path: The unique path in the USD stage hierarchy
# name: A unique name to retrieve this object from the scene later
# position: The initial position in meters
# color: The RGB color of the cube
fancy_cube = world.scene.add(
    DynamicCuboid(
        prim_path="/World/random_cube",
        name="fancy_cube",
        position=np.array([0, 0, 1.0]),
        scale=np.array([0.5, 0.5, 0.5]),
        color=np.array([0.0, 0.0, 1.0]), # Blue
    )
)

# Reset the world to ensure all objects are initialized correctly
world.reset()

# Main simulation loop
# This loop will run until the simulation is stopped
while simulation_app.is_running():
    # The world.step() function advances the physics simulation by one step
    # and renders the scene
    world.step(render=True)

# Cleanup
simulation_app.close()