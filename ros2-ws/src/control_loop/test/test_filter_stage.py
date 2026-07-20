"""Tests for control_loop.logic.filter_stage (REQ-S2R-003). No ROS required."""

import numpy as np
import pytest
from s2r_dsp import apply_filter_realtime, generate_telemetry

from control_loop.logic.filter_stage import FilterSpec, FilterStage, apply_causal_batch

FS = 200.0
IIR = FilterSpec(kind="iir", sample_rate_hz=FS, cutoff_hz=5.0, order=4)
FIR = FilterSpec(kind="fir", sample_rate_hz=FS, cutoff_hz=5.0, numtaps=101)


def _band_amplitude(x: np.ndarray, fs: float, f0: float, half_width: float = 2.0):
    """Peak spectral magnitude in [f0-hw, f0+hw] via rFFT."""
    freqs = np.fft.rfftfreq(len(x), 1.0 / fs)
    mag = np.abs(np.fft.rfft(x)) / len(x)
    band = (freqs >= f0 - half_width) & (freqs <= f0 + half_width)
    return mag[band].max()


class TestCausalPathEquivalence:
    """The streaming stage must BE the s2r_dsp causal path, bit-for-bit."""

    def test_streaming_equals_apply_filter_realtime_iir_bit_exact(self):
        _, _, noisy = generate_telemetry(duration=2.0, fs=FS)
        stage = FilterStage(IIR, num_joints=1)
        streamed = np.array([stage.process([x])[0] for x in noisy])
        b, a = IIR.design()
        assert np.array_equal(streamed, apply_filter_realtime(b, a, noisy))

    def test_streaming_equals_apply_filter_realtime_fir(self):
        # SciPy's stateless FIR path uses a different summation order than the
        # zi-carried streaming path, so FIR matches to float rounding (~1e-16
        # relative), not bit-for-bit; IIR above is bit-exact.
        _, _, noisy = generate_telemetry(duration=2.0, fs=FS)
        stage = FilterStage(FIR, num_joints=1)
        streamed = np.array([stage.process([x])[0] for x in noisy])
        b, a = FIR.design()
        batch = apply_filter_realtime(b, a, noisy)
        np.testing.assert_allclose(streamed, batch, rtol=1e-12, atol=1e-14)

    def test_batch_helper_delegates_to_s2r_dsp(self):
        _, _, noisy = generate_telemetry(duration=1.0, fs=FS)
        b, a = IIR.design()
        assert np.array_equal(
            apply_causal_batch(IIR, noisy), apply_filter_realtime(b, a, noisy)
        )

    def test_per_joint_state_is_independent(self):
        rng = np.random.default_rng(0)
        block = rng.normal(size=(300, 3))
        stage = FilterStage(IIR, num_joints=3)
        out = stage.process_batch(block)
        for j in range(3):
            solo = FilterStage(IIR, num_joints=1)
            solo_out = np.array([solo.process([x])[0] for x in block[:, j]])
            assert np.array_equal(out[:, j], solo_out)


class TestAttenuation:
    def test_iir_attenuates_25hz_vibration_band(self):
        """REQ-S2R-003: attenuation >= spec (20 dB) at the 25 Hz band."""
        _, _, noisy = generate_telemetry(duration=5.0, fs=FS)
        stage = FilterStage(IIR, num_joints=1)
        filtered = np.array([stage.process([x])[0] for x in noisy])
        before = _band_amplitude(noisy, FS, 25.0)
        after = _band_amplitude(filtered, FS, 25.0)
        atten_db = 20.0 * np.log10(before / after)
        assert atten_db >= 20.0, f"attenuation only {atten_db:.1f} dB"

    def test_passband_signal_survives(self):
        _, clean, noisy = generate_telemetry(duration=5.0, fs=FS)
        stage = FilterStage(IIR, num_joints=1)
        filtered = np.array([stage.process([x])[0] for x in noisy])
        # 0.5 Hz base motion must come through near unity.
        base_in = _band_amplitude(clean, FS, 0.5, half_width=0.4)
        base_out = _band_amplitude(filtered, FS, 0.5, half_width=0.4)
        assert base_out >= 0.8 * base_in


class TestDegenerateStreams:
    """Adversarial gate: constant / zero-length / single-sample streams."""

    def test_constant_stream_converges_to_constant(self):
        stage = FilterStage(IIR, num_joints=2)
        const = np.array([0.7, -0.3])
        out = None
        for _ in range(2000):
            out = stage.process(const)
        assert np.allclose(out, const, atol=1e-6)

    def test_zero_length_batch_returns_empty(self):
        stage = FilterStage(IIR, num_joints=2)
        out = stage.process_batch(np.empty((0, 2)))
        assert out.shape == (0, 2)
        assert stage.samples_seen == 0

    def test_zero_length_causal_batch(self):
        assert apply_causal_batch(IIR, np.empty(0)).shape == (0,)

    def test_single_sample_stream(self):
        stage = FilterStage(IIR, num_joints=1)
        out = stage.process([1.0])
        b, a = IIR.design()
        expected = apply_filter_realtime(b, a, np.array([1.0]))
        assert np.array_equal(out, expected)

    def test_reset_restarts_causal_run(self):
        _, _, noisy = generate_telemetry(duration=0.5, fs=FS)
        stage = FilterStage(IIR, num_joints=1)
        first = np.array([stage.process([x])[0] for x in noisy])
        stage.reset()
        second = np.array([stage.process([x])[0] for x in noisy])
        assert np.array_equal(first, second)


class TestValidation:
    def test_rejects_bad_kind(self):
        with pytest.raises(ValueError, match="kind"):
            FilterSpec(kind="chebyshev").validate()

    def test_rejects_cutoff_above_nyquist(self):
        with pytest.raises(ValueError, match="Nyquist"):
            FilterSpec(kind="iir", sample_rate_hz=100.0, cutoff_hz=60.0).validate()

    def test_rejects_nonpositive_sample_rate(self):
        with pytest.raises(ValueError, match="sample_rate_hz"):
            FilterSpec(sample_rate_hz=0.0).validate()

    def test_rejects_wrong_joint_count(self):
        stage = FilterStage(IIR, num_joints=2)
        with pytest.raises(ValueError, match="expected 2 joint positions"):
            stage.process([1.0, 2.0, 3.0])

    def test_rejects_nonpositive_num_joints(self):
        with pytest.raises(ValueError, match="num_joints"):
            FilterStage(IIR, num_joints=0)
