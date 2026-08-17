"""Validate the COMMITTED campaign evidence — offline, no simulator, no GPU.

This is the test that makes the campaign checkable by someone who does not have
the machine it ran on. It reads only files in the repository: it re-hashes every
evidence file against the digest recorded in its own packet, re-derives the
execution plan from the frozen manifest, and confirms the counts and the rate
contract hold for every scheduled run.

If a run were quietly deleted, edited, produced against a different manifest, or
marked valid despite drifting outside the frozen rate tolerance, one of these
tests fails. That is the entire point: "the evidence is intact" should be a
thing you can run, not a thing you are told.

The suite skips cleanly when no campaign has been committed yet, so it is safe
in CI before the first campaign lands.
"""

from pathlib import Path

import pytest

from campaign.manifest import file_sha256, load_manifest, sampling_rate_valid
from campaign.raw_evidence import (
    STATUS_VALID,
    integrity_index,
    load_raw_packet,
    verify_integrity,
)

REPO = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO / "campaign" / "manifests"
RESULTS_DIR = REPO / "campaign" / "results"


def _campaigns():
    if not MANIFEST_DIR.is_dir() or not RESULTS_DIR.is_dir():
        return []
    out = []
    for mpath in sorted(MANIFEST_DIR.glob("*.json")):
        logs = RESULTS_DIR / mpath.stem
        if logs.is_dir():
            out.append((mpath, logs))
    return out


CAMPAIGNS = _campaigns()
pytestmark = pytest.mark.skipif(
    not CAMPAIGNS, reason="no committed campaign evidence yet"
)


@pytest.fixture(params=CAMPAIGNS, ids=lambda c: c[0].stem)
def campaign(request):
    mpath, logs = request.param
    manifest = load_manifest(mpath)
    packets = {}
    for entry in manifest["design"]["execution_plan"]:
        p = logs / entry["run_id"] / "raw_evidence.json"
        if p.is_file():
            packets[entry["run_id"]] = load_raw_packet(p)
    return manifest, logs, packets


class TestEveryScheduledRunIsPresent:
    def test_no_run_is_missing(self, campaign):
        manifest, _, packets = campaign
        scheduled = [e["run_id"] for e in manifest["design"]["execution_plan"]]
        missing = [r for r in scheduled if r not in packets]
        assert not missing, f"scheduled runs with no evidence: {missing}"

    def test_the_count_is_the_preregistered_one(self, campaign):
        manifest, _, packets = campaign
        assert len(packets) == manifest["design"]["scheduled_runs"] == 40

    def test_twenty_per_condition(self, campaign):
        _, _, packets = campaign
        for cond in ("filtered", "unfiltered"):
            n = sum(1 for p in packets.values() if p["condition"] == cond)
            assert n == 20, f"{cond}: {n}"

    def test_every_seed_is_paired(self, campaign):
        manifest, _, packets = campaign
        for seed in manifest["design"]["seeds"]:
            conds = {p["condition"] for p in packets.values() if p["seed"] == seed}
            assert conds == {"filtered", "unfiltered"}, f"seed {seed}: {conds}"

    def test_no_extra_run_directories_snuck_in(self, campaign):
        # An unscheduled run appearing in the evidence tree would mean the
        # campaign was extended after the fact.
        manifest, logs, _ = campaign
        scheduled = {e["run_id"] for e in manifest["design"]["execution_plan"]}
        found = {d.name for d in logs.iterdir()
                 if d.is_dir() and (d / "raw_evidence.json").is_file()}
        assert found - scheduled == set()


class TestProvenance:
    def test_every_run_cites_the_frozen_manifest(self, campaign):
        # Pooling runs from two manifests would be pooling two experiments.
        manifest, _, packets = campaign
        for run_id, p in packets.items():
            assert p["manifest_sha256"] == manifest["manifest_sha256"], run_id

    def test_execution_positions_match_the_frozen_plan(self, campaign):
        manifest, _, packets = campaign
        for entry in manifest["design"]["execution_plan"]:
            p = packets[entry["run_id"]]
            assert p["execution_position"] == entry["position"]
            assert p["condition"] == entry["condition"]
            assert p["seed"] == entry["seed"]

    def test_scenario_is_not_the_synthetic_one(self, campaign):
        # campaign/synth.py output carries a "-synthetic" suffix and must never
        # be presented as an empirical campaign result.
        _, _, packets = campaign
        for run_id, p in packets.items():
            assert not p["scenario"].endswith("-synthetic"), run_id


class TestIntegrity:
    def test_every_recorded_hash_matches_the_bytes_on_disk(self, campaign):
        _, logs, packets = campaign
        result = verify_integrity(integrity_index(list(packets.values())), logs)
        assert result["passed"], (
            f"mismatched={result['mismatched']} missing={result['missing']}"
        )

    def test_the_index_covers_the_telemetry_of_every_run(self, campaign):
        _, _, packets = campaign
        for run_id, p in packets.items():
            assert "telemetry.csv" in p["files"], run_id
            assert "run_meta.json" in p["files"], run_id

    def test_hashes_are_recomputed_not_trusted(self, campaign):
        _, logs, packets = campaign
        for run_id, p in packets.items():
            path = logs / run_id / "telemetry.csv"
            assert file_sha256(path) == p["files"]["telemetry.csv"], run_id


class TestTheRateContractHeldPerRun:
    def test_no_valid_run_drifted_outside_the_frozen_tolerance(self, campaign):
        manifest, _, packets = campaign
        target = manifest["sampling"]["sample_rate_hz"]
        tol = manifest["sampling"]["rate_tolerance_frac"]
        for run_id, p in packets.items():
            if p["status"] != STATUS_VALID:
                continue
            assert sampling_rate_valid(p["rate"]["measured_hz"], target, tol), (
                f"{run_id}: {p['rate']['measured_hz']} Hz"
            )

    def test_every_run_carries_its_own_rate_evidence(self, campaign):
        # The preflight measurement does not stay true by assumption.
        _, _, packets = campaign
        for run_id, p in packets.items():
            assert p["rate"]["n_samples"] > 1, run_id
            assert p["rate"]["dt_mean_s"] is not None, run_id

    def test_timestamps_are_monotonic(self, campaign):
        _, _, packets = campaign
        for run_id, p in packets.items():
            if p["status"] == STATUS_VALID:
                assert p["rate"]["monotonic"], run_id


class TestRunContract:
    def test_valid_runs_have_the_preregistered_length(self, campaign):
        manifest, _, packets = campaign
        n = manifest["run_contract"]["samples_per_run"]
        for run_id, p in packets.items():
            if p["status"] == STATUS_VALID:
                assert p["signals_summary"]["n_rows"] == n, run_id

    def test_every_valid_run_started_from_the_declared_pose(self, campaign):
        manifest, _, packets = campaign
        tol = manifest["run_contract"]["reset_tolerance_rad"]
        for run_id, p in packets.items():
            if p["status"] != STATUS_VALID:
                continue
            assert p["reset"]["achieved"], run_id
            assert p["reset"]["final_error_rad"] <= tol, run_id

    def test_the_reference_span_is_identical_across_conditions(self, campaign):
        # The pilot's confound: an endogenous reference gave the two arms
        # different spans, which silently changed overshoot_pct's denominator.
        _, _, packets = campaign
        spans = {p["signals_summary"]["reference_span_rad"]
                 for p in packets.values() if p["status"] == STATUS_VALID}
        assert len(spans) == 1, f"reference spans differ across runs: {spans}"

    def test_excluded_runs_carry_an_exact_reason(self, campaign):
        _, _, packets = campaign
        for run_id, p in packets.items():
            if p["status"] != STATUS_VALID:
                assert p["failure_reason"], run_id
