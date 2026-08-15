"""The measured sampling boundary of the simulated joint-state stream (D6).

Pure Python — no ROS, no Isaac.

Why this module exists. The DSP path was designed against an *assumed*
`sample_rate_hz = 200.0`. When the loop was first run on a real Isaac Sim
6.0.1 host the stream arrived at **30 Hz**, which would have made a 5 Hz
cutoff behave as 0.75 Hz and — far worse — put the 25 Hz injected vibration
*above* the 15 Hz Nyquist, where it aliases to 5 Hz and lands exactly on the
cutoff. A campaign run in that state produces a filtered-vs-unfiltered
comparison of an aliasing artifact, and every run is contaminated identically,
which is precisely what a paired comparison cannot detect.

The resolution was to fix the sampling boundary rather than retune the filter:
the simulation is configured so `/joint_states` really is published at 200 Hz.
This module records the measured value and gives the campaign a hard guard, so
the failure can never recur silently.

Provenance of `MEASURED_JOINT_STATE_RATE_HZ`: `scripts/validate_isaac6_runtime.py`
on Isaac Sim 6.0.1 / DGX Spark / GB10, 1811 messages over 30 s, mean inter-sample
interval 4.988 ms, stdev 0.176 ms. See docs/M4_RUNTIME_VALIDATION.md.
"""

from __future__ import annotations

# Measured, not assumed. Update ONLY from a fresh runtime measurement.
MEASURED_JOINT_STATE_RATE_HZ = 200.498
MEASUREMENT_STDEV_S = 0.000176
MEASUREMENT_SAMPLES = 1811

# The rate the DSP path is configured for. It must agree with the measurement.
CONFIGURED_SAMPLE_RATE_HZ = 200.0

# Fractional disagreement tolerated between configured and measured rates.
RATE_TOLERANCE = 0.02


def nyquist_hz(sample_rate_hz: float = CONFIGURED_SAMPLE_RATE_HZ) -> float:
    """Half the sampling rate — the highest representable frequency."""
    return 0.5 * float(sample_rate_hz)


def rate_is_consistent(
    configured_hz: float = CONFIGURED_SAMPLE_RATE_HZ,
    measured_hz: float = MEASURED_JOINT_STATE_RATE_HZ,
    tolerance: float = RATE_TOLERANCE,
) -> bool:
    """True when the configured DSP rate matches what the simulator delivers."""
    if measured_hz <= 0:
        return False
    return abs(configured_hz - measured_hz) / measured_hz <= tolerance


def assert_campaign_sampling_valid(
    sample_rate_hz: float,
    vibration_freq_hz: float,
    cutoff_hz: float,
    measured_hz: float = MEASURED_JOINT_STATE_RATE_HZ,
) -> None:
    """Raise unless a campaign configuration is physically meaningful.

    Three independent ways a seeded sweep can produce numbers that look fine
    and mean nothing:

    1. the DSP rate disagrees with the rate the simulator actually publishes
       (the filter's cutoff is then wrong by that ratio);
    2. the injected vibration sits at or above Nyquist, so it aliases and the
       "attenuation" being measured is of a frequency that was never there;
    3. the cutoff sits at or above Nyquist, so there is no stopband.
    """
    if not rate_is_consistent(sample_rate_hz, measured_hz):
        raise ValueError(
            f"sample_rate_hz={sample_rate_hz} disagrees with the measured "
            f"/joint_states rate {measured_hz} Hz beyond {RATE_TOLERANCE:.0%}. "
            "Re-measure with scripts/validate_isaac6_runtime.py; do not adjust "
            "the filter to paper over this."
        )
    nyq = nyquist_hz(sample_rate_hz)
    if vibration_freq_hz >= nyq:
        raise ValueError(
            f"vibration_freq_hz={vibration_freq_hz} is at or above Nyquist "
            f"({nyq} Hz) for sample_rate_hz={sample_rate_hz}; it would alias to "
            f"{abs(sample_rate_hz - vibration_freq_hz)} Hz and the campaign "
            "would be measuring an artifact."
        )
    if cutoff_hz >= nyq:
        raise ValueError(
            f"cutoff_hz={cutoff_hz} is at or above Nyquist ({nyq} Hz) for "
            f"sample_rate_hz={sample_rate_hz}; the filter has no stopband."
        )
