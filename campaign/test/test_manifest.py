"""The frozen manifest must be tamper-evident and self-consistent.

These tests exist because preregistration is only worth anything if changing
the design after the fact is *visible*. A manifest that silently accepted an
edited seed list, a re-ordered execution plan, or a sampling contract the D6
guard would reject would be preregistration theater.
"""

import json

import pytest

from campaign.errors import CampaignError
from campaign.manifest import (
    CAMPAIGN_ID,
    DEFAULT_SEEDS,
    START_POSE_RAD,
    arm_order_for_seed,
    build_manifest,
    execution_plan,
    load_manifest,
    manifest_hash,
    sampling_rate_valid,
    validate_manifest,
    write_manifest,
)

ENV = {"python": "3.12.13", "numpy": "2.3.1", "scipy": "1.17.0"}


def make(**kw):
    base = dict(
        repo_commit="a" * 40,
        runtime_parent_commit="b" * 40,
        scene_graph_fingerprint="c" * 64,
        isaac_build="6.0.1-rc.7+release.42383.32955d8d.gl",
        environment=ENV,
    )
    base.update(kw)
    return build_manifest(**base)


class TestTheDesignIsActuallyFrozen:
    def test_builds_and_validates(self):
        m = make()
        assert m["campaign_id"] == CAMPAIGN_ID
        assert validate_manifest(m) is m

    def test_forty_scheduled_runs_from_twenty_seeds(self):
        m = make()
        assert m["design"]["scheduled_runs"] == 40
        assert len(m["design"]["seeds"]) == 20
        plan = m["design"]["execution_plan"]
        assert sum(1 for p in plan if p["condition"] == "filtered") == 20
        assert sum(1 for p in plan if p["condition"] == "unfiltered") == 20

    def test_every_seed_appears_in_both_conditions(self):
        m = make()
        plan = m["design"]["execution_plan"]
        for seed in m["design"]["seeds"]:
            conds = {p["condition"] for p in plan if p["seed"] == seed}
            assert conds == {"filtered", "unfiltered"}, f"seed {seed}: {conds}"

    def test_arm_order_is_balanced_across_seed_pairs(self):
        # Order confounding is the thing this policy exists to prevent: if
        # filtered always ran first, anything that drifts with execution
        # position would load one condition and not the other.
        firsts = [arm_order_for_seed(s)[0] for s in DEFAULT_SEEDS]
        assert firsts.count("filtered") == firsts.count("unfiltered") == 10

    def test_execution_positions_are_dense_and_ordered(self):
        plan = execution_plan(DEFAULT_SEEDS)
        assert [p["position"] for p in plan] == list(range(40))

    def test_run_ids_match_the_aggregator_convention(self):
        from campaign.aggregate import classify_condition

        for entry in execution_plan(DEFAULT_SEEDS):
            assert classify_condition(entry["run_id"]) == entry["condition"]

    def test_start_pose_is_inside_the_franka_limits(self):
        # A start pose outside the limits would be silently clamped, so every
        # run would begin somewhere other than where the manifest claims.
        import sys
        from pathlib import Path

        sys.path.insert(
            0, str(Path(__file__).resolve().parents[2] / "ros2-ws" / "src" / "control_loop")
        )
        from control_loop.logic.franka_limits import ARM_JOINT_NAMES, limits_for

        for p, (lo, hi) in zip(START_POSE_RAD, limits_for(list(ARM_JOINT_NAMES))):
            assert lo <= p <= hi


class TestTamperEvidence:
    def test_hash_matches_the_body(self):
        m = make()
        assert m["manifest_sha256"] == manifest_hash(m)

    def test_editing_a_frozen_value_is_detected(self):
        m = make()
        m["filter"]["cutoff_hz"] = 4.0
        with pytest.raises(CampaignError, match="does not match the manifest body"):
            validate_manifest(m)

    def test_dropping_a_seed_is_detected(self):
        m = make()
        m["design"]["seeds"] = m["design"]["seeds"][:-1]
        with pytest.raises(CampaignError):
            validate_manifest(m)

    def test_reordering_the_execution_plan_is_detected(self):
        m = make()
        m["design"]["execution_plan"].reverse()
        with pytest.raises(CampaignError, match="execution_plan does not match"):
            validate_manifest(m)

    def test_missing_top_level_field_is_detected(self):
        m = make()
        del m["analysis"]
        with pytest.raises(CampaignError, match="missing required fields"):
            validate_manifest(m)

    def test_round_trips_through_disk(self, tmp_path):
        m = make()
        path = write_manifest(m, tmp_path / "m.json")
        assert load_manifest(path) == m

    def test_corrupt_file_fails_closed(self, tmp_path):
        path = tmp_path / "m.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(CampaignError, match="corrupt"):
            load_manifest(path)

    def test_missing_file_fails_closed(self, tmp_path):
        with pytest.raises(CampaignError, match="not found"):
            load_manifest(tmp_path / "nope.json")

    def test_serialization_is_deterministic(self, tmp_path):
        a = write_manifest(make(), tmp_path / "a.json").read_bytes()
        b = write_manifest(make(), tmp_path / "b.json").read_bytes()
        assert a == b


class TestTheSamplingContractCannotBeIncoherent:
    def test_rejects_cutoff_above_the_vibration(self):
        m = make()
        m["filter"]["cutoff_hz"] = 30.0
        m["manifest_sha256"] = manifest_hash(m)
        with pytest.raises(CampaignError, match="incoherent"):
            validate_manifest(m)

    def test_rejects_vibration_above_nyquist(self):
        # The exact D6 defect, expressed as a manifest rather than a launch file.
        m = make()
        m["sampling"]["sample_rate_hz"] = 30.0
        m["filter"]["sample_rate_hz"] = 30.0
        m["manifest_sha256"] = manifest_hash(m)
        with pytest.raises(CampaignError, match="incoherent"):
            validate_manifest(m)

    def test_the_frozen_config_passes_the_committed_d6_guard(self):
        import sys
        from pathlib import Path

        sys.path.insert(
            0, str(Path(__file__).resolve().parents[2] / "ros2-ws" / "src" / "control_loop")
        )
        from control_loop.logic.sampling import assert_campaign_sampling_valid

        m = make()
        assert_campaign_sampling_valid(
            sample_rate_hz=m["sampling"]["sample_rate_hz"],
            vibration_freq_hz=m["disturbance"]["vibration_freq_hz"],
            cutoff_hz=m["filter"]["cutoff_hz"],
        )


class TestRateAdmission:
    @pytest.mark.parametrize("hz,ok", [
        (200.0, True), (200.492, True), (204.0, True), (196.0, True),
        (205.0, False), (195.0, False), (30.02, False), (0.0, False),
        (None, False),
    ])
    def test_tolerance_boundary(self, hz, ok):
        assert sampling_rate_valid(hz, 200.0, 0.02) is ok


class TestCommittedManifest:
    """The manifest actually committed to this repo must still be valid."""

    def test_committed_manifests_load(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "manifests"
        if not root.is_dir():
            pytest.skip("no committed manifests yet")
        found = sorted(root.glob("*.json"))
        assert found, "manifests/ exists but is empty"
        for path in found:
            m = load_manifest(path)
            assert m["design"]["scheduled_runs"] == 40
            assert json.loads(path.read_text())["manifest_sha256"] == manifest_hash(m)
