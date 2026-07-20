"""Causal streaming filter stage for joint states (REQ-S2R-003).

Pure Python/NumPy/SciPy — no ROS imports. The rclpy wrapper is
:mod:`control_loop.dsp_filter_node`.

Ground rule (AGENTS.md §2): only the CAUSAL ``s2r_dsp.apply_filter_realtime``
path is allowed in the closed loop. This module wraps exactly that path:

- :func:`apply_causal_batch` delegates to ``s2r_dsp.apply_filter_realtime``.
- :class:`FilterStage` is the sample-by-sample streaming form of the same
  computation: an ``scipy.signal.lfilter`` direct-form-II-transposed run with
  zero initial conditions, carried across samples via per-joint filter state.
  Unit tests assert the streamed output equals ``apply_filter_realtime`` on
  the full sequence — bit-for-bit for IIR, and to float rounding (~1e-16
  relative; SciPy's stateless FIR path sums in a different order) for FIR —
  which is what licenses the streaming implementation as "the causal path".

The zero-phase ``apply_filter_offline`` is intentionally NOT imported here —
it is for offline analysis only and must never enter the loop.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.signal as signal
from s2r_dsp import apply_filter_realtime, design_fir_lowpass, design_iir_lowpass

_VALID_KINDS = ("fir", "iir")


@dataclass(frozen=True)
class FilterSpec:
    """Design parameters for the in-loop low-pass filter.

    ``kind`` selects the s2r_dsp designer: ``"fir"`` (windowed FIR,
    ``numtaps`` coefficients) or ``"iir"`` (Butterworth, ``order``).
    """

    kind: str = "iir"
    sample_rate_hz: float = 200.0
    cutoff_hz: float = 5.0
    numtaps: int = 101
    order: int = 4

    def validate(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(f"kind must be one of {_VALID_KINDS}, got {self.kind!r}")
        if self.sample_rate_hz <= 0.0:
            raise ValueError(f"sample_rate_hz must be > 0, got {self.sample_rate_hz}")
        if not 0.0 < self.cutoff_hz < 0.5 * self.sample_rate_hz:
            raise ValueError(
                "cutoff_hz must be in (0, Nyquist) = "
                f"(0, {0.5 * self.sample_rate_hz}), got {self.cutoff_hz}"
            )
        if self.kind == "fir" and self.numtaps < 1:
            raise ValueError(f"numtaps must be >= 1, got {self.numtaps}")
        if self.kind == "iir" and self.order < 1:
            raise ValueError(f"order must be >= 1, got {self.order}")

    def design(self):
        """Return ``(b, a)`` coefficients via the s2r_dsp designers."""
        self.validate()
        if self.kind == "fir":
            return design_fir_lowpass(self.sample_rate_hz, self.cutoff_hz, self.numtaps)
        return design_iir_lowpass(self.sample_rate_hz, self.cutoff_hz, self.order)


def apply_causal_batch(spec: FilterSpec, data) -> np.ndarray:
    """Filter a full 1-D sequence through the causal s2r_dsp path."""
    b, a = spec.design()
    data = np.asarray(data, dtype=float)
    if data.ndim != 1:
        raise ValueError(f"expected 1-D data, got shape {data.shape}")
    if data.size == 0:
        return np.empty(0, dtype=float)
    return np.asarray(apply_filter_realtime(b, a, data))


class FilterStage:
    """Streaming causal filter with independent state per joint.

    Feed one joint-position vector per sample via :meth:`process`; each joint
    channel is filtered independently with its own delay-line state. Starting
    from :meth:`reset` (zero initial conditions), the concatenated per-joint
    outputs equal ``apply_causal_batch`` over the same per-joint input
    sequence exactly.
    """

    def __init__(self, spec: FilterSpec, num_joints: int) -> None:
        if num_joints <= 0:
            raise ValueError(f"num_joints must be positive, got {num_joints}")
        self._spec = spec
        b, a = spec.design()
        self._b = np.atleast_1d(np.asarray(b, dtype=float))
        self._a = np.atleast_1d(np.asarray(a, dtype=float))
        self._num_joints = int(num_joints)
        self._state_len = max(len(self._a), len(self._b)) - 1
        self._zi = np.zeros((self._num_joints, self._state_len), dtype=float)
        self._samples_seen = 0

    @property
    def spec(self) -> FilterSpec:
        return self._spec

    @property
    def num_joints(self) -> int:
        return self._num_joints

    @property
    def samples_seen(self) -> int:
        return self._samples_seen

    def reset(self) -> None:
        """Zero the delay-line state (equivalent to a fresh causal run)."""
        self._zi = np.zeros((self._num_joints, self._state_len), dtype=float)
        self._samples_seen = 0

    def process(self, positions) -> np.ndarray:
        """Filter one joint-position sample vector; returns the filtered vector."""
        pos = np.asarray(positions, dtype=float)
        if pos.shape != (self._num_joints,):
            raise ValueError(
                f"expected {self._num_joints} joint positions, got shape {pos.shape}"
            )
        out = np.empty(self._num_joints, dtype=float)
        for j in range(self._num_joints):
            y, self._zi[j] = signal.lfilter(
                self._b, self._a, pos[j : j + 1], zi=self._zi[j]
            )
            out[j] = y[0]
        self._samples_seen += 1
        return out

    def process_batch(self, samples) -> np.ndarray:
        """Filter a ``(n_samples, num_joints)`` block sample-by-sample.

        Zero-length input returns an empty ``(0, num_joints)`` array without
        touching filter state.
        """
        block = np.asarray(samples, dtype=float)
        if block.size == 0:
            return np.empty((0, self._num_joints), dtype=float)
        if block.ndim != 2 or block.shape[1] != self._num_joints:
            raise ValueError(
                f"expected shape (n, {self._num_joints}), got {block.shape}"
            )
        return np.vstack([self.process(row) for row in block])
