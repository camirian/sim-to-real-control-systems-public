"""Tests for the pure-glue parts of run_campaign (REQ-S2R-102).

Only the NON-ROS orchestration glue is tested: the campaign plan and the
command-line builders. The live-sim execution (run_one / main) is
EDGEXPERT-VERIFY and py_compile-gated only — it is never invoked here.
"""

import sys

import pytest

from campaign import run_campaign as rc


class TestPlan:
    def test_two_conditions_per_seed(self):
        specs = rc.plan_campaign([1, 2, 3])
        assert len(specs) == 6
        assert [s.run_id for s in specs] == [
            "unfiltered-0001", "filtered-0001",
            "unfiltered-0002", "filtered-0002",
            "unfiltered-0003", "filtered-0003",
        ]

    def test_run_ids_classify_by_condition(self):
        from campaign.aggregate import classify_condition
        for spec in rc.plan_campaign([7, 42]):
            assert classify_condition(spec.run_id) == spec.condition

    def test_filter_enabled_flag(self):
        specs = {s.condition: s for s in rc.plan_campaign([1])}
        assert specs["filtered"].filter_enabled is True
        assert specs["unfiltered"].filter_enabled is False

    def test_rejects_empty_and_duplicate_seeds(self):
        with pytest.raises(ValueError, match="at least one seed"):
            rc.plan_campaign([])
        with pytest.raises(ValueError, match="duplicate"):
            rc.plan_campaign([1, 1])


class TestCommandBuilders:
    def test_launch_command_filtered(self):
        spec = rc.plan_campaign([42])[1]  # filtered-0042
        argv = rc.launch_command(spec)
        assert argv[:2] == ["ros2", "launch"]
        assert "seed:=42" in argv
        assert "filter_kind:=iir" in argv

    def test_launch_command_unfiltered_uses_passthrough(self):
        spec = rc.plan_campaign([42])[0]  # unfiltered-0042
        assert "filter_kind:=passthrough" in rc.launch_command(spec)

    def test_launch_extra_args_override(self):
        spec = rc.plan_campaign([1])[1]
        argv = rc.launch_command(spec, extra_args={"cutoff_hz": "5.0"})
        assert "cutoff_hz:=5.0" in argv

    def test_gauntlet_command(self):
        argv = rc.gauntlet_command("logs/filtered-0001", "evidence", "2026-01-01T00:00:00Z")
        assert argv[:3] == [sys.executable, "-m", "gauntlet.cli"]
        assert "logs/filtered-0001" in argv
        assert "--evidence-dir" in argv and "evidence" in argv
        assert "--timestamp" in argv

    def test_aggregate_command(self):
        argv = rc.aggregate_command("evidence", "evidence")
        assert argv[:3] == [sys.executable, "-m", "campaign.cli"]
        assert "--out-dir" in argv
