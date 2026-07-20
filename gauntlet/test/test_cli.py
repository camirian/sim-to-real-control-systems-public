"""End-to-end CLI tests over synthesized run-log directories (REQ-S2R-100/101)."""

import json

import pytest

from gauntlet.cli import EXIT_FAILED, EXIT_INVALID, EXIT_PASSED, main
from gauntlet.evidence import load_packet
from gauntlet.test.conftest import write_run_log


def run_cli(log_dir, out_dir, *extra):
    return main([str(log_dir), "--evidence-dir", str(out_dir), *extra])


class TestVerdicts:
    def test_filtered_run_passes(self, filtered_log, tmp_path, capsys):
        out = tmp_path / "out"
        assert run_cli(filtered_log, out) == EXIT_PASSED
        packet = load_packet(out / "run-filtered-0001.json")
        assert packet["overall_passed"] is True
        assert (out / "run-filtered-0001.md").is_file()
        assert "PASSED" in capsys.readouterr().out

    def test_clean_run_passes_with_skipped_attenuation(self, clean_log, tmp_path):
        out = tmp_path / "out"
        assert run_cli(clean_log, out) == EXIT_PASSED
        packet = load_packet(out / "run-clean-0001.json")
        statuses = {c["name"]: c["status"] for c in packet["checks"]}
        assert statuses["filter_attenuation_db"] == "skipped"

    def test_noisy_run_fails(self, noisy_log, tmp_path, capsys):
        """A run that SHOULD fail a check does fail — end-to-end."""
        out = tmp_path / "out"
        assert run_cli(noisy_log, out) == EXIT_FAILED
        packet = load_packet(out / "run-noisy-0001.json")
        assert packet["overall_passed"] is False
        failed = [c["name"] for c in packet["checks"] if c["status"] == "failed"]
        assert set(failed) == {
            "tracking_rms_error",
            "settling_time_s",
            "overshoot_pct",
            "filter_attenuation_db",
        }
        report = (out / "run-noisy-0001.md").read_text(encoding="utf-8")
        assert "**Verdict: FAILED**" in report

    def test_seed_and_scenario_embedded(self, tmp_path):
        log = write_run_log(tmp_path / "log", "filtered", run_id="seeded-7", seed=7)
        out = tmp_path / "out"
        run_cli(log, out)
        packet = load_packet(out / "run-seeded-7.json")
        assert packet["seed"] == 7
        assert packet["scenario"] == "franka-joint-tracking-synthetic"


class TestDeterminism:
    def test_two_invocations_identical_bytes(self, filtered_log, tmp_path):
        out1, out2 = tmp_path / "o1", tmp_path / "o2"
        run_cli(filtered_log, out1)
        run_cli(filtered_log, out2)
        assert (out1 / "run-filtered-0001.json").read_bytes() == (
            out2 / "run-filtered-0001.json"
        ).read_bytes()
        assert (out1 / "run-filtered-0001.md").read_bytes() == (
            out2 / "run-filtered-0001.md"
        ).read_bytes()

    def test_timestamp_only_via_argument(self, filtered_log, tmp_path):
        out = tmp_path / "out"
        run_cli(filtered_log, out, "--timestamp", "2026-07-19T12:00:00Z")
        packet = load_packet(out / "run-filtered-0001.json")
        assert packet["generated_at"] == "2026-07-19T12:00:00Z"


class TestCorruptInputs:
    """Adversarial gate: empty/corrupt logs -> clean error, no false PASS."""

    def _assert_invalid(self, log_dir, tmp_path, capsys, match):
        out = tmp_path / "out"
        assert run_cli(log_dir, out) == EXIT_INVALID
        err = capsys.readouterr().err
        assert "gauntlet: error:" in err and match in err
        # No verdict artifacts may exist after a failed grade.
        assert not out.exists() or not any(out.iterdir())

    def test_missing_directory(self, tmp_path, capsys):
        self._assert_invalid(tmp_path / "nope", tmp_path, capsys, "not found")

    def test_empty_directory(self, tmp_path, capsys):
        empty = tmp_path / "empty"
        empty.mkdir()
        self._assert_invalid(empty, tmp_path, capsys, "missing run_meta.json")

    def test_corrupt_meta_json(self, filtered_log, tmp_path, capsys):
        (filtered_log / "run_meta.json").write_text("{oops", encoding="utf-8")
        self._assert_invalid(filtered_log, tmp_path, capsys, "corrupt")

    def test_meta_missing_seed(self, filtered_log, tmp_path, capsys):
        (filtered_log / "run_meta.json").write_text(
            json.dumps({"run_id": "x", "scenario": "s"}), encoding="utf-8"
        )
        self._assert_invalid(filtered_log, tmp_path, capsys, "missing fields")

    def test_telemetry_header_only(self, filtered_log, tmp_path, capsys):
        (filtered_log / "telemetry.csv").write_text(
            "t,reference,measured\n", encoding="utf-8"
        )
        self._assert_invalid(filtered_log, tmp_path, capsys, "no data rows")

    def test_telemetry_empty_file(self, filtered_log, tmp_path, capsys):
        (filtered_log / "telemetry.csv").write_text("", encoding="utf-8")
        self._assert_invalid(filtered_log, tmp_path, capsys, "is empty")

    def test_telemetry_non_numeric_cell(self, filtered_log, tmp_path, capsys):
        (filtered_log / "telemetry.csv").write_text(
            "t,reference,measured\n0.0,0.0,banana\n0.01,0.0,0.0\n", encoding="utf-8"
        )
        self._assert_invalid(filtered_log, tmp_path, capsys, "non-numeric")

    def test_telemetry_missing_column(self, filtered_log, tmp_path, capsys):
        (filtered_log / "telemetry.csv").write_text(
            "t,reference\n0.0,0.0\n", encoding="utf-8"
        )
        self._assert_invalid(filtered_log, tmp_path, capsys, "missing columns")

    def test_telemetry_ragged_row(self, filtered_log, tmp_path, capsys):
        (filtered_log / "telemetry.csv").write_text(
            "t,reference,measured\n0.0,0.0\n", encoding="utf-8"
        )
        self._assert_invalid(filtered_log, tmp_path, capsys, "expected 3 cells")

    def test_nan_in_telemetry(self, filtered_log, tmp_path, capsys):
        (filtered_log / "telemetry.csv").write_text(
            "t,reference,measured\n0.0,0.0,nan\n0.01,0.0,0.0\n", encoding="utf-8"
        )
        self._assert_invalid(filtered_log, tmp_path, capsys, "non-finite")
