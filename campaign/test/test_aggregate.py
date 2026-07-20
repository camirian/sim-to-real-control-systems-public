"""Aggregation tests (REQ-S2R-102). Synthetic packets built via gauntlet.evidence."""

import json
import math

import pytest

from campaign import FILTERED, UNFILTERED
from campaign.aggregate import aggregate_directory, classify_condition
from campaign.errors import CampaignError
from campaign.synth import make_packet, write_campaign
from gauntlet.evidence import write_packet


class TestClassify:
    def test_prefix_before_first_hyphen(self):
        assert classify_condition("filtered-0007") == "filtered"
        assert classify_condition("unfiltered-0007") == "unfiltered"

    def test_case_insensitive(self):
        assert classify_condition("Filtered-1") == "filtered"

    def test_unrecognized_is_none(self):
        assert classify_condition("clean-0001") is None
        assert classify_condition("garbage") is None


class TestHappyPath:
    def test_balanced_campaign(self, campaign_dir):
        r = aggregate_directory(campaign_dir)
        assert r.n_packets_used == 8
        assert r.conditions[FILTERED].n == 4
        assert r.conditions[UNFILTERED].n == 4
        # Filtered passes everything; unfiltered fails everything.
        assert r.conditions[FILTERED].pass_rate == 1.0
        assert r.conditions[UNFILTERED].pass_rate == 0.0

    def test_all_pass_filtered_set(self, tmp_path):
        d = tmp_path / "ev"
        write_campaign(d, n_filtered=5, n_unfiltered=0)
        r = aggregate_directory(d)
        assert r.conditions[FILTERED].passed == 5
        assert r.conditions[FILTERED].pass_rate == 1.0
        assert UNFILTERED not in r.conditions
        # No delta possible with one condition; headline says so honestly.
        assert r.deltas == {}
        assert any("Incomplete comparison" in h for h in r.headline)

    def test_failing_unfiltered_set(self, tmp_path):
        d = tmp_path / "ev"
        write_campaign(d, n_filtered=0, n_unfiltered=6)
        r = aggregate_directory(d)
        assert r.conditions[UNFILTERED].passed == 0
        assert r.conditions[UNFILTERED].pass_rate == 0.0

    def test_single_run_each(self, tmp_path):
        d = tmp_path / "ev"
        write_campaign(d, n_filtered=1, n_unfiltered=1)
        r = aggregate_directory(d)
        fs = r.conditions[FILTERED].metrics["tracking_rms_error"]
        assert fs.n_present == 1
        assert fs.mean == fs.median == fs.minimum == fs.maximum
        # Delta computed even for n=1 each.
        assert r.deltas["tracking_rms_error"].improved is True

    def test_uneven_counts(self, tmp_path):
        d = tmp_path / "ev"
        write_campaign(d, n_filtered=5, n_unfiltered=3)
        r = aggregate_directory(d)
        assert r.conditions[FILTERED].n == 5
        assert r.conditions[UNFILTERED].n == 3
        assert r.deltas["tracking_rms_error"].improved is True


class TestInfHandling:
    def test_unfiltered_settling_is_inf(self, campaign_dir):
        r = aggregate_directory(campaign_dir)
        st = r.conditions[UNFILTERED].metrics["settling_time_s"]
        assert st.mean == math.inf
        assert st.n_finite == 0
        # Filtered settles finitely; the delta describes "now settles" honestly.
        delta = r.deltas["settling_time_s"]
        assert delta.improved is True
        assert delta.pct_improvement is None
        assert "never reaches the band" in delta.note


class TestDeltas:
    def test_rms_improvement_is_positive_and_signed(self, campaign_dir):
        d = aggregate_directory(campaign_dir).deltas["tracking_rms_error"]
        assert d.improved is True
        assert d.pct_improvement > 0  # filtered RMS lower than unfiltered

    def test_attenuation_higher_is_better(self, campaign_dir):
        d = aggregate_directory(campaign_dir).deltas["filter_attenuation_db"]
        assert d.improved is True
        assert d.filtered_mean > d.unfiltered_mean

    def test_honest_regression_when_filtered_loses(self, tmp_path):
        """Adversarial: a filtered set that does NOT beat unfiltered must be
        reported as a regression, never cooked into a fake win."""
        d = tmp_path / "ev"
        # Force filtered RMS WORSE than unfiltered.
        write_packet(make_packet("unfiltered", 1, index=1,
                     overrides={"tracking_rms_error": 0.10}), d)
        write_packet(make_packet("filtered", 1, index=1,
                     overrides={"tracking_rms_error": 0.20}), d)
        r = aggregate_directory(d)
        delta = r.deltas["tracking_rms_error"]
        assert delta.improved is False
        assert delta.pct_improvement < 0  # signed, honest
        assert any("REGRESSION" in h for h in r.headline)


class TestErrors:
    def test_missing_directory(self, tmp_path):
        with pytest.raises(CampaignError, match="not found"):
            aggregate_directory(tmp_path / "nope")

    def test_empty_directory(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        with pytest.raises(CampaignError, match="no evidence packets"):
            aggregate_directory(d)

    def test_all_unclassifiable_raises(self, tmp_path):
        d = tmp_path / "ev"
        # Valid packets, but run ids the aggregator cannot classify.
        p = make_packet("filtered", 1, index=1)
        p2 = dict(p, run_id="clean-0001")
        # Re-validate/write via gauntlet path by faking run id through write.
        (d).mkdir(parents=True, exist_ok=True)
        from gauntlet.evidence import dumps_packet
        # dumps_packet re-validates; run id "clean-0001" is a legal id.
        (d / "run-clean-0001.json").write_text(dumps_packet(p2), encoding="utf-8")
        with pytest.raises(CampaignError, match="no usable evidence"):
            aggregate_directory(d)


class TestMalformedSkip:
    def test_malformed_packet_skipped_with_warning(self, campaign_dir):
        # Drop a corrupt file among 8 good packets.
        (campaign_dir / "run-filtered-9999.json").write_text("{not json",
                                                             encoding="utf-8")
        r = aggregate_directory(campaign_dir)
        assert r.n_packets_found == 9
        assert r.n_packets_used == 8  # corrupt one skipped, rest aggregated
        assert any("skipped malformed packet run-filtered-9999.json" in w
                   for w in r.warnings)

    def test_unclassifiable_packet_skipped_with_warning(self, campaign_dir):
        from gauntlet.evidence import dumps_packet
        p = make_packet("filtered", 1, index=1)
        p = dict(p, run_id="clean-0001")
        (campaign_dir / "run-clean-0001.json").write_text(dumps_packet(p),
                                                         encoding="utf-8")
        r = aggregate_directory(campaign_dir)
        assert r.n_packets_used == 8
        assert any("no recognized condition prefix" in w for w in r.warnings)

    def test_tampered_verdict_packet_rejected_and_skipped(self, campaign_dir, tmp_path):
        # A packet with failing checks but overall_passed=true is rejected by
        # gauntlet.load_packet -> skipped with a warning, never counted.
        p = make_packet("unfiltered", 1, index=1)  # fails checks
        tampered = dict(p, overall_passed=True)
        (campaign_dir / "run-unfiltered-9999.json").write_text(
            json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        r = aggregate_directory(campaign_dir)
        assert r.n_packets_used == 8
        assert any("run-unfiltered-9999.json" in w and "contradicts" in w
                   for w in r.warnings)


class TestDeterminism:
    def test_timestamp_only_via_argument(self, campaign_dir):
        assert aggregate_directory(campaign_dir).generated_at is None
        r = aggregate_directory(campaign_dir, generated_at="2026-07-19T00:00:00Z")
        assert r.generated_at == "2026-07-19T00:00:00Z"
