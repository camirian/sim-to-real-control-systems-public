"""Campaign aggregation CLI: evidence directory -> money table (REQ-S2R-102).

Usage (no ROS/Isaac required — pure Python over committed evidence packets):

    python -m campaign.cli <evidence_dir> --out-dir <dir> \
        [--timestamp 2026-07-19T00:00:00Z]

Reads every ``run-<id>.json`` under ``<evidence_dir>``, writes
``results_table.md`` and ``results.json`` into ``--out-dir`` (default: the
evidence directory itself). Deterministic: wall-clock time enters the outputs
only via ``--timestamp``.

Exit codes:
  0  aggregated; filtered beats unfiltered on tracking RMS (the headline claim)
  1  aggregated, but filtered does NOT beat unfiltered (honest: no cooked delta)
  2  invalid input (empty/absent dir, no usable packets) — no table emitted
"""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from campaign.aggregate import aggregate_directory
from campaign.errors import CampaignError
from campaign.render import write_results

EXIT_IMPROVED = 0
EXIT_NO_IMPROVEMENT = 1
EXIT_INVALID = 2


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m campaign.cli",
        description="Aggregate a directory of gauntlet evidence packets into "
        "the filtered-vs-unfiltered money table (REQ-S2R-102).",
    )
    parser.add_argument("evidence_dir", help="directory of run-<id>.json packets")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="output directory for results_table.md + results.json "
        "(default: the evidence directory)",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="ISO-8601 generated_at to embed; omitted -> null (deterministic)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = aggregate_directory(args.evidence_dir, generated_at=args.timestamp)
    except CampaignError as e:
        print(f"campaign: error: {e}", file=sys.stderr)
        return EXIT_INVALID

    out_dir = args.out_dir if args.out_dir else args.evidence_dir
    table_path, json_path = write_results(result, out_dir)

    for w in result.warnings:
        print(f"campaign: warning: {w}", file=sys.stderr)
    print(f"aggregated {result.n_packets_used} run(s) across "
          f"{len(result.conditions)} condition(s)")
    for line in result.headline:
        print(f"  {line}")
    print(f"table: {table_path}")
    print(f"json:  {json_path}")

    rms = result.deltas.get("tracking_rms_error")
    if rms is not None and rms.improved:
        return EXIT_IMPROVED
    return EXIT_NO_IMPROVEMENT


if __name__ == "__main__":
    sys.exit(main())
