import os
from glob import glob

from setuptools import find_packages, setup

package_name = "control_loop"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools", "numpy", "scipy", "s2r-dsp"],
    zip_safe=True,
    maintainer="Caaren Amirian",
    maintainer_email="153974602+camirian@users.noreply.github.com",
    description=(
        "Closed-loop nodes for the sim-to-real Franka demo: seeded noise "
        "injector, causal DSP filter node, joint-space waypoint controller "
        "(REQ-S2R-002..005)."
    ),
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "noise_injector = control_loop.noise_injector_node:main",
            "dsp_filter = control_loop.dsp_filter_node:main",
            "waypoint_controller = control_loop.waypoint_controller_node:main",
        ],
    },
)
