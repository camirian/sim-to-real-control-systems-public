"""Aggregate a directory of gauntlet evidence packets into the money table.

REQ-S2R-102. Given a directory of ``run-<id>.json`` packets (the format
:func:`gauntlet.evidence.write_packet` emits), partition them into the
``filtered`` and ``unfiltered`` conditions, compute per-condition statistics
over the four graded metrics, and derive the headline filtered-vs-unfiltered
deltas.

Design decisions (all documented, all tested):

- **Packet validation** is delegated to :func:`gauntlet.evidence.load_packet`
  so packets are validated exactly as the gauntlet validates them. A tampered
  packet (failing checks but ``overall_passed=true``) is rejected there, never
  trusted here.
- **Condition classification** is by the leading token of the run id
  (``filtered-0001`` -> ``filtered``). The campaign runner
  (:mod:`campaign.run_campaign`) writes ids following this convention.
- **Malformed packets are SKIPPED WITH A WARNING**, not fatal: one corrupt file
  must not sink an otherwise-complete 40-run campaign. Every skip is recorded in
  ``CampaignResult.warnings`` and surfaced by the CLI and the rendered outputs,
  so a skip is always visible — never silent. A packet whose run id has no
  recognized condition prefix is skipped the same way.
- **Empty / all-skipped directories raise** :class:`CampaignError` — there is no
  honest table to render from zero runs.
- **``inf`` is preserved** end to end (an unfiltered run that never settles has
  ``settling_time_s = inf``); it is aggregated inf-aware and rendered as
  ``"inf"``.
- **Deltas are reported honestly**: improvement percentages are signed. A
  filtered set that does NOT beat unfiltered yields a negative improvement and
  an ``improved=False`` flag — the harness never cooks the delta.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from campaign import CONDITIONS, FILTERED, SCHEMA_VERSION, UNFILTERED
from campaign.errors import CampaignError
from gauntlet.errors import GauntletError
from gauntlet.evidence import load_packet

#: Metrics compared in the money table, in table order. Each maps to whether a
#: lower value is better (RMS/settling/overshoot) or a higher one is
#: (attenuation) — this drives the sign convention for deltas.
LOWER_IS_BETTER = {
    "tracking_rms_error": True,
    "settling_time_s": True,
    "overshoot_pct": True,
    "filter_attenuation_db": False,
}
METRIC_ORDER = (
    "tracking_rms_error",
    "settling_time_s",
    "overshoot_pct",
    "filter_attenuation_db",
)
#: Human units for rendering (documentation only; never affects the numbers).
METRIC_UNITS = {
    "tracking_rms_error": "rad",
    "settling_time_s": "s",
    "overshoot_pct": "%",
    "filter_attenuation_db": "dB",
}

_PACKET_GLOB = "run-*.json"


@dataclass(frozen=True)
class MetricStats:
    """Aggregate of one metric across the runs of one condition.

    ``n_present`` counts runs that recorded the metric (skipped checks are
    excluded); ``n_finite`` counts those with a finite value. ``mean`` is
    inf-aware: any inf sample makes the mean inf. All values are plain floats
    (``math.inf`` allowed) so the result serializes deterministically.
    """

    name: str
    n_present: int
    n_finite: int
    mean: Optional[float]
    median: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]


@dataclass(frozen=True)
class RunSummary:
    """Flat per-run view used for the detail table and JSON."""

    run_id: str
    condition: str
    seed: int
    overall_passed: bool
    metrics: Dict[str, Optional[float]]  # name -> value (None = skipped)


@dataclass(frozen=True)
class ConditionStats:
    n: int
    passed: int
    metrics: Dict[str, MetricStats]

    @property
    def pass_rate(self) -> float:
        return self.passed / self.n if self.n else 0.0


@dataclass(frozen=True)
class MetricDelta:
    """Filtered-vs-unfiltered comparison for one metric.

    Both improvement figures are signed and oriented so positive always means
    "filtered is better" regardless of metric direction; ``improved`` is the
    honest verdict.

    - ``abs_improvement`` — absolute filtered-vs-unfiltered gap in the metric's
      own unit, the natural figure for an already-logarithmic quantity like
      ``filter_attenuation_db`` (a percentage over dB is meaningless).
    - ``pct_improvement`` — percentage change, the natural figure for the
      linear lower-is-better metrics (RMS, settling, overshoot). ``None`` when
      undefined (zero baseline, or a non-finite mean — described in ``note``).
    """

    name: str
    unfiltered_mean: Optional[float]
    filtered_mean: Optional[float]
    abs_improvement: Optional[float]
    pct_improvement: Optional[float]
    improved: Optional[bool]
    note: str = ""


@dataclass
class CampaignResult:
    scenario: str
    generated_at: Optional[str]
    conditions: Dict[str, ConditionStats]
    deltas: Dict[str, MetricDelta]
    headline: List[str]
    runs: List[RunSummary]
    warnings: List[str] = field(default_factory=list)
    n_packets_found: int = 0
    n_packets_used: int = 0


# --------------------------------------------------------------------------- #
# Packet -> per-run extraction
# --------------------------------------------------------------------------- #


def _metric_value(check: dict) -> Optional[float]:
    """Extract a numeric metric value from a check dict (JSON -> float).

    Skipped checks carry ``value=None`` -> returned as ``None``. The gauntlet
    encodes non-finite values as the string ``"inf"`` -> returned as
    ``math.inf``.
    """
    value = check.get("value")
    if value is None:
        return None
    if value == "inf":
        return math.inf
    return float(value)


def classify_condition(run_id: str) -> Optional[str]:
    """Return the campaign condition for a run id, or ``None`` if unrecognized.

    The condition is the leading token before the first ``-``
    (``filtered-0007`` -> ``filtered``), matched case-insensitively against
    :data:`campaign.CONDITIONS`.
    """
    token = run_id.split("-", 1)[0].lower()
    return token if token in CONDITIONS else None


def _summarize_run(packet: dict) -> RunSummary:
    metrics = {c["name"]: _metric_value(c) for c in packet["checks"]}
    condition = classify_condition(packet["run_id"])
    assert condition is not None  # callers filter unrecognized ids first
    return RunSummary(
        run_id=packet["run_id"],
        condition=condition,
        seed=int(packet["seed"]),
        overall_passed=bool(packet["overall_passed"]),
        metrics=metrics,
    )


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #


def _mean(values: List[float]) -> float:
    if any(math.isinf(v) for v in values):
        # inf-aware: an unsettled run makes the mean settling time inf. Mixed
        # +inf/-inf would be nan; attenuation is the only "higher is better"
        # metric and its inf is always +inf, so this stays well-defined.
        return math.inf
    return sum(values) / len(values)


def _median(values: List[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    lo, hi = s[mid - 1], s[mid]
    if math.isinf(lo) or math.isinf(hi):
        # Averaging with inf: if both sides are inf -> inf; if only the upper
        # side is inf the true median is unbounded above -> report inf.
        return math.inf
    return (lo + hi) / 2.0


def _metric_stats(name: str, values: List[Optional[float]]) -> MetricStats:
    present = [v for v in values if v is not None]
    finite = [v for v in present if math.isfinite(v)]
    if not present:
        return MetricStats(name, 0, 0, None, None, None, None)
    return MetricStats(
        name=name,
        n_present=len(present),
        n_finite=len(finite),
        mean=_mean(present),
        median=_median(present),
        minimum=min(present),
        maximum=max(present),
    )


def _condition_stats(runs: List[RunSummary]) -> ConditionStats:
    metrics: Dict[str, MetricStats] = {}
    for name in METRIC_ORDER:
        values = [r.metrics.get(name) for r in runs]
        metrics[name] = _metric_stats(name, values)
    passed = sum(1 for r in runs if r.overall_passed)
    return ConditionStats(n=len(runs), passed=passed, metrics=metrics)


# --------------------------------------------------------------------------- #
# Deltas
# --------------------------------------------------------------------------- #


def _delta(name: str, unfiltered: ConditionStats, filtered: ConditionStats) -> MetricDelta:
    u = unfiltered.metrics[name].mean
    f = filtered.metrics[name].mean
    lower_better = LOWER_IS_BETTER[name]

    if u is None or f is None:
        return MetricDelta(name, u, f, None, None, None, "metric absent in one condition")

    # Handle the common unsettled-baseline case explicitly and honestly.
    if lower_better and math.isinf(u) and math.isfinite(f):
        return MetricDelta(
            name, u, f, None, None, True,
            "unfiltered never reaches the band (inf); filtered is finite",
        )
    if lower_better and math.isfinite(u) and math.isinf(f):
        return MetricDelta(
            name, u, f, None, None, False,
            "filtered never reaches the band (inf); unfiltered is finite",
        )
    if math.isinf(u) or math.isinf(f):
        improved = (f > u) if not lower_better else (f < u)
        return MetricDelta(name, u, f, None, None, improved, "non-finite mean(s)")

    if lower_better:
        improved = f < u
        abs_impr = u - f
        pct = (u - f) / u * 100.0 if u != 0 else None
    else:
        improved = f > u
        abs_impr = f - u
        pct = (f - u) / u * 100.0 if u != 0 else None

    note = "" if pct is not None else "baseline mean is zero; percentage undefined"
    return MetricDelta(name, u, f, abs_impr, pct, improved, note)


def _fmt_num(value: Optional[float], places: int = 4) -> str:
    if value is None:
        return "n/a"
    if math.isinf(value):
        return "inf"
    return f"{value:.{places}g}"


def _build_headline(
    conditions: Dict[str, ConditionStats], deltas: Dict[str, MetricDelta]
) -> List[str]:
    """One-line-per-claim headline, each phrased honestly from the numbers."""
    lines: List[str] = []
    filt = conditions.get(FILTERED)
    unf = conditions.get(UNFILTERED)
    if filt is None or unf is None:
        present = ", ".join(sorted(conditions)) or "none"
        lines.append(
            f"Incomplete comparison: only these conditions are present: {present}."
        )
        return lines

    lines.append(
        f"Overall pass rate: filtered {filt.passed}/{filt.n} "
        f"vs unfiltered {unf.passed}/{unf.n}."
    )

    rms = deltas.get("tracking_rms_error")
    if rms is not None and rms.pct_improvement is not None:
        arrow = "down" if rms.improved else "up"
        verb = "improvement" if rms.improved else "REGRESSION"
        lines.append(
            f"Tracking RMS: filtered {_fmt_num(rms.filtered_mean)} rad "
            f"vs unfiltered {_fmt_num(rms.unfiltered_mean)} rad "
            f"({arrow} {abs(rms.pct_improvement):.1f}% {verb})."
        )

    att = deltas.get("filter_attenuation_db")
    if att is not None and att.filtered_mean is not None and att.unfiltered_mean is not None:
        lines.append(
            f"Filter attenuation at the vibration band: filtered "
            f"{_fmt_num(att.filtered_mean)} dB vs unfiltered "
            f"{_fmt_num(att.unfiltered_mean)} dB."
        )

    st = deltas.get("settling_time_s")
    if st is not None:
        if st.note:
            lines.append(f"Settling time: {st.note}.")
        elif st.pct_improvement is not None:
            arrow = "down" if st.improved else "up"
            lines.append(
                f"Settling time: filtered {_fmt_num(st.filtered_mean)} s "
                f"vs unfiltered {_fmt_num(st.unfiltered_mean)} s "
                f"({arrow} {abs(st.pct_improvement):.1f}%)."
            )
    return lines


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def aggregate_directory(evidence_dir, generated_at: Optional[str] = None) -> CampaignResult:
    """Aggregate every ``run-*.json`` under ``evidence_dir`` into a table model.

    Raises :class:`CampaignError` if the directory is absent/empty or if no
    usable packet remains after skipping malformed / unclassifiable ones.
    ``generated_at`` is embedded verbatim (or null) — never read from the clock.
    """
    evidence_dir = Path(evidence_dir)
    if not evidence_dir.is_dir():
        raise CampaignError(f"evidence directory not found: {evidence_dir}")

    packet_paths = sorted(evidence_dir.glob(_PACKET_GLOB))
    if not packet_paths:
        raise CampaignError(f"no evidence packets ({_PACKET_GLOB}) in {evidence_dir}")

    warnings: List[str] = []
    runs: List[RunSummary] = []
    scenarios = set()

    for path in packet_paths:
        try:
            packet = load_packet(path)
        except GauntletError as e:
            warnings.append(f"skipped malformed packet {path.name}: {e}")
            continue
        if classify_condition(packet["run_id"]) is None:
            warnings.append(
                f"skipped {path.name}: run id {packet['run_id']!r} has no "
                f"recognized condition prefix (expected one of {list(CONDITIONS)})"
            )
            continue
        runs.append(_summarize_run(packet))
        scenarios.add(packet["scenario"])

    if not runs:
        raise CampaignError(
            f"no usable evidence packets in {evidence_dir} "
            f"({len(packet_paths)} found, all skipped — see warnings)"
        )
    if len(scenarios) > 1:
        warnings.append(
            f"packets span multiple scenarios {sorted(scenarios)}; "
            f"the comparison assumes a single scenario"
        )

    runs.sort(key=lambda r: (r.condition, r.run_id))
    conditions: Dict[str, ConditionStats] = {}
    for cond in CONDITIONS:
        cond_runs = [r for r in runs if r.condition == cond]
        if cond_runs:
            conditions[cond] = _condition_stats(cond_runs)

    deltas: Dict[str, MetricDelta] = {}
    if FILTERED in conditions and UNFILTERED in conditions:
        for name in METRIC_ORDER:
            deltas[name] = _delta(name, conditions[UNFILTERED], conditions[FILTERED])

    headline = _build_headline(conditions, deltas)

    return CampaignResult(
        scenario=sorted(scenarios)[0],
        generated_at=generated_at,
        conditions=conditions,
        deltas=deltas,
        headline=headline,
        runs=runs,
        warnings=warnings,
        n_packets_found=len(packet_paths),
        n_packets_used=len(runs),
    )
