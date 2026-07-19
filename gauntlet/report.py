"""Markdown compliance report rendered from an evidence packet (REQ-S2R-101).

Pure function of the packet dict — no wall clock, no environment reads — so
reports golden-file cleanly.
"""

from __future__ import annotations

from pathlib import Path

from gauntlet.checks import CheckStatus
from gauntlet.evidence import validate_packet

_STATUS_LABEL = {
    CheckStatus.PASSED.value: "PASS",
    CheckStatus.FAILED.value: "FAIL",
    CheckStatus.SKIPPED.value: "SKIP",
}


def _fmt_value(value) -> str:
    if value is None:
        return "—"
    if value == "inf":
        return "inf"
    return f"{float(value):.4g}"


def render_report(packet: dict) -> str:
    """Render one packet as a markdown compliance report."""
    validate_packet(packet)
    verdict = "PASSED" if packet["overall_passed"] else "FAILED"
    lines = [
        f"# Compliance report — run {packet['run_id']}",
        "",
        f"**Verdict: {verdict}**",
        "",
        f"- Scenario: `{packet['scenario']}`",
        f"- Seed: `{packet['seed']}`",
        f"- Schema version: {packet['schema_version']}",
        f"- Generated at: {packet['generated_at'] or 'not recorded'}",
        "",
        "## Checks",
        "",
        "| Check | Value | Threshold | Result |",
        "|---|---|---|---|",
    ]
    for c in packet["checks"]:
        label = _STATUS_LABEL[c["status"]]
        lines.append(
            f"| {c['name']} | {_fmt_value(c['value'])} | "
            f"{c['comparator']} {_fmt_value(c['threshold'])} | {label} |"
        )
    lines += ["", "## Environment", ""]
    for name, version in sorted(packet["environment"].items()):
        lines.append(f"- {name}: {version}")
    lines += [
        "",
        "## Thresholds",
        "",
    ]
    for name, value in sorted(packet["thresholds"].items()):
        lines.append(f"- {name}: {_fmt_value(value)}")
    lines += [
        "",
        "---",
        "",
        "_Seeded, reproducible run — regenerate this packet from the same seed",
        "and log to reproduce these numbers (AGENTS.md §2)._",
        "",
    ]
    return "\n".join(lines)


def write_report(packet: dict, report_dir) -> Path:
    """Write ``<report_dir>/run-<id>.md``; returns the path."""
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"run-{packet['run_id']}.md"
    path.write_text(render_report(packet), encoding="utf-8")
    return path
