"""CLI tests (REQ-S2R-102): end-to-end over synthetic evidence directories."""

import json

from campaign.cli import EXIT_IMPROVED, EXIT_INVALID, EXIT_NO_IMPROVEMENT, main
from campaign.synth import make_packet, write_campaign
from gauntlet.evidence import write_packet


def test_improved_campaign_exit_zero(campaign_dir, tmp_path, capsys):
    out = tmp_path / "out"
    rc = main([str(campaign_dir), "--out-dir", str(out)])
    assert rc == EXIT_IMPROVED
    assert (out / "results_table.md").is_file()
    doc = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert doc["packets_used"] == 8
    assert "pass rate" in capsys.readouterr().out.lower()


def test_default_out_dir_is_evidence_dir(campaign_dir):
    assert main([str(campaign_dir)]) == EXIT_IMPROVED
    assert (campaign_dir / "results_table.md").is_file()
    assert (campaign_dir / "results.json").is_file()


def test_regression_exit_one(tmp_path):
    d = tmp_path / "ev"
    write_packet(make_packet("unfiltered", 1, index=1,
                 overrides={"tracking_rms_error": 0.10}), d)
    write_packet(make_packet("filtered", 1, index=1,
                 overrides={"tracking_rms_error": 0.20}), d)
    assert main([str(d)]) == EXIT_NO_IMPROVEMENT


def test_empty_dir_exit_two_no_output(tmp_path, capsys):
    d = tmp_path / "empty"
    d.mkdir()
    assert main([str(d)]) == EXIT_INVALID
    err = capsys.readouterr().err
    assert "campaign: error:" in err
    assert not (d / "results_table.md").exists()


def test_malformed_skip_warns_on_stderr(campaign_dir, capsys):
    (campaign_dir / "run-filtered-9999.json").write_text("{bad", encoding="utf-8")
    main([str(campaign_dir)])
    assert "campaign: warning:" in capsys.readouterr().err


def test_timestamp_embedded(campaign_dir, tmp_path):
    out = tmp_path / "out"
    main([str(campaign_dir), "--out-dir", str(out), "--timestamp", "2026-07-19T12:00:00Z"])
    doc = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert doc["generated_at"] == "2026-07-19T12:00:00Z"
