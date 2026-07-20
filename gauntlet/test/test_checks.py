"""Tests for gauntlet.checks (REQ-S2R-100). No ROS/Isaac required."""

import numpy as np
import pytest

from gauntlet.checks import (
    CheckStatus,
    DEFAULT_THRESHOLDS,
    filter_attenuation_db,
    overshoot_pct,
    run_checks,
    settling_time_s,
    tracking_rms_error,
)
from gauntlet.errors import GauntletError
from gauntlet.test.conftest import synth_streams


class TestMetricPrimitives:
    def test_rms_of_known_offset(self):
        ref = np.zeros(100)
        meas = np.full(100, 0.5)
        assert tracking_rms_error(ref, meas) == pytest.approx(0.5)

    def test_rms_zero_for_perfect_tracking(self):
        ref = np.sin(np.linspace(0, 6.28, 200))
        assert tracking_rms_error(ref, ref) == 0.0

    def test_settling_time_of_constructed_signal(self):
        t = np.arange(100) * 0.01
        ref = np.zeros(100)
        meas = np.zeros(100)
        meas[:30] = 1.0  # outside the band until sample 30
        assert settling_time_s(t, ref, meas, band=0.1) == pytest.approx(0.30)

    def test_settling_time_zero_when_always_inside(self):
        t = np.arange(50) * 0.01
        assert settling_time_s(t, np.zeros(50), np.zeros(50), band=0.1) == 0.0

    def test_settling_time_inf_when_never_settles(self):
        t = np.arange(50) * 0.01
        meas = np.ones(50)
        assert settling_time_s(t, np.zeros(50), meas, band=0.1) == float("inf")

    def test_overshoot_of_constructed_step(self):
        ref = np.concatenate([np.zeros(50), np.ones(50)])  # span 1.0
        meas = ref.copy()
        meas[60] = 1.25  # 25% overshoot
        assert overshoot_pct(ref, meas) == pytest.approx(25.0)

    def test_overshoot_zero_span_reference_stays_defined(self):
        ref = np.zeros(100)
        meas = np.zeros(100)
        meas[10] = 0.3
        assert overshoot_pct(ref, meas) == pytest.approx(30.0)  # span fallback 1.0

    def test_attenuation_of_pure_sine_mixture(self):
        fs, f0 = 200.0, 25.0
        t = np.arange(0, 5.0, 1 / fs)
        vib = 0.3 * np.sin(2 * np.pi * f0 * t)
        attenuated = 0.03 * np.sin(2 * np.pi * f0 * t)  # 10x amplitude drop
        att = filter_attenuation_db(vib, attenuated, fs, f0, 2.0)
        assert att == pytest.approx(20.0, abs=0.1)

    def test_attenuation_zero_when_unfiltered(self):
        fs, f0 = 200.0, 25.0
        t = np.arange(0, 5.0, 1 / fs)
        vib = 0.3 * np.sin(2 * np.pi * f0 * t)
        assert filter_attenuation_db(vib, vib, fs, f0, 2.0) == pytest.approx(0.0)


class TestMetricValidation:
    def test_zero_length_arrays_raise(self):
        with pytest.raises(GauntletError, match="empty"):
            tracking_rms_error(np.empty(0), np.empty(0))

    def test_mismatched_lengths_raise(self):
        with pytest.raises(GauntletError, match="length"):
            tracking_rms_error(np.zeros(10), np.zeros(9))

    def test_nan_raises(self):
        with pytest.raises(GauntletError, match="non-finite"):
            tracking_rms_error(np.zeros(10), np.full(10, np.nan))

    def test_nonpositive_settling_band_raises(self):
        t = np.arange(10) * 0.01
        with pytest.raises(GauntletError, match="band"):
            settling_time_s(t, np.zeros(10), np.zeros(10), band=0.0)

    def test_run_checks_rejects_non_increasing_time(self):
        t = np.array([0.0, 0.1, 0.1, 0.2])
        with pytest.raises(GauntletError, match="strictly increasing"):
            run_checks(t, np.zeros(4), np.zeros(4))

    def test_run_checks_rejects_single_sample(self):
        with pytest.raises(GauntletError, match="at least 2 samples"):
            run_checks(np.array([0.0]), np.array([0.0]), np.array([0.0]))

    def test_run_checks_rejects_unknown_threshold_keys(self):
        t = np.arange(10) * 0.01
        with pytest.raises(GauntletError, match="unknown threshold"):
            run_checks(t, np.zeros(10), np.zeros(10), thresholds={"bogus": 1.0})


class TestDiscrimination:
    """The gauntlet must separate clean / noisy / filtered runs (REQ-S2R-100)."""

    def _statuses(self, measured, noisy=None):
        t, clean, _, _ = synth_streams()
        results = run_checks(t, clean, measured, noisy=noisy)
        return {r.name: r.status for r in results}

    def test_clean_run_passes_everything_and_skips_attenuation(self):
        _, clean, _, _ = synth_streams()
        statuses = self._statuses(clean)
        assert statuses["tracking_rms_error"] is CheckStatus.PASSED
        assert statuses["settling_time_s"] is CheckStatus.PASSED
        assert statuses["overshoot_pct"] is CheckStatus.PASSED
        assert statuses["filter_attenuation_db"] is CheckStatus.SKIPPED

    def test_noisy_run_fails_every_check(self):
        """A run that SHOULD fail does fail — discrimination proof."""
        _, _, noisy, _ = synth_streams()
        statuses = self._statuses(noisy, noisy=noisy)
        assert statuses["tracking_rms_error"] is CheckStatus.FAILED
        assert statuses["settling_time_s"] is CheckStatus.FAILED
        assert statuses["overshoot_pct"] is CheckStatus.FAILED
        assert statuses["filter_attenuation_db"] is CheckStatus.FAILED

    def test_filtered_run_passes_every_check(self):
        _, _, noisy, filtered = synth_streams()
        statuses = self._statuses(filtered, noisy=noisy)
        assert all(s is CheckStatus.PASSED for s in statuses.values())

    def test_filtered_beats_noisy_on_every_metric(self):
        t, clean, noisy, filtered = synth_streams()
        band = DEFAULT_THRESHOLDS["settling_band_rad"]
        assert tracking_rms_error(clean, filtered) < tracking_rms_error(clean, noisy)
        assert settling_time_s(t, clean, filtered, band) < settling_time_s(
            t, clean, noisy, band
        )
        assert overshoot_pct(clean, filtered) < overshoot_pct(clean, noisy)

    def test_results_are_deterministic(self):
        t, clean, noisy, _ = synth_streams()
        a = [r.to_dict() for r in run_checks(t, clean, noisy, noisy=noisy)]
        b = [r.to_dict() for r in run_checks(t, clean, noisy, noisy=noisy)]
        assert a == b

    def test_threshold_override_flips_verdict(self):
        t, clean, _, _ = synth_streams()
        results = run_checks(
            t, clean, clean, thresholds={"tracking_rms_error_max": -1.0}
        )
        rms = next(r for r in results if r.name == "tracking_rms_error")
        assert rms.status is CheckStatus.FAILED
