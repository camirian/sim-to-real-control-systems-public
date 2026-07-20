"""Certification checks computed from logged run data (REQ-S2R-100).

Inputs are plain NumPy arrays extracted from run logs (CSV columns exported
from rosbag or written by the campaign runner) — no ROS anywhere.

Metric definitions (trajectory-tracking adaptations of the classical
step-response quantities; thresholds live in :data:`DEFAULT_THRESHOLDS` and
are embedded in every evidence packet):

- **tracking_rms_error** — RMS of ``measured - reference`` over the run.
- **settling_time_s** — earliest time ``t_k`` such that
  ``|measured - reference| <= settling_band`` for every sample from ``t_k``
  to the end of the run; ``inf`` if the error never stays inside the band.
- **overshoot_pct** — ``100 * max|measured - reference| / span(reference)``
  (span = max - min of the reference; a zero-span reference uses 1.0 to stay
  defined). Bounds the worst instantaneous excursion relative to the
  commanded motion's scale.
- **filter_attenuation_db** — band-power attenuation from the raw noisy
  stream to the measured (post-filter) stream inside the vibration band,
  ``10*log10(P_in / P_out)`` via an rFFT periodogram. Skipped (not passed)
  when the log carries no noisy stream to compare against.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from gauntlet.errors import GauntletError

#: Default check thresholds. Tuned against the s2r_dsp synthesizer profile
#: (0.5 Hz base motion, 0.3 rad vibration at 25 Hz, AWGN sigma 0.1): the
#: clean and causally-filtered (IIR order 4, 10 Hz cutoff at 200 Hz) streams
#: pass all checks; the raw noisy stream fails RMS, settling, overshoot, and
#: (as a filter run) attenuation. Measured margins in the trailing comments.
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "tracking_rms_error_max": 0.15,  # rad (noisy≈0.236, filtered≈0.091)
    "settling_time_max_s": 2.0,  # s (noisy=inf, filtered≈0.12)
    "settling_band_rad": 0.2,  # |err| band used by settling time
    "overshoot_max_pct": 25.0,  # % of ref span (noisy≈34.5, filtered≈10.3)
    "filter_attenuation_min_db": 20.0,  # dB (noisy=0.0, filtered≈33.6)
    "vibration_band_hz": 25.0,  # band center
    "vibration_band_halfwidth_hz": 2.0,  # band half-width
}


class CheckStatus(enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CheckResult:
    """One graded metric: value vs. threshold with an explicit comparator."""

    name: str
    value: Optional[float]  # None when skipped
    threshold: float
    comparator: str  # "<=" or ">="
    status: CheckStatus
    detail: str = ""

    def to_dict(self) -> dict:
        value = self.value
        if value is not None and math.isinf(value):
            value = "inf"  # JSON-safe
        return {
            "name": self.name,
            "value": value,
            "threshold": self.threshold,
            "comparator": self.comparator,
            "status": self.status.value,
            "detail": self.detail,
        }


def _as_clean_1d(name: str, arr) -> np.ndarray:
    a = np.asarray(arr, dtype=float)
    if a.ndim != 1:
        raise GauntletError(f"{name} must be 1-D, got shape {a.shape}")
    if a.size == 0:
        raise GauntletError(f"{name} is empty")
    if not np.all(np.isfinite(a)):
        raise GauntletError(f"{name} contains non-finite values")
    return a


def _check_same_length(t: np.ndarray, *streams: np.ndarray) -> None:
    lengths = {len(t)} | {len(s) for s in streams}
    if len(lengths) != 1:
        raise GauntletError(f"log streams disagree on length: {sorted(lengths)}")


def tracking_rms_error(reference, measured) -> float:
    ref = _as_clean_1d("reference", reference)
    meas = _as_clean_1d("measured", measured)
    _check_same_length(ref, meas)
    return float(np.sqrt(np.mean((meas - ref) ** 2)))


def settling_time_s(t, reference, measured, band: float) -> float:
    tt = _as_clean_1d("t", t)
    ref = _as_clean_1d("reference", reference)
    meas = _as_clean_1d("measured", measured)
    _check_same_length(tt, ref, meas)
    if band <= 0.0:
        raise GauntletError(f"settling band must be > 0, got {band}")
    inside = np.abs(meas - ref) <= band
    if not inside[-1]:
        return float("inf")
    # Last sample outside the band; settled ever after.
    outside = np.nonzero(~inside)[0]
    if outside.size == 0:
        return float(tt[0] - tt[0])  # settled from the start -> 0.0
    first_settled = outside[-1] + 1
    return float(tt[first_settled] - tt[0])


def overshoot_pct(reference, measured) -> float:
    ref = _as_clean_1d("reference", reference)
    meas = _as_clean_1d("measured", measured)
    _check_same_length(ref, meas)
    span = float(ref.max() - ref.min())
    if span == 0.0:
        span = 1.0
    return float(100.0 * np.max(np.abs(meas - ref)) / span)


def _band_power(x: np.ndarray, fs: float, f0: float, halfwidth: float) -> float:
    freqs = np.fft.rfftfreq(len(x), 1.0 / fs)
    psd = np.abs(np.fft.rfft(x)) ** 2 / len(x)
    mask = (freqs >= f0 - halfwidth) & (freqs <= f0 + halfwidth)
    if not np.any(mask):
        raise GauntletError(
            f"vibration band {f0}±{halfwidth} Hz outside resolvable spectrum "
            f"(fs={fs} Hz, n={len(x)})"
        )
    return float(psd[mask].sum())


def filter_attenuation_db(noisy, measured, fs: float, f0: float, halfwidth: float) -> float:
    """Band-power drop from the noisy input stream to the measured stream."""
    n = _as_clean_1d("noisy", noisy)
    m = _as_clean_1d("measured", measured)
    _check_same_length(n, m)
    if fs <= 0.0:
        raise GauntletError(f"sample rate must be > 0, got {fs}")
    p_in = _band_power(n, fs, f0, halfwidth)
    p_out = _band_power(m, fs, f0, halfwidth)
    if p_in <= 0.0:
        raise GauntletError("noisy stream has zero power in the vibration band")
    if p_out == 0.0:
        return float("inf")
    return float(10.0 * math.log10(p_in / p_out))


def run_checks(
    t,
    reference,
    measured,
    noisy=None,
    thresholds: Optional[Dict[str, float]] = None,
) -> List[CheckResult]:
    """Grade one run's streams; returns all four checks in a fixed order.

    ``noisy`` is the pre-filter stream; when absent the attenuation check is
    recorded SKIPPED (never silently passed).
    """
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        unknown = set(thresholds) - set(th)
        if unknown:
            raise GauntletError(f"unknown threshold keys: {sorted(unknown)}")
        th.update({k: float(v) for k, v in thresholds.items()})

    tt = _as_clean_1d("t", t)
    if len(tt) > 1 and not np.all(np.diff(tt) > 0):
        raise GauntletError("t must be strictly increasing")
    if len(tt) > 1:
        fs = 1.0 / float(np.median(np.diff(tt)))
    else:
        raise GauntletError("run log must contain at least 2 samples")

    results: List[CheckResult] = []

    rms = tracking_rms_error(reference, measured)
    results.append(
        CheckResult(
            "tracking_rms_error",
            rms,
            th["tracking_rms_error_max"],
            "<=",
            CheckStatus.PASSED if rms <= th["tracking_rms_error_max"] else CheckStatus.FAILED,
            "RMS of measured-vs-reference joint position (rad)",
        )
    )

    st = settling_time_s(tt, reference, measured, th["settling_band_rad"])
    results.append(
        CheckResult(
            "settling_time_s",
            st,
            th["settling_time_max_s"],
            "<=",
            CheckStatus.PASSED if st <= th["settling_time_max_s"] else CheckStatus.FAILED,
            f"time to stay within ±{th['settling_band_rad']} rad of reference",
        )
    )

    ov = overshoot_pct(reference, measured)
    results.append(
        CheckResult(
            "overshoot_pct",
            ov,
            th["overshoot_max_pct"],
            "<=",
            CheckStatus.PASSED if ov <= th["overshoot_max_pct"] else CheckStatus.FAILED,
            "worst |error| as % of reference span",
        )
    )

    if noisy is None:
        results.append(
            CheckResult(
                "filter_attenuation_db",
                None,
                th["filter_attenuation_min_db"],
                ">=",
                CheckStatus.SKIPPED,
                "no noisy (pre-filter) stream in this log",
            )
        )
    else:
        att = filter_attenuation_db(
            noisy,
            measured,
            fs,
            th["vibration_band_hz"],
            th["vibration_band_halfwidth_hz"],
        )
        results.append(
            CheckResult(
                "filter_attenuation_db",
                att,
                th["filter_attenuation_min_db"],
                ">=",
                CheckStatus.PASSED if att >= th["filter_attenuation_min_db"] else CheckStatus.FAILED,
                f"band-power drop noisy->measured at "
                f"{th['vibration_band_hz']}±{th['vibration_band_halfwidth_hz']} Hz",
            )
        )

    return results
