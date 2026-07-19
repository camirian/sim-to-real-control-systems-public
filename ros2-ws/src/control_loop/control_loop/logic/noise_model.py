"""Seeded, parameter-driven joint-state noise model (REQ-S2R-002).

Pure Python/NumPy — no ROS imports. The rclpy wrapper is
:mod:`control_loop.noise_injector_node`.

Noise model (mirrors ``s2r_dsp.generate_telemetry``): each joint position gets

1. a deterministic structural-vibration term ``A * sin(2*pi*f*t + phase)``
   (a pure function of the sample timestamp ``t``), and
2. additive white Gaussian noise drawn from ``numpy.random.default_rng(seed)``.

Determinism contract (AGENTS.md §2 "determinism is the product"): for a given
:class:`NoiseProfile` (seed included) and the same sequence of ``apply()``
calls (same joint counts, same timestamps, same order), the emitted noisy
sequence is bit-identical — across calls, processes, and machines (same
NumPy generator algorithm). This is unit-tested including a cross-process
digest comparison.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class NoiseProfile:
    """Parameter set for the joint-state noise model.

    Defaults match the ``s2r_dsp.generate_telemetry`` synthesizer: 25 Hz
    structural vibration at amplitude 0.3 rad plus AWGN with sigma 0.1 rad.
    """

    seed: int = 0
    awgn_sigma: float = 0.1
    vibration_amplitude: float = 0.3
    vibration_freq_hz: float = 25.0
    vibration_phase_rad: float = 0.0

    def validate(self) -> None:
        if self.awgn_sigma < 0.0:
            raise ValueError(f"awgn_sigma must be >= 0, got {self.awgn_sigma}")
        if self.vibration_amplitude < 0.0:
            raise ValueError(
                f"vibration_amplitude must be >= 0, got {self.vibration_amplitude}"
            )
        if self.vibration_freq_hz < 0.0:
            raise ValueError(
                f"vibration_freq_hz must be >= 0, got {self.vibration_freq_hz}"
            )


class JointStateNoiseModel:
    """Applies seeded noise to per-sample joint position vectors.

    Parameters
    ----------
    profile:
        Noise parameters (including the seed).
    num_joints:
        Number of joints expected in every ``apply()`` call.
    """

    def __init__(self, profile: NoiseProfile, num_joints: int) -> None:
        profile.validate()
        if num_joints <= 0:
            raise ValueError(f"num_joints must be positive, got {num_joints}")
        self._profile = profile
        self._num_joints = int(num_joints)
        self._rng = np.random.default_rng(profile.seed)

    @property
    def profile(self) -> NoiseProfile:
        return self._profile

    @property
    def num_joints(self) -> int:
        return self._num_joints

    def reset(self) -> None:
        """Rewind the AWGN stream to the start of the seed sequence."""
        self._rng = np.random.default_rng(self._profile.seed)

    def vibration(self, t: float) -> float:
        """Deterministic vibration displacement at timestamp ``t`` (seconds)."""
        p = self._profile
        return p.vibration_amplitude * math.sin(
            2.0 * math.pi * p.vibration_freq_hz * t + p.vibration_phase_rad
        )

    def apply(self, positions, t: float) -> np.ndarray:
        """Return a noisy copy of one joint-position sample.

        Parameters
        ----------
        positions:
            Sequence of ``num_joints`` joint positions (radians).
        t:
            Sample timestamp in seconds (drives the vibration phase). Use the
            message header stamp so replays are reproducible.
        """
        pos = np.asarray(positions, dtype=float)
        if pos.shape != (self._num_joints,):
            raise ValueError(
                f"expected {self._num_joints} joint positions, got shape {pos.shape}"
            )
        if not math.isfinite(t):
            raise ValueError(f"timestamp must be finite, got {t}")
        awgn = self._rng.normal(0.0, self._profile.awgn_sigma, self._num_joints)
        return pos + self.vibration(t) + awgn
