"""Joint-space waypoint sequencing + simple position controller (REQ-S2R-004).

Pure Python/NumPy — no ROS imports. The rclpy wrapper is
:mod:`control_loop.waypoint_controller_node`.

Design (MASTER_PLAN §6 — credible, not optimal): a proportional position-step
controller with fixed gains. Each update the commanded position moves from the
measured position toward the active waypoint by ``kp * error``, clipped to
``max_step_rad`` per joint per update. A waypoint is reached when every joint
is within its tolerance; unreachable waypoints hit ``waypoint_timeout_s`` and
the tracker latches TIMED_OUT (it never spins forever — adversarially tested).

Time is injected by the caller (``t`` in seconds, e.g. from message stamps or
the node clock); the tracker never reads a wall clock, so tests and replays
are deterministic.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

DEFAULT_TOLERANCE_RAD = 0.01


class TrackerStatus(enum.Enum):
    """Lifecycle of a waypoint plan."""

    IDLE = "idle"  # no update() received yet
    TRACKING = "tracking"  # driving toward the active waypoint
    DONE = "done"  # all waypoints reached (terminal)
    TIMED_OUT = "timed_out"  # a waypoint exceeded its timeout (terminal)


@dataclass(frozen=True)
class Waypoint:
    """One joint-space target: positions (radians) + per-waypoint tolerance."""

    positions: Tuple[float, ...]
    tolerance_rad: float = DEFAULT_TOLERANCE_RAD

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "positions", tuple(float(p) for p in self.positions)
        )
        if len(self.positions) == 0:
            raise ValueError("waypoint must have at least one joint position")
        if not all(math.isfinite(p) for p in self.positions):
            raise ValueError(f"waypoint positions must be finite: {self.positions}")
        if self.tolerance_rad <= 0.0:
            raise ValueError(f"tolerance_rad must be > 0, got {self.tolerance_rad}")


@dataclass
class WaypointResult:
    """Outcome record for one waypoint (feeds the evidence packet in M3)."""

    index: int
    reached: bool
    elapsed_s: float
    final_error_rad: float


@dataclass
class TrackerOutput:
    """Result of one control update."""

    command: np.ndarray  # joint positions to command this cycle
    status: TrackerStatus
    active_index: Optional[int]  # waypoint being tracked, None when terminal
    error_norm_rad: float  # inf-norm error to active/last target


@dataclass
class _Segment:
    start_t: float
    results: List[WaypointResult] = field(default_factory=list)


class WaypointTracker:
    """Sequences joint-space waypoints with a fixed-gain position controller.

    Parameters
    ----------
    waypoints:
        Ordered joint-space targets; all must share one joint count.
    kp:
        Proportional gain on position error (per update).
    max_step_rad:
        Per-joint, per-update command step clip (rate limiting).
    waypoint_timeout_s:
        Max time on one waypoint before latching TIMED_OUT.
    """

    def __init__(
        self,
        waypoints: Sequence[Waypoint],
        kp: float = 0.8,
        max_step_rad: float = 0.05,
        waypoint_timeout_s: float = 10.0,
    ) -> None:
        waypoints = list(waypoints)
        if kp <= 0.0:
            raise ValueError(f"kp must be > 0, got {kp}")
        if max_step_rad <= 0.0:
            raise ValueError(f"max_step_rad must be > 0, got {max_step_rad}")
        if waypoint_timeout_s <= 0.0:
            raise ValueError(
                f"waypoint_timeout_s must be > 0, got {waypoint_timeout_s}"
            )
        dims = {len(w.positions) for w in waypoints}
        if len(dims) > 1:
            raise ValueError(f"waypoints disagree on joint count: {sorted(dims)}")
        self._waypoints = waypoints
        self._num_joints = dims.pop() if dims else None  # None: empty plan
        self._kp = float(kp)
        self._max_step = float(max_step_rad)
        self._timeout = float(waypoint_timeout_s)
        self._index = 0
        self._status = TrackerStatus.IDLE if waypoints else TrackerStatus.DONE
        self._segment: Optional[_Segment] = None
        self._results: List[WaypointResult] = []

    @property
    def status(self) -> TrackerStatus:
        return self._status

    @property
    def results(self) -> List[WaypointResult]:
        return list(self._results)

    @property
    def done(self) -> bool:
        return self._status is TrackerStatus.DONE

    @property
    def timed_out(self) -> bool:
        return self._status is TrackerStatus.TIMED_OUT

    def _target(self) -> np.ndarray:
        return np.asarray(self._waypoints[self._index].positions, dtype=float)

    def update(self, measured_positions, t: float) -> TrackerOutput:
        """Advance one control cycle.

        Terminal states (DONE / TIMED_OUT) hold position: the command equals
        the measured positions and no further sequencing happens.
        """
        meas = np.asarray(measured_positions, dtype=float)
        if meas.ndim != 1 or (
            self._num_joints is not None and meas.shape != (self._num_joints,)
        ):
            raise ValueError(
                f"expected {self._num_joints} measured positions, got shape {meas.shape}"
            )
        if not np.all(np.isfinite(meas)):
            raise ValueError("measured positions contain non-finite values")
        if not math.isfinite(t):
            raise ValueError(f"timestamp must be finite, got {t}")

        if self._status in (TrackerStatus.DONE, TrackerStatus.TIMED_OUT):
            return TrackerOutput(meas.copy(), self._status, None, 0.0)

        if self._segment is None:
            self._segment = _Segment(start_t=t)
            self._status = TrackerStatus.TRACKING

        # Advance through any waypoints already satisfied at this sample.
        while self._index < len(self._waypoints):
            wp = self._waypoints[self._index]
            err = self._target() - meas
            err_norm = float(np.max(np.abs(err)))
            if err_norm <= wp.tolerance_rad:
                self._results.append(
                    WaypointResult(
                        index=self._index,
                        reached=True,
                        elapsed_s=t - self._segment.start_t,
                        final_error_rad=err_norm,
                    )
                )
                self._index += 1
                self._segment = _Segment(start_t=t)
                continue
            break

        if self._index >= len(self._waypoints):
            self._status = TrackerStatus.DONE
            return TrackerOutput(meas.copy(), self._status, None, 0.0)

        wp = self._waypoints[self._index]
        err = self._target() - meas
        err_norm = float(np.max(np.abs(err)))

        if t - self._segment.start_t > self._timeout:
            self._results.append(
                WaypointResult(
                    index=self._index,
                    reached=False,
                    elapsed_s=t - self._segment.start_t,
                    final_error_rad=err_norm,
                )
            )
            self._status = TrackerStatus.TIMED_OUT
            return TrackerOutput(meas.copy(), self._status, None, err_norm)

        step = np.clip(self._kp * err, -self._max_step, self._max_step)
        command = meas + step
        return TrackerOutput(command, self._status, self._index, err_norm)


def waypoints_from_flat(
    flat: Sequence[float], num_joints: int, tolerance_rad: float = DEFAULT_TOLERANCE_RAD
) -> List[Waypoint]:
    """Build waypoints from a flat parameter list (ROS param arrays are flat).

    ``flat`` length must be a positive multiple of ``num_joints``.
    """
    if num_joints <= 0:
        raise ValueError(f"num_joints must be positive, got {num_joints}")
    flat = [float(x) for x in flat]
    if len(flat) == 0 or len(flat) % num_joints != 0:
        raise ValueError(
            f"flat waypoint list length {len(flat)} is not a positive multiple "
            f"of num_joints={num_joints}"
        )
    return [
        Waypoint(tuple(flat[i : i + num_joints]), tolerance_rad)
        for i in range(0, len(flat), num_joints)
    ]
