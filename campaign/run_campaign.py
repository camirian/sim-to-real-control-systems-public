"""Orchestrate the seeded filtered-vs-unfiltered campaign (REQ-S2R-102).

One command, on the EdgeXpert, that turns a seed list into the money table:

    for each seed s:
        run UNFILTERED  (filter bypassed) -> logs/unfiltered-<s>/telemetry.csv
        run FILTERED    (dsp_filter live) -> logs/filtered-<s>/telemetry.csv
    for each run dir:  python -m gauntlet.cli <dir> --evidence-dir evidence/
    python -m campaign.cli evidence/ --out-dir evidence/   -> results_table.md

The two kinds of work in this file are deliberately separated:

* **Pure glue (real, tested here):** the campaign PLAN (which runs to do, with
  which run ids and launch arguments), the exact ``ros2 launch`` / ``gauntlet``
  / ``campaign`` command lines, and the aggregation invocation. None of this
  needs ROS or Isaac, so it is unit-tested in ``campaign/test``.

* **Live-sim execution (EDGEXPERT-VERIFY, py_compile-gated only):**
  :func:`run_one` and :func:`main` actually spawn ``ros2 launch`` against a
  running Isaac scene and record a rosbag/CSV. Nothing below the EDGEXPERT
  markers has been executed anywhere — it is authored in the cloud sandbox and
  only syntax-checked. Do not claim a campaign ran until it has run on the
  EdgeXpert per docs/RUN_ON_EDGEXPERT.md.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

# Default two-condition sweep. "unfiltered" bypasses the dsp_filter node so the
# controller consumes /joint_states_noisy directly; "filtered" runs the causal
# filter in-loop (the only DSP path allowed in-loop, AGENTS.md §2).
CONDITIONS = ("unfiltered", "filtered")
DEFAULT_LAUNCH_FILE = "control_loop closed_loop.launch.py"
DEFAULT_SCENARIO = "franka-joint-tracking"


@dataclass(frozen=True)
class RunSpec:
    """One planned run: its condition, seed, run id, and launch overrides."""

    condition: str
    seed: int
    run_id: str
    filter_enabled: bool

    @property
    def log_dir_name(self) -> str:
        return self.run_id


def plan_campaign(
    seeds: Sequence[int], conditions: Sequence[str] = CONDITIONS
) -> List[RunSpec]:
    """Expand a seed list into the ordered list of runs (pure, deterministic).

    Run ids follow the ``<condition>-<seed:04d>`` convention the aggregator
    classifies by (see :func:`campaign.aggregate.classify_condition`).
    """
    if not seeds:
        raise ValueError("campaign needs at least one seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"duplicate seeds in {list(seeds)}")
    specs: List[RunSpec] = []
    for seed in seeds:
        for cond in conditions:
            if cond not in ("filtered", "unfiltered"):
                raise ValueError(f"unknown condition {cond!r}")
            specs.append(
                RunSpec(
                    condition=cond,
                    seed=int(seed),
                    run_id=f"{cond}-{int(seed):04d}",
                    filter_enabled=(cond == "filtered"),
                )
            )
    return specs


def launch_command(
    spec: RunSpec,
    launch_file: str = DEFAULT_LAUNCH_FILE,
    extra_args: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Build the ``ros2 launch`` argv for one run (pure string assembly).

    The unfiltered condition sets ``filter_kind:=passthrough`` so the launch
    keeps identical topology and only the filter behavior differs. (The
    passthrough kind is an EDGEXPERT-VERIFY item in the dsp_filter node — until
    it exists on the sim box, run unfiltered by pointing the controller's
    ``input_topic`` at ``/joint_states_noisy`` via ``extra_args``.)
    """
    args = {
        "seed": str(spec.seed),
        "filter_kind": "iir" if spec.filter_enabled else "passthrough",
    }
    if extra_args:
        args.update({k: str(v) for k, v in extra_args.items()})
    argv = ["ros2", "launch", *launch_file.split()]
    argv += [f"{k}:={v}" for k, v in args.items()]
    return argv


def gauntlet_command(log_dir, evidence_dir, timestamp: Optional[str] = None) -> List[str]:
    """Build the ``python -m gauntlet.cli`` argv that grades one run's logs."""
    argv = [
        sys.executable, "-m", "gauntlet.cli", str(log_dir),
        "--evidence-dir", str(evidence_dir),
    ]
    if timestamp:
        argv += ["--timestamp", timestamp]
    return argv


def aggregate_command(evidence_dir, out_dir=None, timestamp: Optional[str] = None) -> List[str]:
    """Build the ``python -m campaign.cli`` argv that renders the money table."""
    argv = [sys.executable, "-m", "campaign.cli", str(evidence_dir)]
    if out_dir is not None:
        argv += ["--out-dir", str(out_dir)]
    if timestamp:
        argv += ["--timestamp", timestamp]
    return argv


# --------------------------------------------------------------------------- #
# EDGEXPERT-VERIFY below this line — live-sim execution, py_compile-gated only.
# --------------------------------------------------------------------------- #


def run_one(spec: RunSpec, logs_root: Path, launch_file: str, steps: int) -> Path:  # pragma: no cover
    """Execute one live closed-loop run and return its log directory.

    EDGEXPERT-VERIFY: this spawns ``ros2 launch`` against an already-running
    Isaac scene (scripts/run_franka_headless.py) and records the loop topics to
    ``<logs_root>/<run_id>/telemetry.csv`` in the gauntlet's run-log layout.
    NONE of this has been executed — Isaac + ROS 2 Humble are required and live
    only on the EdgeXpert. The rosbag->CSV export convention
    (t,reference,measured[,noisy]) must be confirmed there.
    """
    import subprocess  # local import: never needed for the pure-glue path

    log_dir = logs_root / spec.log_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)
    argv = launch_command(spec, launch_file)
    # EDGEXPERT-VERIFY: launch lifecycle — how the run is bounded (fixed step
    # count vs. controller "DONE") and how topics are captured to telemetry.csv
    # is sim-box work. Placeholder invocation; adjust to the real bag pipeline.
    print(f"[EDGEXPERT-VERIFY] would run: {' '.join(argv)}  (steps={steps})")
    subprocess.run(argv, check=True)
    return log_dir


def main(argv: Optional[Sequence[str]] = None) -> int:  # pragma: no cover
    """Full campaign entry point (EDGEXPERT-VERIFY — runs the sim)."""
    import argparse
    import subprocess

    parser = argparse.ArgumentParser(
        prog="python -m campaign.run_campaign",
        description="Run the seeded filtered-vs-unfiltered campaign end to end "
        "on the EdgeXpert and render the money table (REQ-S2R-102).",
    )
    parser.add_argument("--seeds", type=int, nargs="+", required=True,
                        help="seed list (>=20 per condition recommended, REQ-S2R-102)")
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--evidence-dir", default="evidence")
    parser.add_argument("--launch-file", default=DEFAULT_LAUNCH_FILE)
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--timestamp", default=None)
    args = parser.parse_args(argv)

    specs = plan_campaign(args.seeds)
    logs_root = Path(args.logs_root)
    evidence_dir = Path(args.evidence_dir)

    # EDGEXPERT-VERIFY: the loop below drives the sim. The command builders it
    # calls are the same ones the unit tests cover, but the subprocess.run of
    # the ROS launch has never executed outside the EdgeXpert.
    for spec in specs:
        log_dir = run_one(spec, logs_root, args.launch_file, args.steps)
        subprocess.run(
            gauntlet_command(log_dir, evidence_dir, args.timestamp), check=True
        )
    return subprocess.run(
        aggregate_command(evidence_dir, evidence_dir, args.timestamp)
    ).returncode


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
