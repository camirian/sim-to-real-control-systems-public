"""Tests for control_loop.logic.noise_model (REQ-S2R-002). No ROS required."""

import hashlib
import subprocess
import sys

import numpy as np
import pytest

from control_loop.logic.noise_model import JointStateNoiseModel, NoiseProfile

NUM_JOINTS = 7
FS = 200.0


def _run_sequence(seed: int, n_samples: int = 100) -> np.ndarray:
    model = JointStateNoiseModel(NoiseProfile(seed=seed), NUM_JOINTS)
    base = np.zeros(NUM_JOINTS)
    return np.vstack([model.apply(base, i / FS) for i in range(n_samples)])


def _digest(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


class TestDeterminism:
    def test_same_seed_identical_sequence(self):
        assert np.array_equal(_run_sequence(42), _run_sequence(42))

    def test_reset_replays_identical_sequence(self):
        model = JointStateNoiseModel(NoiseProfile(seed=7), NUM_JOINTS)
        base = np.ones(NUM_JOINTS)
        first = np.vstack([model.apply(base, i / FS) for i in range(50)])
        model.reset()
        second = np.vstack([model.apply(base, i / FS) for i in range(50)])
        assert np.array_equal(first, second)

    def test_different_seeds_differ(self):
        assert not np.array_equal(_run_sequence(1), _run_sequence(2))

    def test_determinism_across_processes(self):
        """Adversarial gate: same seed must produce bit-identical noise in a
        separate Python process (no hidden global-RNG state)."""
        code = (
            "import hashlib, numpy as np\n"
            "from control_loop.logic.noise_model import JointStateNoiseModel, NoiseProfile\n"
            f"m = JointStateNoiseModel(NoiseProfile(seed=42), {NUM_JOINTS})\n"
            f"base = np.zeros({NUM_JOINTS})\n"
            f"seq = np.vstack([m.apply(base, i / {FS}) for i in range(100)])\n"
            "print(hashlib.sha256(np.ascontiguousarray(seq).tobytes()).hexdigest())\n"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        assert out.stdout.strip() == _digest(_run_sequence(42))


class TestNoiseContent:
    def test_zero_profile_is_identity(self):
        model = JointStateNoiseModel(
            NoiseProfile(seed=0, awgn_sigma=0.0, vibration_amplitude=0.0), NUM_JOINTS
        )
        base = np.linspace(-1.0, 1.0, NUM_JOINTS)
        assert np.array_equal(model.apply(base, 0.123), base)

    def test_vibration_is_pure_function_of_time(self):
        model = JointStateNoiseModel(
            NoiseProfile(seed=0, awgn_sigma=0.0, vibration_amplitude=0.3,
                         vibration_freq_hz=25.0),
            NUM_JOINTS,
        )
        # At t=0.01 s, sin(2*pi*25*0.01) = sin(pi/2) = 1 -> offset = amplitude.
        out = model.apply(np.zeros(NUM_JOINTS), 0.01)
        assert np.allclose(out, 0.3)

    def test_awgn_statistics_roughly_match_sigma(self):
        sigma = 0.1
        model = JointStateNoiseModel(
            NoiseProfile(seed=3, awgn_sigma=sigma, vibration_amplitude=0.0),
            NUM_JOINTS,
        )
        samples = np.vstack(
            [model.apply(np.zeros(NUM_JOINTS), 0.0) for _ in range(2000)]
        )
        assert abs(samples.std() - sigma) < 0.01
        assert abs(samples.mean()) < 0.01

    def test_noise_matches_synthesizer_band(self):
        """The model's vibration term matches s2r_dsp.generate_telemetry's
        25 Hz interference model (same defaults)."""
        profile = NoiseProfile()
        assert profile.vibration_freq_hz == 25.0
        assert profile.vibration_amplitude == 0.3
        assert profile.awgn_sigma == 0.1


class TestValidation:
    def test_rejects_wrong_joint_count(self):
        model = JointStateNoiseModel(NoiseProfile(), NUM_JOINTS)
        with pytest.raises(ValueError, match="expected 7 joint positions"):
            model.apply(np.zeros(3), 0.0)

    def test_rejects_nonpositive_num_joints(self):
        with pytest.raises(ValueError, match="num_joints"):
            JointStateNoiseModel(NoiseProfile(), 0)

    def test_rejects_negative_sigma(self):
        with pytest.raises(ValueError, match="awgn_sigma"):
            JointStateNoiseModel(NoiseProfile(awgn_sigma=-0.1), NUM_JOINTS)

    def test_rejects_negative_amplitude(self):
        with pytest.raises(ValueError, match="vibration_amplitude"):
            JointStateNoiseModel(
                NoiseProfile(vibration_amplitude=-1.0), NUM_JOINTS
            )

    def test_rejects_nonfinite_timestamp(self):
        model = JointStateNoiseModel(NoiseProfile(), NUM_JOINTS)
        with pytest.raises(ValueError, match="timestamp"):
            model.apply(np.zeros(NUM_JOINTS), float("nan"))
