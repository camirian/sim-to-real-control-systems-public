"""The campaign's sampling-boundary guard (D6). No ROS required.

These tests exist because a 30 Hz stream filtered as if it were 200 Hz
produced numbers that looked entirely reasonable and meant nothing. The guard
is cheap; discovering the problem after 40 runs is not.
"""

import ast
from pathlib import Path

import pytest

from control_loop.logic.sampling import (
    CONFIGURED_SAMPLE_RATE_HZ,
    MEASURED_JOINT_STATE_RATE_HZ,
    assert_campaign_sampling_valid,
    nyquist_hz,
    rate_is_consistent,
)

LAUNCH = (
    Path(__file__).resolve().parents[1] / "launch" / "closed_loop.launch.py"
)


def _launch_default(name: str) -> float:
    """Read a DeclareLaunchArgument default statically (no ROS import)."""
    tree = ast.parse(LAUNCH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "DeclareLaunchArgument"):
            continue
        if not node.args or getattr(node.args[0], "value", None) != name:
            continue
        for kw in node.keywords:
            if kw.arg == "default_value":
                return float(ast.literal_eval(kw.value))
    raise AssertionError(f"no DeclareLaunchArgument({name!r}) in {LAUNCH}")


class TestConfiguredRateMatchesReality:
    def test_configured_rate_agrees_with_the_measurement(self):
        assert rate_is_consistent()

    def test_launch_sample_rate_matches_the_configured_rate(self):
        assert _launch_default("sample_rate_hz") == CONFIGURED_SAMPLE_RATE_HZ

    def test_the_shipped_launch_defaults_are_a_valid_campaign_config(self):
        # The exact configuration a campaign run would use.
        assert_campaign_sampling_valid(
            sample_rate_hz=_launch_default("sample_rate_hz"),
            vibration_freq_hz=_launch_default("vibration_freq_hz"),
            cutoff_hz=_launch_default("cutoff_hz"),
        )

    def test_vibration_is_below_nyquist_with_margin(self):
        vib = _launch_default("vibration_freq_hz")
        assert vib < nyquist_hz() * 0.9, (
            f"vibration {vib} Hz is too close to Nyquist {nyquist_hz()} Hz"
        )

    def test_cutoff_is_below_the_vibration_band(self):
        # The whole premise: the filter must have something to attenuate.
        assert _launch_default("cutoff_hz") < _launch_default("vibration_freq_hz")


class TestTheGuardHasTeeth:
    def test_rejects_the_30hz_reality_against_a_200hz_config(self):
        # The exact defect that was found on the sim box.
        with pytest.raises(ValueError, match="disagrees with the measured"):
            assert_campaign_sampling_valid(200.0, 25.0, 5.0, measured_hz=30.02)

    def test_rejects_vibration_at_or_above_nyquist(self):
        with pytest.raises(ValueError, match="at or above Nyquist"):
            assert_campaign_sampling_valid(30.0, 25.0, 5.0, measured_hz=30.0)

    def test_rejects_cutoff_at_or_above_nyquist(self):
        with pytest.raises(ValueError, match="no stopband"):
            assert_campaign_sampling_valid(200.0, 25.0, 150.0,
                                           measured_hz=MEASURED_JOINT_STATE_RATE_HZ)

    def test_aliasing_message_names_the_alias_frequency(self):
        # 25 Hz sampled at 30 Hz folds to 5 Hz — exactly the intended cutoff,
        # which is why this was so dangerous.
        with pytest.raises(ValueError, match="alias to 5.0 Hz"):
            assert_campaign_sampling_valid(30.0, 25.0, 2.0, measured_hz=30.0)
