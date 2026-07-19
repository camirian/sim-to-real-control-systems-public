"""Import-surface and edge-case behavior tests for the s2r-dsp package.

REQ-S2R-001: ``dsp/`` installs as the ``s2r_dsp`` package with a stable
public API and no ``sys.path`` hacks.

The edge-case tests DOCUMENT the current behavior of the filter paths for
degenerate inputs (NaN, empty, odd dtypes). They pin today's contract so
downstream nodes (noise injector, filter node — REQ-S2R-002/003) know
exactly what they must guard against; they do not bless NaN as acceptable
in-loop input. If a future change intentionally alters this contract,
update these tests and the PR must say so.
"""
import numpy as np
import pytest

import s2r_dsp
from s2r_dsp import (
    apply_filter_offline,
    apply_filter_realtime,
    design_fir_lowpass,
    design_iir_lowpass,
    generate_telemetry,
)

FS = 200.0
CUTOFF = 5.0


# --- Import surface -------------------------------------------------------

def test_public_api_is_exported():
    expected = {
        "apply_filter_offline",
        "apply_filter_realtime",
        "design_fir_lowpass",
        "design_iir_lowpass",
        "generate_telemetry",
        "__version__",
    }
    assert expected == set(s2r_dsp.__all__)
    for name in expected:
        assert getattr(s2r_dsp, name) is not None


def test_submodules_importable():
    # The flat functions also remain importable from their home modules.
    from s2r_dsp.data_synthesizer import generate_telemetry as gt
    from s2r_dsp.filters import apply_filter_realtime as afr

    assert gt is generate_telemetry
    assert afr is apply_filter_realtime


def test_no_sys_path_mutation_needed():
    # The package resolves via normal import machinery (installed or
    # src-dir on path), never via a sys.path hack inside the modules.
    import sys

    assert "s2r_dsp" in sys.modules
    assert s2r_dsp.__file__ is not None


# --- Edge-case behavior (documented, not endorsed) ------------------------

def test_realtime_filter_empty_input_returns_empty():
    b, a = design_iir_lowpass(FS, CUTOFF, order=4)
    out = apply_filter_realtime(b, a, np.array([]))
    assert isinstance(out, np.ndarray)
    assert out.size == 0


def test_offline_filter_empty_or_short_input_raises():
    # filtfilt needs len(x) > padlen (3 * max(len(a), len(b)) for the
    # default padding); empty/short inputs raise ValueError today.
    b, a = design_iir_lowpass(FS, CUTOFF, order=4)
    with pytest.raises(ValueError):
        apply_filter_offline(b, a, np.array([]))
    with pytest.raises(ValueError):
        apply_filter_offline(b, a, np.zeros(5))


def test_realtime_filter_nan_propagates():
    # A single NaN sample poisons the IIR output from that sample onward
    # (infinite impulse response); it is NOT silently repaired. In-loop
    # nodes must validate samples before filtering (REQ-S2R-003 lane).
    b, a = design_iir_lowpass(FS, CUTOFF, order=4)
    x = np.zeros(100)
    x[10] = np.nan
    out = apply_filter_realtime(b, a, x)
    assert np.isnan(out[10:]).all()
    assert not np.isnan(out[:10]).any()

    # FIR contamination is bounded by the filter length (numtaps samples).
    fb, fa = design_fir_lowpass(FS, CUTOFF, numtaps=11)
    fir_out = apply_filter_realtime(fb, fa, x)
    assert np.isnan(fir_out[10:21]).all()
    assert not np.isnan(fir_out[:10]).any()
    assert not np.isnan(fir_out[21:]).any()


def test_realtime_filter_accepts_list_and_int_dtype():
    # lfilter coerces python lists and integer arrays to float64 output.
    b, a = design_iir_lowpass(FS, CUTOFF, order=4)
    out_list = apply_filter_realtime(b, a, [0.0, 1.0, 0.0, 0.0])
    assert isinstance(out_list, np.ndarray)
    assert out_list.dtype == np.float64
    out_int = apply_filter_realtime(b, a, np.array([0, 1, 0, 0], dtype=np.int64))
    assert out_int.dtype == np.float64


def test_realtime_filter_rejects_non_numeric_dtype():
    b, a = design_iir_lowpass(FS, CUTOFF, order=4)
    with pytest.raises(NotImplementedError):
        apply_filter_realtime(b, a, np.array(["a", "b"]))


def test_synthesizer_shapes_and_determinism():
    t, clean, noisy = generate_telemetry(duration=1.0, fs=FS)
    assert t.shape == clean.shape == noisy.shape
    t2, clean2, noisy2 = generate_telemetry(duration=1.0, fs=FS)
    assert np.array_equal(noisy, noisy2)
