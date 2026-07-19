"""Tests for gauntlet.report (REQ-S2R-101): golden-file the report."""

from pathlib import Path

import pytest

from gauntlet.checks import CheckResult, CheckStatus
from gauntlet.errors import GauntletError
from gauntlet.evidence import build_packet
from gauntlet.report import render_report, write_report

GOLDEN = Path(__file__).parent / "golden" / "run-golden-0001.md"

# Fully pinned packet: no environment reads, no wall clock — reproducible
# byte-for-byte forever.
FIXED_ENV = {
    "python": "3.10.12",
    "numpy": "1.26.4",
    "scipy": "1.11.4",
    "s2r_dsp": "0.1.0",
    "gauntlet": "0.1.0",
}
FIXED_THRESHOLDS = {
    "tracking_rms_error_max": 0.15,
    "settling_time_max_s": 2.0,
    "settling_band_rad": 0.2,
    "overshoot_max_pct": 25.0,
    "filter_attenuation_min_db": 20.0,
    "vibration_band_hz": 25.0,
    "vibration_band_halfwidth_hz": 2.0,
}


def golden_packet():
    return build_packet(
        run_id="golden-0001",
        scenario="franka-joint-tracking-synthetic",
        seed=42,
        checks=[
            CheckResult(
                "tracking_rms_error", 0.0912, 0.15, "<=", CheckStatus.PASSED,
                "RMS of measured-vs-reference joint position (rad)",
            ),
            CheckResult(
                "settling_time_s", 0.115, 2.0, "<=", CheckStatus.PASSED,
                "time to stay within ±0.2 rad of reference",
            ),
            CheckResult(
                "overshoot_pct", 10.26, 25.0, "<=", CheckStatus.PASSED,
                "worst |error| as % of reference span",
            ),
            CheckResult(
                "filter_attenuation_db", 33.6, 20.0, ">=", CheckStatus.PASSED,
                "band-power drop noisy->measured at 25.0±2.0 Hz",
            ),
        ],
        thresholds=FIXED_THRESHOLDS,
        environment=FIXED_ENV,
        generated_at="2026-07-19T00:00:00Z",
    )


class TestGolden:
    def test_report_matches_golden_file(self):
        rendered = render_report(golden_packet())
        assert rendered == GOLDEN.read_text(encoding="utf-8")

    def test_render_is_deterministic(self):
        assert render_report(golden_packet()) == render_report(golden_packet())


class TestContent:
    def test_failing_packet_reports_failed_verdict(self):
        p = build_packet(
            run_id="fail-0001",
            scenario="s",
            seed=7,
            checks=[
                CheckResult("tracking_rms_error", 0.236, 0.15, "<=", CheckStatus.FAILED),
                CheckResult("settling_time_s", float("inf"), 2.0, "<=", CheckStatus.FAILED),
            ],
            thresholds=FIXED_THRESHOLDS,
            environment=FIXED_ENV,
        )
        report = render_report(p)
        assert "**Verdict: FAILED**" in report
        assert "| tracking_rms_error | 0.236 | <= 0.15 | FAIL |" in report
        assert "| settling_time_s | inf | <= 2 | FAIL |" in report

    def test_skipped_check_reports_skip_with_dash_value(self):
        p = build_packet(
            run_id="skip-0001",
            scenario="s",
            seed=7,
            checks=[
                CheckResult("tracking_rms_error", 0.01, 0.15, "<=", CheckStatus.PASSED),
                CheckResult("filter_attenuation_db", None, 20.0, ">=", CheckStatus.SKIPPED),
            ],
            thresholds=FIXED_THRESHOLDS,
            environment=FIXED_ENV,
        )
        report = render_report(p)
        assert "| filter_attenuation_db | — | >= 20 | SKIP |" in report
        assert "**Verdict: PASSED**" in report

    def test_unrecorded_timestamp_renders_placeholder(self):
        p = golden_packet()
        p = dict(p, generated_at=None)
        assert "Generated at: not recorded" in render_report(p)

    def test_invalid_packet_is_refused(self):
        with pytest.raises(GauntletError, match="missing required fields"):
            render_report({"run_id": "x"})

    def test_write_report_path(self, tmp_path):
        path = write_report(golden_packet(), tmp_path)
        assert path.name == "run-golden-0001.md"
        assert path.read_text(encoding="utf-8") == render_report(golden_packet())
