"""Tests for the s2r-dsp package (REQ-S2R-001).

These run without ROS 2 or Isaac Sim:

    pip install -e dsp/
    pytest dsp/
"""
import numpy as np

from s2r_dsp import (
    apply_filter_offline,
    apply_filter_realtime,
    design_fir_lowpass,
    design_iir_lowpass,
    generate_telemetry,
)

FS = 200.0
CUTOFF = 5.0


def test_fir_coefficient_count():
    b, a = design_fir_lowpass(FS, CUTOFF, numtaps=101)
    assert len(b) == 101
    assert a == [1.0]


def test_iir_coefficient_count():
    b, a = design_iir_lowpass(FS, CUTOFF, order=4)
    # A Butterworth filter of order N has N+1 numerator and denominator coeffs.
    assert len(b) == 5
    assert len(a) == 5


def test_telemetry_is_deterministic():
    # The synthesizer is seeded, so two calls must be identical.
    _, clean_a, noisy_a = generate_telemetry(duration=2.0, fs=FS)
    _, clean_b, noisy_b = generate_telemetry(duration=2.0, fs=FS)
    assert np.array_equal(clean_a, clean_b)
    assert np.array_equal(noisy_a, noisy_b)


def test_filters_reduce_noise():
    t, clean, noisy = generate_telemetry(duration=5.0, fs=FS)

    fir_b, fir_a = design_fir_lowpass(FS, CUTOFF, numtaps=101)
    iir_b, iir_a = design_iir_lowpass(FS, CUTOFF, order=4)

    fir_out = apply_filter_realtime(fir_b, fir_a, noisy)
    iir_out = apply_filter_offline(iir_b, iir_a, noisy)

    # Output length is preserved.
    assert len(fir_out) == len(noisy)
    assert len(iir_out) == len(noisy)

    # Filtering should reduce the residual error against ground truth.
    raw_err = np.var(noisy - clean)
    iir_err = np.var(iir_out - clean)
    assert iir_err < raw_err
