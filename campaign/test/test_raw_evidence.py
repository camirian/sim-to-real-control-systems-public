"""Raw evidence packets must fail closed on every shape of quiet omission.

The dangerous failure is not a corrupt file — that is loud. It is a run that
disappears, or one that stays in the numerator while its rate quietly drifted.
Each test below is one such route, closed.
"""

import pytest

from campaign.errors import CampaignError
from campaign.manifest import file_sha256
from campaign.raw_evidence import (
    STATUS_FAILED,
    STATUS_INVALID,
    STATUS_VALID,
    build_raw_packet,
    integrity_index,
    load_raw_packet,
    rate_stats,
    summarize_signals,
    validate_raw_packet,
    verify_integrity,
    write_raw_packet,
)


def make(**kw):
    base = dict(
        run_id="filtered-0003",
        condition="filtered",
        seed=3,
        scenario="franka-joint-tracking",
        campaign_id="m4-franka-filtered-vs-unfiltered",
        campaign_version=1,
        manifest_sha256="d" * 64,
        execution_position=6,
        status=STATUS_VALID,
        failure_reason=None,
        start_state={"declared_start_pose_rad": [0.0] * 7},
        reset={"achieved": True, "final_error_rad": 0.001},
        rate={"measured_hz": 200.4, "target_hz": 200.0,
              "tolerance_frac": 0.02, "within_tolerance": True},
        controller={"cycles": 2000},
        signals_summary={"n_rows": 2000},
        runtime={"platform": "aarch64"},
        files={"telemetry.csv": "e" * 64},
    )
    base.update(kw)
    return build_raw_packet(**base)


class TestNoRunDisappearsQuietly:
    def test_valid_packet_builds(self):
        assert make()["status"] == STATUS_VALID

    @pytest.mark.parametrize("status", [STATUS_INVALID, STATUS_FAILED])
    def test_non_valid_run_must_carry_a_reason(self, status):
        with pytest.raises(CampaignError, match="every exclusion must carry"):
            make(status=status, failure_reason=None)

    @pytest.mark.parametrize("status", [STATUS_INVALID, STATUS_FAILED])
    def test_non_valid_run_with_a_reason_is_accepted(self, status):
        p = make(status=status, failure_reason="rate_out_of_tolerance: 30.02 Hz")
        assert p["failure_reason"]

    def test_valid_run_may_not_carry_a_reason(self):
        with pytest.raises(CampaignError, match="is valid but carries"):
            make(status=STATUS_VALID, failure_reason="looked bad")

    def test_unknown_status_is_rejected(self):
        with pytest.raises(CampaignError, match="status must be one of"):
            make(status="probably_fine")

    def test_unknown_condition_is_rejected(self):
        with pytest.raises(CampaignError, match="unknown condition"):
            make(condition="filtered_v2")


class TestRateAdmissionCannotBeFaked:
    def test_rate_verdict_must_match_the_measurement(self):
        with pytest.raises(CampaignError, match="contradicts measured_hz"):
            make(rate={"measured_hz": 150.0, "target_hz": 200.0,
                       "tolerance_frac": 0.02, "within_tolerance": True})

    def test_a_drifted_run_cannot_be_marked_valid(self):
        with pytest.raises(CampaignError, match="marked valid but its measured rate"):
            make(status=STATUS_VALID,
                 rate={"measured_hz": 150.0, "target_hz": 200.0,
                       "tolerance_frac": 0.02, "within_tolerance": False})

    def test_a_drifted_run_is_preserved_as_invalid(self):
        p = make(status=STATUS_INVALID,
                 failure_reason="rate_out_of_tolerance: measured 150.0 Hz",
                 rate={"measured_hz": 150.0, "target_hz": 200.0,
                       "tolerance_frac": 0.02, "within_tolerance": False})
        assert p["status"] == STATUS_INVALID
        assert "150.0" in p["failure_reason"]


class TestRateStats:
    def test_uniform_sampling(self):
        t = [i / 200.0 for i in range(1000)]
        s = rate_stats(t)
        assert s["n_samples"] == 1000
        assert abs(s["measured_hz"] - 200.0) < 1e-6
        assert s["dt_stdev_s"] < 1e-12
        assert s["monotonic"] is True

    def test_a_dropped_sample_shows_up_as_an_inflated_interval(self):
        t = [i / 200.0 for i in range(100)]
        del t[50]
        s = rate_stats(t)
        assert s["dt_max_s"] > 1.5 * s["dt_mean_s"]

    def test_non_monotonic_is_reported(self):
        assert rate_stats([0.0, 0.01, 0.005])["monotonic"] is False

    def test_too_short_returns_none_rather_than_guessing(self):
        assert rate_stats([0.0])["measured_hz"] is None


class TestSignalSummary:
    def test_separates_estimate_tracking_from_true_tracking(self):
        # The controller's estimate can look perfect while the articulation is
        # nowhere near the reference. Conflating the two would let a filter
        # claim credit for a physical outcome it did not produce.
        ref = [1.0] * 10
        estimate = [1.0] * 10
        true = [0.0] * 10
        s = summarize_signals(ref, estimate, estimate, true, estimate)
        assert s["tracking_rms_error_rad"] == pytest.approx(0.0)
        assert s["true_tracking_rms_error_rad"] == pytest.approx(1.0)

    def test_peak_error_is_the_worst_sample_not_the_mean(self):
        s = summarize_signals([0.0] * 5, [0, 0, 3, 0, 0], [0] * 5, [0] * 5, [0] * 5)
        assert s["peak_tracking_error_rad"] == pytest.approx(3.0)


class TestIntegrityIsVerifiableOffline:
    def test_index_and_verify_round_trip(self, tmp_path):
        run_dir = tmp_path / "filtered-0003"
        run_dir.mkdir()
        f = run_dir / "telemetry.csv"
        f.write_text("t,reference,measured\n0,0,0\n", encoding="utf-8")
        p = make(files={"telemetry.csv": file_sha256(f)})
        index = integrity_index([p])
        assert verify_integrity(index, tmp_path)["passed"] is True

    def test_a_single_edited_byte_is_caught(self, tmp_path):
        run_dir = tmp_path / "filtered-0003"
        run_dir.mkdir()
        f = run_dir / "telemetry.csv"
        f.write_text("t,reference,measured\n0,0,0\n", encoding="utf-8")
        index = integrity_index([make(files={"telemetry.csv": file_sha256(f)})])
        f.write_text("t,reference,measured\n0,0,1\n", encoding="utf-8")
        result = verify_integrity(index, tmp_path)
        assert result["passed"] is False
        assert result["mismatched"] == ["filtered-0003/telemetry.csv"]

    def test_a_deleted_file_is_caught(self, tmp_path):
        run_dir = tmp_path / "filtered-0003"
        run_dir.mkdir()
        f = run_dir / "telemetry.csv"
        f.write_text("x\n", encoding="utf-8")
        index = integrity_index([make(files={"telemetry.csv": file_sha256(f)})])
        f.unlink()
        result = verify_integrity(index, tmp_path)
        assert result["passed"] is False
        assert result["missing"] == ["filtered-0003/telemetry.csv"]


class TestDiskRoundTrip:
    def test_round_trips(self, tmp_path):
        p = make()
        assert load_raw_packet(write_raw_packet(p, tmp_path / "r.json")) == p

    def test_corrupt_fails_closed(self, tmp_path):
        path = tmp_path / "r.json"
        path.write_text("{", encoding="utf-8")
        with pytest.raises(CampaignError, match="corrupt"):
            load_raw_packet(path)

    def test_missing_field_fails_closed(self, tmp_path):
        p = make()
        del p["rate"]
        with pytest.raises(CampaignError, match="missing required fields"):
            validate_raw_packet(p)

    def test_serialization_is_deterministic(self, tmp_path):
        a = write_raw_packet(make(), tmp_path / "a.json").read_bytes()
        b = write_raw_packet(make(), tmp_path / "b.json").read_bytes()
        assert a == b
