"""Synthesize gauntlet evidence packets for tests and the aggregator smoke test.

These packets are built by calling :mod:`gauntlet.evidence` and
:mod:`gauntlet.checks` directly — real ``CheckResult`` objects run through
:func:`gauntlet.evidence.build_packet` and :func:`write_packet`, never
hand-rolled JSON — so the fixtures exercise the exact packet format the
gauntlet emits and are validated on write.

They are SYNTHETIC and clearly labeled as such: they are NOT the real EdgeXpert
campaign results. Their only jobs are (1) to drive the campaign unit tests and
(2) to let a cloud/CI environment run the aggregator end to end (the "smoke
test" in docs/RUN_ON_EDGEXPERT.md) without ROS or Isaac.

Values are seeded-deterministic with a small per-seed jitter so that means and
medians differ meaningfully across runs while pass/fail verdicts stay stable.
The default profiles mirror the gauntlet's tuned margins (see
:data:`gauntlet.checks.DEFAULT_THRESHOLDS`): filtered runs pass every check;
unfiltered runs fail RMS, settling, overshoot, and attenuation.
"""

from __future__ import annotations

import math
from typing import Optional

from gauntlet.checks import DEFAULT_THRESHOLDS, CheckResult, CheckStatus
from gauntlet.evidence import build_packet, write_packet

SCENARIO = "franka-joint-tracking-synthetic"

# Fixed environment so synthesized packets serialize deterministically across
# machines (the real gauntlet fills these from the live interpreter).
_ENV = {
    "python": "3.10.0",
    "numpy": "1.26.0",
    "scipy": "1.11.0",
    "s2r_dsp": "0.1.0",
    "gauntlet": "0.1.0",
}

# Per-condition metric profiles: (base value, per-seed jitter step). Chosen to
# sit comfortably on the passing / failing side of DEFAULT_THRESHOLDS.
_PROFILES = {
    "filtered": {
        "tracking_rms_error": (0.090, 0.004),
        "settling_time_s": (0.120, 0.010),
        "overshoot_pct": (10.3, 0.6),
        "filter_attenuation_db": (33.6, 0.5),
    },
    "unfiltered": {
        "tracking_rms_error": (0.236, 0.006),
        "settling_time_s": (math.inf, 0.0),  # never settles
        "overshoot_pct": (34.5, 0.8),
        "filter_attenuation_db": (0.05, 0.02),
    },
}

_COMPARATORS = {
    "tracking_rms_error": ("<=", "tracking_rms_error_max"),
    "settling_time_s": ("<=", "settling_time_max_s"),
    "overshoot_pct": ("<=", "overshoot_max_pct"),
    "filter_attenuation_db": (">=", "filter_attenuation_min_db"),
}


def _status(name: str, value: float, threshold: float, comparator: str) -> CheckStatus:
    ok = value <= threshold if comparator == "<=" else value >= threshold
    return CheckStatus.PASSED if ok else CheckStatus.FAILED


def _jitter(base: float, step: float, seed: int) -> float:
    if math.isinf(base) or step == 0.0:
        return base
    # Deterministic zig-zag in [-2,2]*step; keeps mean≈base, median≠mean.
    return base + step * ((seed % 5) - 2)


def make_packet(
    condition: str,
    seed: int,
    *,
    index: Optional[int] = None,
    generated_at: Optional[str] = None,
    overrides: Optional[dict] = None,
) -> dict:
    """Build one synthetic evidence packet for ``condition`` at ``seed``.

    ``overrides`` maps metric name -> value to force specific numbers (used by
    the adversarial "filtered does not beat unfiltered" test). The run id is
    ``<condition>-<index or seed, zero-padded>`` so the aggregator classifies it
    by prefix.
    """
    if condition not in _PROFILES:
        raise ValueError(f"unknown condition {condition!r}")
    profile = _PROFILES[condition]
    overrides = overrides or {}
    n = index if index is not None else seed
    run_id = f"{condition}-{n:04d}"

    checks = []
    for name in ("tracking_rms_error", "settling_time_s", "overshoot_pct",
                 "filter_attenuation_db"):
        base, step = profile[name]
        value = float(overrides[name]) if name in overrides else _jitter(base, step, seed)
        comparator, thr_key = _COMPARATORS[name]
        threshold = DEFAULT_THRESHOLDS[thr_key]
        checks.append(
            CheckResult(name, value, threshold, comparator,
                        _status(name, value, threshold, comparator), f"synthetic {condition}")
        )

    thresholds = {
        "tracking_rms_error_max": DEFAULT_THRESHOLDS["tracking_rms_error_max"],
        "settling_time_max_s": DEFAULT_THRESHOLDS["settling_time_max_s"],
        "overshoot_max_pct": DEFAULT_THRESHOLDS["overshoot_max_pct"],
        "filter_attenuation_min_db": DEFAULT_THRESHOLDS["filter_attenuation_min_db"],
    }
    return build_packet(
        run_id=run_id,
        scenario=SCENARIO,
        seed=seed,
        checks=checks,
        thresholds=thresholds,
        environment=_ENV,
        generated_at=generated_at,
    )


def write_campaign(
    evidence_dir,
    n_filtered: int,
    n_unfiltered: int,
    *,
    base_seed: int = 1,
    generated_at: Optional[str] = None,
) -> list:
    """Write ``n_filtered`` + ``n_unfiltered`` synthetic packets; return paths.

    Seeds run ``base_seed .. base_seed+n-1`` within each condition; the two
    conditions share seeds so the sweep is a paired filtered-vs-unfiltered
    comparison, exactly as the real campaign runs it.
    """
    paths = []
    for i in range(n_filtered):
        p = make_packet("filtered", base_seed + i, index=base_seed + i,
                        generated_at=generated_at)
        paths.append(write_packet(p, evidence_dir))
    for i in range(n_unfiltered):
        p = make_packet("unfiltered", base_seed + i, index=base_seed + i,
                        generated_at=generated_at)
        paths.append(write_packet(p, evidence_dir))
    return paths
