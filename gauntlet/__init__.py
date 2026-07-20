"""gauntlet — the certification gauntlet (M3, REQ-S2R-100/101).

Grades logged closed-loop runs into JSON evidence packets
(``evidence/run-<id>.json``) and markdown compliance reports.

Provenance: the evidence-packet concept is ported from the author's archived
``camirian/sim-to-real-benchmarking`` repository (per MASTER_PLAN §2/M3).
That repo was not reachable from the cloud sandbox where this port was
authored (private/archived; access denied), so this is a clean-room
re-implementation of the concept as specified in MASTER_PLAN REQ-S2R-100/101
— seeded per-run JSON packets with per-check pass/fail plus a rendered
markdown compliance report — not a line-for-line vendoring.

Everything here is pure Python/NumPy: no ROS, no Isaac. Inputs are logged
run data (CSV exported from rosbag or the campaign runner); determinism is
absolute — timestamps enter a packet only via an explicit argument.
"""

from gauntlet.checks import CheckResult, CheckStatus, run_checks
from gauntlet.errors import GauntletError
from gauntlet.evidence import build_packet, load_packet, validate_packet, write_packet
from gauntlet.report import render_report

__version__ = "0.1.0"

__all__ = [
    "CheckResult",
    "CheckStatus",
    "GauntletError",
    "build_packet",
    "load_packet",
    "validate_packet",
    "write_packet",
    "render_report",
    "run_checks",
    "__version__",
]
