"""Evidence packets: ``evidence/run-<id>.json`` (REQ-S2R-100).

A packet is the immutable record of one graded run: run id, seed, scenario,
thresholds, per-check results, environment versions, and overall verdict.
Committed packets are never edited (AGENTS.md §2) — regenerate under a new
run id instead.

Determinism: identical inputs serialize to identical bytes (sorted keys,
fixed separators, trailing newline). Wall-clock time never enters a packet
implicitly — ``generated_at`` is whatever ISO-8601 string the caller passes
(or null).
"""

from __future__ import annotations

import json
import platform
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from gauntlet.checks import CheckResult, CheckStatus
from gauntlet.errors import GauntletError

SCHEMA_VERSION = 1
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

REQUIRED_FIELDS = (
    "schema_version",
    "run_id",
    "scenario",
    "seed",
    "generated_at",
    "environment",
    "thresholds",
    "checks",
    "overall_passed",
)
_REQUIRED_CHECK_FIELDS = ("name", "value", "threshold", "comparator", "status")


def environment_versions() -> Dict[str, str]:
    """Versions of everything that shaped the numbers (REQ-S2R-100)."""
    import numpy
    import scipy

    import gauntlet
    import s2r_dsp

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "s2r_dsp": s2r_dsp.__version__,
        "gauntlet": gauntlet.__version__,
    }


def build_packet(
    run_id: str,
    scenario: str,
    seed: int,
    checks: Sequence[CheckResult],
    thresholds: Dict[str, float],
    environment: Optional[Dict[str, str]] = None,
    generated_at: Optional[str] = None,
) -> dict:
    """Assemble a packet dict; raises GauntletError on invalid inputs."""
    if not _RUN_ID_RE.match(run_id or ""):
        raise GauntletError(f"invalid run id: {run_id!r}")
    if not scenario:
        raise GauntletError("scenario must be a non-empty string")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise GauntletError(f"seed must be an int, got {type(seed).__name__}")
    checks = list(checks)
    if not checks:
        raise GauntletError("a packet must contain at least one check")
    packet = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "scenario": scenario,
        "seed": seed,
        "generated_at": generated_at,
        "environment": environment if environment is not None else environment_versions(),
        "thresholds": {k: float(v) for k, v in sorted(thresholds.items())},
        "checks": [c.to_dict() for c in checks],
        "overall_passed": all(c.status is not CheckStatus.FAILED for c in checks),
    }
    validate_packet(packet)
    return packet


def validate_packet(packet: dict) -> dict:
    """Validate packet structure; returns the packet or raises GauntletError."""
    if not isinstance(packet, dict):
        raise GauntletError(f"packet must be an object, got {type(packet).__name__}")
    missing = [f for f in REQUIRED_FIELDS if f not in packet]
    if missing:
        raise GauntletError(f"packet missing required fields: {missing}")
    if packet["schema_version"] != SCHEMA_VERSION:
        raise GauntletError(
            f"unsupported schema_version {packet['schema_version']!r} "
            f"(expected {SCHEMA_VERSION})"
        )
    checks = packet["checks"]
    if not isinstance(checks, list) or not checks:
        raise GauntletError("packet checks must be a non-empty list")
    statuses = {s.value for s in CheckStatus}
    for i, c in enumerate(checks):
        if not isinstance(c, dict):
            raise GauntletError(f"check #{i} is not an object")
        miss = [f for f in _REQUIRED_CHECK_FIELDS if f not in c]
        if miss:
            raise GauntletError(f"check #{i} missing fields: {miss}")
        if c["status"] not in statuses:
            raise GauntletError(f"check #{i} has invalid status {c['status']!r}")
    # The verdict must be derivable from the checks — a tampered packet with
    # failing checks but overall_passed=true is rejected, never trusted.
    derived = all(c["status"] != CheckStatus.FAILED.value for c in checks)
    if bool(packet["overall_passed"]) != derived:
        raise GauntletError(
            "packet overall_passed contradicts its checks "
            f"(stored={packet['overall_passed']}, derived={derived})"
        )
    return packet


def dumps_packet(packet: dict) -> str:
    """Deterministic serialization (sorted keys, fixed separators, LF EOL)."""
    validate_packet(packet)
    return json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_packet(packet: dict, evidence_dir) -> Path:
    """Write ``<evidence_dir>/run-<id>.json``; returns the path."""
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"run-{packet.get('run_id', 'unknown')}.json"
    path.write_text(dumps_packet(packet), encoding="utf-8")
    return path


def load_packet(path) -> dict:
    """Load and validate a packet file; raises GauntletError on any defect."""
    path = Path(path)
    if not path.is_file():
        raise GauntletError(f"evidence packet not found: {path}")
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise GauntletError(f"corrupt evidence packet {path}: {e}") from e
    return validate_packet(packet)
