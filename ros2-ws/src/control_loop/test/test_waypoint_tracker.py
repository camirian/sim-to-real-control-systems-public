"""Tests for control_loop.logic.waypoint_tracker (REQ-S2R-004). No ROS required."""

import numpy as np
import pytest

from control_loop.logic.waypoint_tracker import (
    TrackerStatus,
    Waypoint,
    WaypointTracker,
    waypoints_from_flat,
)

DT = 1.0 / 200.0


def simulate(tracker, start, max_steps=20000, plant_gain=1.0):
    """Ideal plant: the arm lands exactly on the commanded position each step.

    Returns (positions_history, steps_used).
    """
    pos = np.asarray(start, dtype=float)
    history = [pos.copy()]
    for i in range(max_steps):
        out = tracker.update(pos, i * DT)
        if out.status in (TrackerStatus.DONE, TrackerStatus.TIMED_OUT):
            return history, i
        pos = pos + plant_gain * (out.command - pos)
        history.append(pos.copy())
    return history, max_steps


class TestSequencing:
    def test_reaches_single_waypoint(self):
        wp = Waypoint((0.5, -0.5), tolerance_rad=0.01)
        tracker = WaypointTracker([wp], kp=0.8, max_step_rad=0.05)
        history, _ = simulate(tracker, [0.0, 0.0])
        assert tracker.status is TrackerStatus.DONE
        assert np.all(np.abs(history[-1] - np.array([0.5, -0.5])) <= 0.01)
        results = tracker.results
        assert len(results) == 1 and results[0].reached

    def test_reaches_waypoints_in_order(self):
        wps = [
            Waypoint((0.3,), tolerance_rad=0.01),
            Waypoint((-0.2,), tolerance_rad=0.01),
            Waypoint((0.1,), tolerance_rad=0.01),
        ]
        tracker = WaypointTracker(wps)
        simulate(tracker, [0.0])
        assert tracker.status is TrackerStatus.DONE
        assert [r.index for r in tracker.results] == [0, 1, 2]
        assert all(r.reached for r in tracker.results)
        # elapsed times are non-negative and errors within tolerance
        assert all(r.elapsed_s >= 0.0 for r in tracker.results)
        assert all(r.final_error_rad <= 0.01 for r in tracker.results)

    def test_command_step_is_rate_limited(self):
        tracker = WaypointTracker([Waypoint((10.0,))], kp=5.0, max_step_rad=0.05)
        out = tracker.update(np.array([0.0]), 0.0)
        assert out.command[0] == pytest.approx(0.05)

    def test_command_moves_toward_target(self):
        tracker = WaypointTracker([Waypoint((-1.0,))], kp=0.5, max_step_rad=1.0)
        out = tracker.update(np.array([0.0]), 0.0)
        assert out.command[0] == pytest.approx(-0.5)

    def test_empty_plan_is_done_immediately(self):
        tracker = WaypointTracker([])
        assert tracker.status is TrackerStatus.DONE
        out = tracker.update(np.array([1.0, 2.0]), 0.0)
        assert out.status is TrackerStatus.DONE
        assert np.array_equal(out.command, np.array([1.0, 2.0]))  # hold

    def test_already_at_waypoint_advances_without_motion(self):
        tracker = WaypointTracker([Waypoint((0.0, 0.0), tolerance_rad=0.01)])
        out = tracker.update(np.zeros(2), 0.0)
        assert out.status is TrackerStatus.DONE


class TestTimeout:
    """Adversarial gate: unreachable waypoints must time out, never loop."""

    def test_unreachable_waypoint_times_out(self):
        # Plant frozen (gain 0): the arm never moves, target never reached.
        tracker = WaypointTracker(
            [Waypoint((1.0,), tolerance_rad=0.001)], waypoint_timeout_s=2.0
        )
        history, steps = simulate(tracker, [0.0], plant_gain=0.0)
        assert tracker.status is TrackerStatus.TIMED_OUT
        # ~2 s at 200 Hz -> ~400 updates, definitely not the max_steps loop cap.
        assert steps < 500
        results = tracker.results
        assert len(results) == 1
        assert not results[0].reached
        assert results[0].final_error_rad == pytest.approx(1.0)

    def test_timeout_is_terminal_and_holds_position(self):
        tracker = WaypointTracker(
            [Waypoint((1.0,), tolerance_rad=0.001)], waypoint_timeout_s=0.5
        )
        simulate(tracker, [0.0], plant_gain=0.0)
        assert tracker.timed_out
        out = tracker.update(np.array([0.3]), 100.0)
        assert out.status is TrackerStatus.TIMED_OUT
        assert np.array_equal(out.command, np.array([0.3]))  # hold, no chasing
        assert len(tracker.results) == 1  # no duplicate result records

    def test_later_waypoints_not_attempted_after_timeout(self):
        tracker = WaypointTracker(
            [Waypoint((5.0,), tolerance_rad=0.001), Waypoint((0.1,))],
            waypoint_timeout_s=1.0,
            max_step_rad=0.001,  # too slow to get there in time
        )
        simulate(tracker, [0.0])
        assert tracker.timed_out
        assert [r.index for r in tracker.results] == [0]

    def test_done_is_terminal(self):
        tracker = WaypointTracker([Waypoint((0.1,), tolerance_rad=0.2)])
        tracker.update(np.array([0.0]), 0.0)
        assert tracker.done
        out = tracker.update(np.array([9.0]), 1.0)
        assert out.status is TrackerStatus.DONE
        assert np.array_equal(out.command, np.array([9.0]))


class TestValidation:
    def test_rejects_mixed_joint_counts(self):
        with pytest.raises(ValueError, match="disagree"):
            WaypointTracker([Waypoint((0.0,)), Waypoint((0.0, 1.0))])

    def test_rejects_wrong_measurement_size(self):
        tracker = WaypointTracker([Waypoint((0.0, 0.0))])
        with pytest.raises(ValueError, match="measured positions"):
            tracker.update(np.zeros(3), 0.0)

    def test_rejects_nonfinite_measurement(self):
        tracker = WaypointTracker([Waypoint((0.0,))])
        with pytest.raises(ValueError, match="non-finite"):
            tracker.update(np.array([np.nan]), 0.0)

    def test_rejects_nonfinite_waypoint(self):
        with pytest.raises(ValueError, match="finite"):
            Waypoint((float("inf"),))

    def test_rejects_bad_gains(self):
        with pytest.raises(ValueError, match="kp"):
            WaypointTracker([Waypoint((0.0,))], kp=0.0)
        with pytest.raises(ValueError, match="max_step_rad"):
            WaypointTracker([Waypoint((0.0,))], max_step_rad=-1.0)
        with pytest.raises(ValueError, match="waypoint_timeout_s"):
            WaypointTracker([Waypoint((0.0,))], waypoint_timeout_s=0.0)

    def test_rejects_nonpositive_tolerance(self):
        with pytest.raises(ValueError, match="tolerance_rad"):
            Waypoint((0.0,), tolerance_rad=0.0)


class TestFlatParamHelper:
    def test_builds_waypoints_from_flat_list(self):
        wps = waypoints_from_flat([1, 2, 3, 4, 5, 6], num_joints=3)
        assert len(wps) == 2
        assert wps[0].positions == (1.0, 2.0, 3.0)
        assert wps[1].positions == (4.0, 5.0, 6.0)

    def test_rejects_bad_length(self):
        with pytest.raises(ValueError, match="multiple"):
            waypoints_from_flat([1.0, 2.0, 3.0], num_joints=2)
        with pytest.raises(ValueError, match="multiple"):
            waypoints_from_flat([], num_joints=2)


class TestJointLimits:
    """Command bounding against the simulated articulation's limits.

    Not a safety function — see logic.franka_limits. What this buys the
    campaign is that a run cannot emit commands the articulation could never
    hold, which would put physically meaningless numbers into an evidence
    packet.
    """

    LIMITS = [(-1.0, 1.0), (-2.0, 2.0)]

    def test_command_is_clipped_into_the_limit_box(self):
        # kp > 1 overshoots the target: error 0.9 * gain 2.0 = a 1.8 rad step
        # from 0.0, i.e. a command of 1.8 against an upper limit of 1.0. This
        # is the realistic way the limit gets hit — an aggressive gain, not an
        # out-of-range target (those are rejected at construction).
        tracker = WaypointTracker(
            [Waypoint((0.9, 0.0))], kp=2.0, max_step_rad=10.0, joint_limits=self.LIMITS
        )
        out = tracker.update([0.0, 0.0], 0.0)
        assert out.command[0] == 1.0
        assert out.limit_clamped is True

    def test_unclamped_command_reports_false(self):
        tracker = WaypointTracker(
            [Waypoint((0.5, 0.0))], kp=0.5, max_step_rad=0.05, joint_limits=self.LIMITS
        )
        out = tracker.update([0.0, 0.0], 0.0)
        assert out.limit_clamped is False
        assert -1.0 <= out.command[0] <= 1.0

    def test_every_command_of_a_full_run_stays_inside_the_limits(self):
        tracker = WaypointTracker(
            [Waypoint((0.9, 1.9)), Waypoint((-0.9, -1.9))],
            kp=0.8,
            max_step_rad=0.05,
            joint_limits=self.LIMITS,
        )
        pos = np.array([0.0, 0.0])
        for i in range(5000):
            out = tracker.update(pos, i * DT)
            assert out.command[0] >= -1.0 and out.command[0] <= 1.0
            assert out.command[1] >= -2.0 and out.command[1] <= 2.0
            pos = out.command
            if tracker.status in (TrackerStatus.DONE, TrackerStatus.TIMED_OUT):
                break
        assert tracker.status is TrackerStatus.DONE

    def test_terminal_hold_is_also_clamped(self):
        # A measurement outside the limits (sensor noise, a nudged sim) must
        # not be echoed back as a command verbatim once the plan is terminal.
        tracker = WaypointTracker([Waypoint((0.0, 0.0))], joint_limits=self.LIMITS)
        tracker.update([0.0, 0.0], 0.0)  # reaches immediately -> DONE
        assert tracker.status is TrackerStatus.DONE
        out = tracker.update([9.0, 0.0], 1.0)
        assert out.command[0] == 1.0
        assert out.limit_clamped is True

    def test_unreachable_waypoint_is_rejected_at_construction(self):
        # Outside the limits the waypoint can never be reached, so it would
        # burn waypoint_timeout_s and land in the evidence as a TIMED_OUT run.
        # That is a plan defect, not a result — fail loudly instead.
        with pytest.raises(ValueError, match="outside its limits"):
            WaypointTracker([Waypoint((5.0, 0.0))], joint_limits=self.LIMITS)

    def test_rejects_limit_table_of_the_wrong_width(self):
        with pytest.raises(ValueError, match="joint_limits has"):
            WaypointTracker([Waypoint((0.0, 0.0))], joint_limits=[(-1.0, 1.0)])

    def test_rejects_inverted_limits(self):
        with pytest.raises(ValueError, match="lower < upper"):
            WaypointTracker([Waypoint((0.0,))], joint_limits=[(1.0, -1.0)])

    def test_no_limits_means_unbounded_and_never_clamped(self):
        tracker = WaypointTracker([Waypoint((100.0,))], kp=1.0, max_step_rad=10.0)
        out = tracker.update([0.0], 0.0)
        assert out.limit_clamped is False


class TestFrankaLimitTable:
    """The limit table's own contract (values are asset-derived, not invented)."""

    def test_covers_exactly_the_seven_controlled_arm_joints(self):
        from control_loop.logic.franka_limits import (
            ARM_JOINT_NAMES,
            FRANKA_JOINT_LIMITS_RAD,
        )

        assert set(FRANKA_JOINT_LIMITS_RAD) == set(ARM_JOINT_NAMES)
        assert len(ARM_JOINT_NAMES) == 7

    def test_default_waypoint_plan_is_inside_the_limits(self):
        # Guards the shipped default plan: if someone edits
        # DEFAULT_WAYPOINTS_FLAT into an unreachable pose, every campaign run
        # would time out and the money table would fill with failures.
        from control_loop.logic.franka_limits import ARM_JOINT_NAMES, within_limits
        from control_loop.logic.waypoint_tracker import DEFAULT_WAYPOINTS_FLAT

        DEFAULT_JOINT_NAMES = ARM_JOINT_NAMES
        n = len(DEFAULT_JOINT_NAMES)
        assert len(DEFAULT_WAYPOINTS_FLAT) % n == 0
        for i in range(0, len(DEFAULT_WAYPOINTS_FLAT), n):
            chunk = DEFAULT_WAYPOINTS_FLAT[i : i + n]
            assert within_limits(DEFAULT_JOINT_NAMES, chunk), chunk

    def test_degrees_and_radians_tables_agree(self):
        import math

        from control_loop.logic.franka_limits import (
            FRANKA_JOINT_LIMITS_DEG,
            FRANKA_JOINT_LIMITS_RAD,
        )

        for name, (lo_d, hi_d) in FRANKA_JOINT_LIMITS_DEG.items():
            lo_r, hi_r = FRANKA_JOINT_LIMITS_RAD[name]
            assert lo_r == pytest.approx(math.radians(lo_d))
            assert hi_r == pytest.approx(math.radians(hi_d))

    def test_matches_the_published_franka_panda_limits(self):
        # Independent corroboration that the asset table is the real robot's:
        # converted to radians it reproduces Franka Emika's published limits.
        from control_loop.logic.franka_limits import FRANKA_JOINT_LIMITS_RAD

        published = {
            "panda_joint1": (-2.8973, 2.8973),
            "panda_joint2": (-1.7628, 1.7628),
            "panda_joint3": (-2.8973, 2.8973),
            "panda_joint4": (-3.0718, -0.0698),
            "panda_joint5": (-2.8973, 2.8973),
            "panda_joint6": (-0.0175, 3.7525),
            "panda_joint7": (-2.8973, 2.8973),
        }
        for name, (lo, hi) in published.items():
            got_lo, got_hi = FRANKA_JOINT_LIMITS_RAD[name]
            assert got_lo == pytest.approx(lo, abs=1e-4)
            assert got_hi == pytest.approx(hi, abs=1e-4)

    def test_unknown_joint_raises_rather_than_silently_unbounding(self):
        from control_loop.logic.franka_limits import limits_for

        with pytest.raises(KeyError, match="no limit table entry"):
            limits_for(["panda_joint1", "not_a_joint"])
