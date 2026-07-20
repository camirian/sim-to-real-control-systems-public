"""Gauntlet CLI: grade a logged run directory into evidence + report.

Usage (no ROS/Isaac required):

    python -m gauntlet.cli <log_dir> --evidence-dir evidence \
        [--report-dir evidence] [--timestamp 2026-07-19T00:00:00Z]

Outputs ``run-<id>.json`` (evidence packet, REQ-S2R-100) and ``run-<id>.md``
(compliance report, REQ-S2R-101). Deterministic: wall-clock time enters the
packet only via ``--timestamp``. Exit code 0 = graded and PASSED, 1 = graded
and FAILED, 2 = invalid input (no verdict emitted).
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from gauntlet.checks import DEFAULT_THRESHOLDS, run_checks
from gauntlet.errors import GauntletError
from gauntlet.evidence import build_packet, write_packet
from gauntlet.report import write_report
from gauntlet.run_log import load_run_log

EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_INVALID = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m gauntlet.cli",
        description="Grade one logged closed-loop run into an evidence packet "
        "and a markdown compliance report.",
    )
    parser.add_argument("log_dir", help="run log directory (run_meta.json + telemetry.csv)")
    parser.add_argument(
        "--evidence-dir",
        default="evidence",
        help="directory for run-<id>.json (default: evidence)",
    )
    parser.add_argument(
        "--report-dir",
        default=None,
        help="directory for run-<id>.md (default: same as --evidence-dir)",
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
        log = load_run_log(args.log_dir)
        thresholds = dict(DEFAULT_THRESHOLDS)
        if log.thresholds:
            thresholds.update(log.thresholds)
        checks = run_checks(
            log.t,
            log.reference,
            log.measured,
            noisy=log.noisy,
            thresholds=log.thresholds,
        )
        packet = build_packet(
            run_id=log.run_id,
            scenario=log.scenario,
            seed=log.seed,
            checks=checks,
            thresholds=thresholds,
            generated_at=args.timestamp,
        )
        packet_path = write_packet(packet, args.evidence_dir)
        report_path = write_report(
            packet, args.report_dir if args.report_dir else args.evidence_dir
        )
    except GauntletError as e:
        print(f"gauntlet: error: {e}", file=sys.stderr)
        return EXIT_INVALID

    verdict = "PASSED" if packet["overall_passed"] else "FAILED"
    print(f"run {log.run_id}: {verdict}")
    print(f"evidence: {packet_path}")
    print(f"report:   {report_path}")
    return EXIT_PASSED if packet["overall_passed"] else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
