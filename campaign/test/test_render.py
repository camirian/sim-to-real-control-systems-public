"""Rendering tests (REQ-S2R-102): results.json + results_table.md."""

import json

from campaign.aggregate import aggregate_directory
from campaign.render import (
    render_results_json,
    render_results_table,
    write_results,
)
from campaign.synth import write_campaign


class TestJson:
    def test_strict_json_and_inf_encoded(self, campaign_dir):
        r = aggregate_directory(campaign_dir)
        doc = json.loads(render_results_json(r))  # must be strict JSON
        # Unfiltered settling mean is inf -> encoded as the string "inf".
        assert doc["conditions"]["unfiltered"]["metrics"]["settling_time_s"]["mean"] == "inf"
        assert doc["conditions"]["filtered"]["metrics"]["tracking_rms_error"]["mean"] != "inf"

    def test_deterministic_bytes(self, campaign_dir):
        r1 = aggregate_directory(campaign_dir, generated_at="2026-01-01T00:00:00Z")
        r2 = aggregate_directory(campaign_dir, generated_at="2026-01-01T00:00:00Z")
        assert render_results_json(r1) == render_results_json(r2)

    def test_trailing_newline(self, campaign_dir):
        assert render_results_json(aggregate_directory(campaign_dir)).endswith("\n")

    def test_runs_and_deltas_present(self, campaign_dir):
        doc = json.loads(render_results_json(aggregate_directory(campaign_dir)))
        assert len(doc["runs"]) == 8
        assert set(doc["deltas"]) == {
            "tracking_rms_error", "settling_time_s",
            "overshoot_pct", "filter_attenuation_db",
        }


class TestTable:
    def test_has_money_table_sections(self, campaign_dir):
        md = render_results_table(aggregate_directory(campaign_dir))
        assert "# Campaign results" in md
        assert "## Headline" in md
        assert "## Per-condition summary" in md
        assert "## Metric deltas" in md
        assert "## Per-run detail" in md
        assert "filtered" in md and "unfiltered" in md

    def test_regression_shows_no(self, tmp_path):
        from campaign.synth import make_packet
        from gauntlet.evidence import write_packet
        d = tmp_path / "ev"
        write_packet(make_packet("unfiltered", 1, index=1,
                     overrides={"tracking_rms_error": 0.10}), d)
        write_packet(make_packet("filtered", 1, index=1,
                     overrides={"tracking_rms_error": 0.20}), d)
        md = render_results_table(aggregate_directory(d))
        assert "| NO |" in md  # honest "Better? = NO" on the RMS regression row

    def test_deterministic(self, campaign_dir):
        r = aggregate_directory(campaign_dir, generated_at="2026-01-01T00:00:00Z")
        assert render_results_table(r) == render_results_table(r)

    def test_warnings_section_when_skips(self, campaign_dir):
        (campaign_dir / "run-filtered-9999.json").write_text("{bad", encoding="utf-8")
        md = render_results_table(aggregate_directory(campaign_dir))
        assert "## Warnings" in md


class TestWrite:
    def test_writes_both_files(self, campaign_dir, tmp_path):
        r = aggregate_directory(campaign_dir)
        out = tmp_path / "out"
        table_path, json_path = write_results(r, out)
        assert table_path.name == "results_table.md"
        assert json_path.name == "results.json"
        assert table_path.is_file() and json_path.is_file()
        json.loads(json_path.read_text(encoding="utf-8"))
