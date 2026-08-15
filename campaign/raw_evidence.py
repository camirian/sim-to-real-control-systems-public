"""Per-run raw evidence packets — the campaign's primary record.

REQ-S2R-102. The graded packet (:mod:`gauntlet.evidence`) records the four
certification metrics and their verdicts. It is a *derived* artifact. This
module defines the record it is derived FROM: everything the run actually did,
including the parts that make it look bad.

Design rules, each aimed at a specific way a campaign can lie to itself:

- **A run that fails is still a record.** ``status`` distinguishes ``valid``
  from ``failed``/``invalid``, and an invalid run carries an exact
  ``failure_reason``. Nothing is deleted for looking wrong; the aggregate
  reports the denominator it actually had.
- **Rate evidence travels with every run.** The 200 Hz measurement taken once
  at preflight does not stay true by assumption, so each packet carries its own
  inter-sample statistics and its own tolerance verdict.
- **The truth stream is preserved separately from the estimate.** The
  controller consumes a disturbed (and possibly filtered) estimate; the
  articulation has a true position. Keeping both is what allows the difference
  between "the controller thinks it is tracking" and "it is tracking" to be
  reported rather than assumed away.
- **File hashes are recorded in the packet**, so a committed evidence tree can
  be verified offline by a public clone with no simulator.

Pure Python — no ROS, no Isaac, no NumPy. Written by the Isaac driver, read by
the aggregator and the tests.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from campaign.errors import CampaignError

SCHEMA_VERSION = 1

#: A run counted in the primary comparison.
STATUS_VALID = "valid"
#: A run that executed but violated the frozen contract (rate drift, short
#: record, failed reset). Reported, never replaced.
STATUS_INVALID = "invalid"
#: A run that could not execute at all (harness exception).
STATUS_FAILED = "failed"
_STATUSES = (STATUS_VALID, STATUS_INVALID, STATUS_FAILED)

_REQUIRED = (
    "schema_version",
    "run_id",
    "condition",
    "seed",
    "scenario",
    "campaign_id",
    "campaign_version",
    "manifest_sha256",
    "execution_position",
    "status",
    "failure_reason",
    "start_state",
    "reset",
    "rate",
    "controller",
    "signals_summary",
    "runtime",
    "files",
)


def _finite_or_none(value: Optional[float]) -> Optional[float]:
    """JSON-safe float: ``inf``/``nan`` become the strings JSON can carry."""
    if value is None:
        return None
    v = float(value)
    if math.isinf(v):
        return "inf" if v > 0 else "-inf"
    if math.isnan(v):
        return "nan"
    return v


def build_raw_packet(
    run_id: str,
    condition: str,
    seed: int,
    scenario: str,
    campaign_id: str,
    campaign_version: int,
    manifest_sha256: str,
    execution_position: int,
    status: str,
    start_state: Dict[str, Any],
    reset: Dict[str, Any],
    rate: Dict[str, Any],
    controller: Dict[str, Any],
    signals_summary: Dict[str, Any],
    runtime: Dict[str, Any],
    files: Dict[str, str],
    failure_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble one run's raw packet; raises :class:`CampaignError` if invalid."""
    packet = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "condition": condition,
        "seed": int(seed),
        "scenario": scenario,
        "campaign_id": campaign_id,
        "campaign_version": int(campaign_version),
        "manifest_sha256": manifest_sha256,
        "execution_position": int(execution_position),
        "status": status,
        "failure_reason": failure_reason,
        "start_state": start_state,
        "reset": reset,
        "rate": rate,
        "controller": controller,
        "signals_summary": signals_summary,
        "runtime": runtime,
        "files": dict(sorted(files.items())),
    }
    validate_raw_packet(packet)
    return packet


def validate_raw_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Structural validation with the fail-closed rules the campaign relies on."""
    if not isinstance(packet, dict):
        raise CampaignError(
            f"raw packet must be an object, got {type(packet).__name__}"
        )
    missing = [k for k in _REQUIRED if k not in packet]
    if missing:
        raise CampaignError(f"raw packet missing required fields: {missing}")
    if packet["schema_version"] != SCHEMA_VERSION:
        raise CampaignError(
            f"unsupported raw packet schema_version {packet['schema_version']!r}"
        )
    if packet["status"] not in _STATUSES:
        raise CampaignError(
            f"raw packet status must be one of {_STATUSES}, got {packet['status']!r}"
        )
    if packet["condition"] not in ("filtered", "unfiltered"):
        raise CampaignError(f"unknown condition {packet['condition']!r}")
    if not isinstance(packet["seed"], int) or isinstance(packet["seed"], bool):
        raise CampaignError("raw packet seed must be an integer")

    # A non-valid run MUST say why. An unexplained exclusion is exactly the
    # shape a quietly-dropped inconvenient run would take.
    if packet["status"] != STATUS_VALID and not packet["failure_reason"]:
        raise CampaignError(
            f"run {packet['run_id']} has status {packet['status']!r} but no "
            "failure_reason; every exclusion must carry its exact reason"
        )
    if packet["status"] == STATUS_VALID and packet["failure_reason"]:
        raise CampaignError(
            f"run {packet['run_id']} is valid but carries failure_reason "
            f"{packet['failure_reason']!r}"
        )

    # The rate verdict must be derivable, so a packet cannot claim a run was
    # in-tolerance while carrying a measurement that was not.
    rate = packet["rate"]
    for key in ("measured_hz", "target_hz", "tolerance_frac", "within_tolerance"):
        if key not in rate:
            raise CampaignError(f"raw packet rate block missing {key!r}")
    measured, target = rate["measured_hz"], rate["target_hz"]
    if isinstance(measured, (int, float)) and measured > 0:
        derived = abs(measured - target) / target <= rate["tolerance_frac"]
        if bool(rate["within_tolerance"]) != derived:
            raise CampaignError(
                f"run {packet['run_id']}: rate.within_tolerance="
                f"{rate['within_tolerance']} contradicts measured_hz={measured} "
                f"vs target {target} ±{rate['tolerance_frac']:.1%}"
            )
        # A valid run cannot have drifted outside the frozen tolerance.
        if packet["status"] == STATUS_VALID and not derived:
            raise CampaignError(
                f"run {packet['run_id']} is marked valid but its measured rate "
                f"{measured} Hz is outside the frozen tolerance"
            )
    return packet


def dumps_raw_packet(packet: Dict[str, Any]) -> str:
    """Deterministic serialization (sorted keys, LF EOL)."""
    validate_raw_packet(packet)
    return json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_raw_packet(packet: Dict[str, Any], path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_raw_packet(packet), encoding="utf-8")
    return path


def load_raw_packet(path) -> Dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise CampaignError(f"raw evidence packet not found: {path}")
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise CampaignError(f"corrupt raw evidence packet {path}: {e}") from e
    return validate_raw_packet(packet)


def rate_stats(t: Sequence[float]) -> Dict[str, Any]:
    """Inter-sample statistics for one run's simulated timestamps.

    ``measured_hz`` uses the MEAN interval rather than ``n/span`` so a single
    dropped sample shows up as an inflated interval instead of being averaged
    invisibly into the span.
    """
    t = [float(x) for x in t]
    if len(t) < 2:
        return {
            "n_samples": len(t),
            "measured_hz": None,
            "dt_mean_s": None,
            "dt_stdev_s": None,
            "dt_min_s": None,
            "dt_max_s": None,
            "span_s": 0.0,
            "monotonic": True,
        }
    d = [b - a for a, b in zip(t, t[1:])]
    n = len(d)
    mean = sum(d) / n
    var = sum((x - mean) ** 2 for x in d) / (n - 1) if n > 1 else 0.0
    return {
        "n_samples": len(t),
        "measured_hz": (1.0 / mean) if mean > 0 else None,
        "dt_mean_s": mean,
        "dt_stdev_s": math.sqrt(var),
        "dt_min_s": min(d),
        "dt_max_s": max(d),
        "span_s": t[-1] - t[0],
        "monotonic": all(x > 0 for x in d),
    }


def summarize_signals(
    reference: Sequence[float],
    measured: Sequence[float],
    noisy: Sequence[float],
    true_position: Sequence[float],
    command: Sequence[float],
) -> Dict[str, Any]:
    """Secondary diagnostics computed from the run's own arrays.

    ``tracking`` is estimate-vs-reference — what the graded metrics score, and
    what the controller could actually see. ``true_tracking`` is
    articulation-vs-reference: the physical outcome, which the controller does
    NOT observe. Reporting both is the difference between "the filter made the
    number better" and "the filter made the robot better"; they are not the
    same claim and this campaign should not be able to conflate them.
    """
    def _rms(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
        if not a or len(a) != len(b):
            return None
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))

    def _peak(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
        if not a or len(a) != len(b):
            return None
        return max(abs(x - y) for x, y in zip(a, b))

    return {
        "n_rows": len(reference),
        "tracking_rms_error_rad": _finite_or_none(_rms(measured, reference)),
        "peak_tracking_error_rad": _finite_or_none(_peak(measured, reference)),
        "true_tracking_rms_error_rad": _finite_or_none(_rms(true_position, reference)),
        "true_peak_tracking_error_rad": _finite_or_none(_peak(true_position, reference)),
        "noisy_rms_error_rad": _finite_or_none(_rms(noisy, reference)),
        "reference_span_rad": _finite_or_none(
            (max(reference) - min(reference)) if reference else None
        ),
        "command_min_rad": _finite_or_none(min(command) if command else None),
        "command_max_rad": _finite_or_none(max(command) if command else None),
    }


def integrity_index(packets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll every packet's file hashes into one verifiable index."""
    entries = {}
    for p in packets:
        for name, digest in p["files"].items():
            entries[f"{p['run_id']}/{name}"] = digest
    return {
        "schema_version": SCHEMA_VERSION,
        "n_runs": len(packets),
        "n_files": len(entries),
        "files": dict(sorted(entries.items())),
    }


def verify_integrity(index: Dict[str, Any], logs_root) -> Dict[str, Any]:
    """Re-hash every indexed file on disk and report mismatches exactly.

    Runs offline with no simulator, which is the whole point: a public clone
    must be able to check that the committed evidence is the evidence the
    campaign produced.
    """
    from campaign.manifest import file_sha256

    logs_root = Path(logs_root)
    ok, mismatched, missing = [], [], []
    for rel, expected in index["files"].items():
        path = logs_root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        actual = file_sha256(path)
        (ok if actual == expected else mismatched).append(rel)
    return {
        "checked": len(index["files"]),
        "ok": len(ok),
        "mismatched": sorted(mismatched),
        "missing": sorted(missing),
        "passed": not mismatched and not missing,
    }
