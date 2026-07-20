"""Render a :class:`~campaign.aggregate.CampaignResult` to the two artifacts.

REQ-S2R-102 outputs:

- ``results.json`` — deterministic, machine-readable (sorted keys, fixed
  separators, ``inf`` encoded as the string ``"inf"`` so it stays strict JSON,
  trailing newline). Same serialization discipline as evidence packets.
- ``results_table.md`` — the commit-quality "money table": headline deltas, a
  per-condition summary, a metric-delta table, and a per-run detail table.

Both are pure functions of the result model plus the embedded ``generated_at``
string — no wall clock, no environment reads — so they golden-file cleanly.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from campaign import CONDITIONS, FILTERED, SCHEMA_VERSION, UNFILTERED, __version__
from campaign.aggregate import (
    METRIC_ORDER,
    METRIC_UNITS,
    CampaignResult,
    ConditionStats,
    MetricDelta,
    MetricStats,
)


def _jnum(value: Optional[float]):
    """JSON-safe number: ``inf`` -> ``"inf"``, else float (or None)."""
    if value is None:
        return None
    if math.isinf(value):
        return "inf"
    return float(value)


def _metric_stats_json(m: MetricStats) -> dict:
    return {
        "n_present": m.n_present,
        "n_finite": m.n_finite,
        "mean": _jnum(m.mean),
        "median": _jnum(m.median),
        "min": _jnum(m.minimum),
        "max": _jnum(m.maximum),
    }


def _condition_json(c: ConditionStats) -> dict:
    return {
        "n": c.n,
        "passed": c.passed,
        "pass_rate": c.pass_rate,
        "metrics": {name: _metric_stats_json(c.metrics[name]) for name in METRIC_ORDER},
    }


def _delta_json(d: MetricDelta) -> dict:
    return {
        "unfiltered_mean": _jnum(d.unfiltered_mean),
        "filtered_mean": _jnum(d.filtered_mean),
        "abs_improvement": _jnum(d.abs_improvement),
        "pct_improvement": _jnum(d.pct_improvement),
        "improved": d.improved,
        "note": d.note,
    }


def render_results_json(result: CampaignResult) -> str:
    """Serialize the result deterministically (sorted keys, LF EOL)."""
    doc = {
        "schema_version": SCHEMA_VERSION,
        "campaign_tool_version": __version__,
        "scenario": result.scenario,
        "generated_at": result.generated_at,
        "packets_found": result.n_packets_found,
        "packets_used": result.n_packets_used,
        "conditions": {
            cond: _condition_json(result.conditions[cond])
            for cond in CONDITIONS
            if cond in result.conditions
        },
        "deltas": {name: _delta_json(result.deltas[name]) for name in result.deltas},
        "headline": list(result.headline),
        "runs": [
            {
                "run_id": r.run_id,
                "condition": r.condition,
                "seed": r.seed,
                "overall_passed": r.overall_passed,
                "metrics": {k: _jnum(v) for k, v in r.metrics.items()},
            }
            for r in result.runs
        ],
        "warnings": list(result.warnings),
    }
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _fmt(value: Optional[float], places: int = 4) -> str:
    if value is None:
        return "—"
    if math.isinf(value):
        return "inf"
    return f"{value:.{places}g}"


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def render_results_table(result: CampaignResult) -> str:
    """Render the money table (REQ-S2R-102) as commit-quality markdown."""
    lines = [
        "# Campaign results — filtered vs unfiltered (REQ-S2R-102)",
        "",
        f"- Scenario: `{result.scenario}`",
        f"- Generated at: {result.generated_at or 'not recorded'}",
        f"- Evidence packets: {result.n_packets_used} used"
        + (
            f" ({result.n_packets_found} found, "
            f"{result.n_packets_found - result.n_packets_used} skipped)"
            if result.n_packets_found != result.n_packets_used
            else ""
        ),
        "",
        "## Headline",
        "",
    ]
    lines += [f"- {h}" for h in result.headline] or ["- (no headline)"]

    # Per-condition summary.
    lines += [
        "",
        "## Per-condition summary",
        "",
        "| Condition | Runs | Pass rate | RMS mean (rad) | Settling mean (s) "
        "| Overshoot mean (%) | Attenuation mean (dB) |",
        "|---|---|---|---|---|---|---|",
    ]
    for cond in CONDITIONS:
        c = result.conditions.get(cond)
        if c is None:
            lines.append(f"| {cond} | 0 | — | — | — | — | — |")
            continue
        lines.append(
            f"| {cond} | {c.n} | {c.passed}/{c.n} ({c.pass_rate * 100:.0f}%) "
            f"| {_fmt(c.metrics['tracking_rms_error'].mean)} "
            f"| {_fmt(c.metrics['settling_time_s'].mean)} "
            f"| {_fmt(c.metrics['overshoot_pct'].mean)} "
            f"| {_fmt(c.metrics['filter_attenuation_db'].mean)} |"
        )

    # Metric deltas.
    lines += [
        "",
        "## Metric deltas (filtered vs unfiltered)",
        "",
        "Positive improvement = filtered is better. Percentages are signed and "
        "uncooked; a regression shows a negative improvement.",
        "",
        "| Metric | Unit | Unfiltered mean | Filtered mean | Improvement | Better? |",
        "|---|---|---|---|---|---|",
    ]
    if result.deltas:
        for name in METRIC_ORDER:
            d = result.deltas.get(name)
            if d is None:
                continue
            better = "—" if d.improved is None else ("yes" if d.improved else "NO")
            # dB is already logarithmic: report an absolute gap, not a percentage.
            if name == "filter_attenuation_db" and d.abs_improvement is not None:
                sign = "+" if d.abs_improvement >= 0 else ""
                improvement = f"{sign}{_fmt(d.abs_improvement)} dB"
            elif d.pct_improvement is not None:
                improvement = _fmt_pct(d.pct_improvement)
            else:
                improvement = d.note or "—"
            lines.append(
                f"| {name} | {METRIC_UNITS[name]} | {_fmt(d.unfiltered_mean)} "
                f"| {_fmt(d.filtered_mean)} | {improvement} | {better} |"
            )
    else:
        lines.append(
            "| — | — | — | — | both conditions required | — |"
        )

    # Per-run detail.
    lines += [
        "",
        "## Per-run detail",
        "",
        "| Run | Condition | Seed | Verdict | RMS | Settling | Overshoot | Attenuation |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in result.runs:
        verdict = "PASS" if r.overall_passed else "FAIL"
        lines.append(
            f"| {r.run_id} | {r.condition} | {r.seed} | {verdict} "
            f"| {_fmt(r.metrics.get('tracking_rms_error'))} "
            f"| {_fmt(r.metrics.get('settling_time_s'))} "
            f"| {_fmt(r.metrics.get('overshoot_pct'))} "
            f"| {_fmt(r.metrics.get('filter_attenuation_db'))} |"
        )

    if result.warnings:
        lines += ["", "## Warnings", ""]
        lines += [f"- {w}" for w in result.warnings]

    lines += [
        "",
        "---",
        "",
        "_Seeded, reproducible campaign — regenerate every packet from its seed "
        "and re-run `python -m campaign.cli` to reproduce this table "
        "(AGENTS.md §2)._",
        "",
    ]
    return "\n".join(lines)


def write_results(result: CampaignResult, out_dir) -> tuple[Path, Path]:
    """Write ``results_table.md`` and ``results.json``; returns their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    table_path = out_dir / "results_table.md"
    json_path = out_dir / "results.json"
    table_path.write_text(render_results_table(result), encoding="utf-8")
    json_path.write_text(render_results_json(result), encoding="utf-8")
    return table_path, json_path
