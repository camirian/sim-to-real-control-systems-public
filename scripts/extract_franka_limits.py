"""Re-derive the Franka joint-limit table from the referenced Isaac asset.

This is the provenance tool behind
``control_loop.logic.franka_limits.FRANKA_JOINT_LIMITS_DEG``: it fetches the
Franka USD that ``scenes/franka_ros2_bridge_scene.usd`` references, reads
``physics:lowerLimit`` / ``physics:upperLimit`` off each revolute joint, and
compares them to the committed table.

    python scripts/extract_franka_limits.py            # print + verify
    python scripts/extract_franka_limits.py --json     # machine-readable

Requires `pip install usd-core` and **network access** to the Omniverse asset
CDN, which is why it is a script rather than a CI test: the offline guarantee
for a fresh clone (scenes/scene_contract.py) must not depend on a remote host.
Run it when bumping the pinned Isaac version to catch an asset whose limits
changed underneath the committed table.
"""

from __future__ import annotations

import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ros2-ws" / "src" / "control_loop"))

from control_loop.logic.franka_limits import FRANKA_JOINT_LIMITS_DEG  # noqa: E402

# The exact asset URL referenced by scenes/franka_ros2_bridge_scene.usd
# (visible in the scene's /Franka prim reference).
FRANKA_ASSET_URL = (
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/"
    "Assets/Isaac/4.5/Isaac/Robots/Franka/franka.usd"
)


def fetch_limits(url: str = FRANKA_ASSET_URL) -> Dict[str, Tuple[float, float]]:
    """Download the asset and read every revolute joint's limits (degrees)."""
    from pxr import Usd

    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "franka.usd"
        with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310
            local.write_bytes(resp.read())
        # LoadNone: the asset references per-link geometry props we do not need
        # and cannot resolve from a bare download.
        stage = Usd.Stage.Open(str(local), load=Usd.Stage.LoadNone)
        out: Dict[str, Tuple[float, float]] = {}
        for prim in stage.Traverse():
            if str(prim.GetTypeName()) != "PhysicsRevoluteJoint":
                continue
            lo = prim.GetAttribute("physics:lowerLimit").Get()
            hi = prim.GetAttribute("physics:upperLimit").Get()
            if lo is None or hi is None:
                continue
            out[prim.GetName()] = (float(lo), float(hi))
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    import json
    import math

    parser = argparse.ArgumentParser(prog="python scripts/extract_franka_limits.py")
    parser.add_argument("--url", default=FRANKA_ASSET_URL)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    asset = fetch_limits(args.url)
    if args.json:
        print(json.dumps(asset, indent=2, sort_keys=True))

    mismatches = []
    for name, (lo_deg, hi_deg) in sorted(FRANKA_JOINT_LIMITS_DEG.items()):
        got = asset.get(name)
        status = "OK"
        if got is None:
            status = "MISSING FROM ASSET"
            mismatches.append(name)
        elif got != (lo_deg, hi_deg):
            status = f"DRIFTED (asset: {got})"
            mismatches.append(name)
        print(
            f"{name:14s} [{lo_deg:12.6f}, {hi_deg:12.6f}] deg  "
            f"= [{math.radians(lo_deg):9.6f}, {math.radians(hi_deg):9.6f}] rad  {status}"
        )

    extra = sorted(set(asset) - set(FRANKA_JOINT_LIMITS_DEG))
    if extra:
        print(f"\nrevolute joints in the asset but not in the table: {extra}")

    if mismatches:
        print(f"\nFAILED: committed table disagrees with the asset for {mismatches}")
        return 1
    print(f"\nOK: committed table matches {args.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
