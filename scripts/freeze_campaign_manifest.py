"""Freeze the campaign manifest. Run ONCE, before the first empirical run.

    python scripts/freeze_campaign_manifest.py

Writes ``campaign/manifests/<campaign_id>-v<version>.json``, hashed over its own
body. Refuses to overwrite an existing manifest: a frozen design is a record,
not a file you regenerate when something turns out inconvenient. To change the
design, bump ``CAMPAIGN_VERSION`` — which makes the change a new experiment
rather than an edit to a running one.

No Isaac and no ROS: the manifest is pure preregistration, so it can be frozen,
hashed, and reviewed on any machine before the simulator is ever touched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dsp"))
sys.path.insert(0, str(REPO / "ros2-ws" / "src" / "control_loop"))

from campaign.manifest import (  # noqa: E402
    CAMPAIGN_ID,
    CAMPAIGN_VERSION,
    build_manifest,
    write_manifest,
)
from gauntlet.evidence import environment_versions  # noqa: E402
from scenes.scene_contract import graph_fingerprint  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-commit", required=True,
                    help="commit of the harness code the campaign will run")
    ap.add_argument("--runtime-parent", required=True,
                    help="head of the runtime-validation branch this stacks on")
    ap.add_argument("--isaac-build", required=True)
    ap.add_argument("--out-dir", default=str(REPO / "campaign" / "manifests"))
    ap.add_argument("--force", action="store_true",
                    help="allow overwrite (only for pre-freeze dry runs)")
    args = ap.parse_args()

    scene = REPO / "scenes" / "franka_ros2_bridge_scene.usd"
    fingerprint = graph_fingerprint(scene)

    manifest = build_manifest(
        repo_commit=args.repo_commit,
        runtime_parent_commit=args.runtime_parent,
        scene_graph_fingerprint=fingerprint,
        isaac_build=args.isaac_build,
        environment=environment_versions(),
    )

    out = Path(args.out_dir) / f"{CAMPAIGN_ID}-v{CAMPAIGN_VERSION}.json"
    if out.exists() and not args.force:
        print(f"REFUSING to overwrite frozen manifest {out}\n"
              f"A frozen design is a record. Bump CAMPAIGN_VERSION instead.",
              file=sys.stderr)
        return 2

    write_manifest(manifest, out)
    print(f"scene graph fingerprint : {fingerprint}")
    print(f"manifest sha256         : {manifest['manifest_sha256']}")
    print(f"scheduled runs          : {manifest['design']['scheduled_runs']}")
    print(f"seeds                   : {manifest['design']['seeds']}")
    print(f"written                 : {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
