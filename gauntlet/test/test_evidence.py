"""Tests for gauntlet.evidence (REQ-S2R-100). No ROS/Isaac required."""

import json

import pytest

from gauntlet.checks import CheckResult, CheckStatus
from gauntlet.errors import GauntletError
from gauntlet.evidence import (
    build_packet,
    dumps_packet,
    load_packet,
    validate_packet,
    write_packet,
)

ENV = {"python": "3.x", "numpy": "1.x", "scipy": "1.x", "s2r_dsp": "0.1.0", "gauntlet": "0.1.0"}
THRESHOLDS = {"tracking_rms_error_max": 0.15}


def _checks(status=CheckStatus.PASSED):
    return [
        CheckResult("tracking_rms_error", 0.05, 0.15, "<=", status, "test"),
    ]


def _packet(**overrides):
    kwargs = dict(
        run_id="0001",
        scenario="franka-joint-tracking-synthetic",
        seed=42,
        checks=_checks(),
        thresholds=THRESHOLDS,
        environment=ENV,
        generated_at=None,
    )
    kwargs.update(overrides)
    return build_packet(**kwargs)


class TestBuild:
    def test_packet_carries_seed_scenario_and_versions(self):
        p = _packet()
        assert p["seed"] == 42
        assert p["scenario"] == "franka-joint-tracking-synthetic"
        assert p["environment"] == ENV
        assert p["overall_passed"] is True

    def test_failed_check_fails_packet(self):
        p = _packet(checks=_checks(CheckStatus.FAILED))
        assert p["overall_passed"] is False

    def test_skipped_check_does_not_fail_packet(self):
        p = _packet(checks=_checks(CheckStatus.PASSED) + [
            CheckResult("filter_attenuation_db", None, 20.0, ">=", CheckStatus.SKIPPED)
        ])
        assert p["overall_passed"] is True

    def test_default_environment_records_real_versions(self):
        import numpy
        p = _packet(environment=None)
        assert p["environment"]["numpy"] == numpy.__version__
        assert set(p["environment"]) == {"python", "numpy", "scipy", "s2r_dsp", "gauntlet"}

    def test_inf_value_serializes_json_safe(self):
        p = _packet(checks=[
            CheckResult("settling_time_s", float("inf"), 2.0, "<=", CheckStatus.FAILED)
        ])
        assert p["checks"][0]["value"] == "inf"
        json.loads(dumps_packet(p))  # must be strict-JSON parseable

    def test_rejects_bad_run_id(self):
        with pytest.raises(GauntletError, match="run id"):
            _packet(run_id="../evil")

    def test_rejects_empty_checks(self):
        with pytest.raises(GauntletError, match="at least one check"):
            _packet(checks=[])

    def test_rejects_non_int_seed(self):
        with pytest.raises(GauntletError, match="seed"):
            _packet(seed="42")


class TestDeterminism:
    def test_identical_inputs_serialize_to_identical_bytes(self):
        assert dumps_packet(_packet()) == dumps_packet(_packet())

    def test_timestamp_only_via_argument(self):
        p = _packet()
        assert p["generated_at"] is None
        p2 = _packet(generated_at="2026-07-19T00:00:00Z")
        assert p2["generated_at"] == "2026-07-19T00:00:00Z"


class TestRoundTrip:
    def test_write_then_load(self, tmp_path):
        p = _packet()
        path = write_packet(p, tmp_path / "evidence")
        assert path.name == "run-0001.json"
        assert load_packet(path) == p


class TestValidation:
    """Adversarial gate: corrupt packets error cleanly, never a false PASS."""

    def test_missing_file(self, tmp_path):
        with pytest.raises(GauntletError, match="not found"):
            load_packet(tmp_path / "run-nope.json")

    def test_corrupt_json(self, tmp_path):
        f = tmp_path / "run-x.json"
        f.write_text("{not json", encoding="utf-8")
        with pytest.raises(GauntletError, match="corrupt"):
            load_packet(f)

    def test_missing_fields(self):
        with pytest.raises(GauntletError, match="missing required fields"):
            validate_packet({"run_id": "x"})

    def test_wrong_schema_version(self):
        p = _packet()
        p = dict(p, schema_version=99)
        with pytest.raises(GauntletError, match="schema_version"):
            validate_packet(p)

    def test_invalid_check_status(self):
        p = _packet()
        p = dict(p, checks=[dict(p["checks"][0], status="maybe")])
        with pytest.raises(GauntletError, match="invalid status"):
            validate_packet(p)

    def test_tampered_verdict_rejected(self):
        """overall_passed=true with failing checks must be refused."""
        p = build_packet(
            run_id="0002",
            scenario="s",
            seed=1,
            checks=_checks(CheckStatus.FAILED),
            thresholds=THRESHOLDS,
            environment=ENV,
        )
        tampered = dict(p, overall_passed=True)
        with pytest.raises(GauntletError, match="contradicts"):
            validate_packet(tampered)
