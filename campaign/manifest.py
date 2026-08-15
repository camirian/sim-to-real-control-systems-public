"""The frozen campaign manifest: preregistration as a machine-readable file.

REQ-S2R-102. A campaign manifest is written and committed BEFORE the first
empirical run and never edited afterwards. It pins every choice that could
otherwise be made after seeing results: the seed list, the arm order, the run
length, the reset contract, the rate tolerance, the exclusion rules, and the
exact DSP / controller / disturbance parameters.

Why this file exists. The failure it prevents is not fraud, it is drift: a
threshold nudged after run 12, a seed quietly replaced because it "looked
wrong", an arm order chosen once the first few numbers came in. Each is
individually defensible and collectively fatal to the comparison. Freezing the
design in a hashed artifact makes any such change visible as a diff.

Purity: no ROS, no Isaac, no NumPy. The manifest can be built, hashed, and
validated on any machine, which is what lets a public clone verify a committed
campaign without the private runtime.

The manifest hash is a sha256 over the canonical JSON of every field EXCEPT
``manifest_sha256`` itself, so the document can carry its own fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from campaign.errors import CampaignError

SCHEMA_VERSION = 1

#: The campaign this repository preregisters for Issue #9.
CAMPAIGN_ID = "m4-franka-filtered-vs-unfiltered"
CAMPAIGN_VERSION = 1

#: Deterministic seed schedule. Twenty seeds, each run under BOTH conditions,
#: giving 20 filtered + 20 unfiltered = 40 preregistered runs. Paired: a
#: filtered and an unfiltered run sharing a seed see the identical disturbance
#: realization, which is what licenses the paired-difference analysis.
DEFAULT_SEEDS: Sequence[int] = tuple(range(20))

#: Joint-space pose every run starts from (radians, ARM_JOINT_NAMES order).
#: The canonical Franka "ready" pose; verified inside the joint limits.
START_POSE_RAD: Sequence[float] = (0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785)

#: The single joint whose streams are written to telemetry.csv. The gauntlet's
#: checks are single-signal; picking one joint up front (rather than choosing
#: the most flattering one afterwards) is part of the preregistration.
REPRESENTATIVE_JOINT = "panda_joint1"

_REQUIRED_TOP_LEVEL = (
    "schema_version",
    "campaign_id",
    "campaign_version",
    "scenario",
    "provenance",
    "runtime",
    "sampling",
    "disturbance",
    "filter",
    "controller",
    "run_contract",
    "design",
    "evidence",
    "analysis",
    "non_claims",
)


def canonical_json(payload: Dict[str, Any]) -> str:
    """Deterministic serialization: sorted keys, fixed separators, LF EOL."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def manifest_hash(manifest: Dict[str, Any]) -> str:
    """sha256 over the manifest with ``manifest_sha256`` removed.

    Self-referential hashing is otherwise impossible: including the field would
    change the value it records. Excluding exactly that one key keeps the digest
    a pure function of the frozen design.
    """
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def arm_order_for_seed(seed: int) -> List[str]:
    """Preregistered, balanced condition order within a seed pair.

    Even seeds run filtered first, odd seeds unfiltered first. With 20 seeds
    that is exactly 10 pairs each way, so any drift that depends on execution
    position (thermal, cache, accumulated simulator state) loads both conditions
    equally instead of confounding the comparison. Frozen before run 1 and never
    changed after looking at a result.
    """
    return ["filtered", "unfiltered"] if seed % 2 == 0 else ["unfiltered", "filtered"]


def execution_plan(seeds: Sequence[int] = DEFAULT_SEEDS) -> List[Dict[str, Any]]:
    """The exact ordered list of runs, with run ids and execution positions.

    Deterministic and pure: the same seed list always yields the same plan, so
    the order the campaign actually executed can be re-derived and checked
    against the manifest rather than taken on trust.
    """
    if not seeds:
        raise CampaignError("campaign needs at least one seed")
    if len(set(seeds)) != len(seeds):
        raise CampaignError(f"duplicate seeds in {list(seeds)}")
    plan: List[Dict[str, Any]] = []
    for seed in seeds:
        for condition in arm_order_for_seed(int(seed)):
            plan.append(
                {
                    "position": len(plan),
                    "run_id": f"{condition}-{int(seed):04d}",
                    "condition": condition,
                    "seed": int(seed),
                }
            )
    return plan


def build_manifest(
    repo_commit: str,
    runtime_parent_commit: str,
    scene_graph_fingerprint: str,
    isaac_build: str,
    environment: Dict[str, str],
    seeds: Sequence[int] = DEFAULT_SEEDS,
    scenario: str = "franka-joint-tracking",
) -> Dict[str, Any]:
    """Assemble the frozen manifest. Every value here is a preregistered choice.

    ``environment`` carries the interpreter/library versions from
    :func:`gauntlet.evidence.environment_versions` plus the runtime identity
    strings observed on the simulation host.
    """
    seeds = [int(s) for s in seeds]
    plan = execution_plan(seeds)

    manifest: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": CAMPAIGN_ID,
        "campaign_version": CAMPAIGN_VERSION,
        "scenario": scenario,
        "provenance": {
            "repo_commit": repo_commit,
            "runtime_validation_parent_commit": runtime_parent_commit,
            # The scene's identity is its GRAPH, not its bytes: USD crate
            # re-saves are not byte-reproducible, so a .usd file hash would
            # churn without the experiment changing at all.
            "scene_graph_fingerprint": scene_graph_fingerprint,
            "scene_file": "scenes/franka_ros2_bridge_scene.usd",
        },
        "runtime": {
            "isaac_build": isaac_build,
            "ros_distro": "jazzy",
            "ros_library_source": "isaac-internal (exts/isaacsim.ros2.core/jazzy/lib)",
            "rmw_implementation": "rmw_fastrtps_cpp",
            "rclpy_source": "omniverse-built",
            "platform": "aarch64",
            "gpu_class": "NVIDIA GB10 (DGX Spark class)",
            "environment": dict(sorted(environment.items())),
        },
        "sampling": {
            # Preserved from the committed runtime measurement — NOT re-chosen.
            "sample_rate_hz": 200.0,
            "physics_dt_s": 1.0 / 400.0,
            "rendering_dt_s": 1.0 / 400.0,
            "graph_tick_per_physics_steps": 2,
            "nyquist_hz": 100.0,
            "rate_tolerance_frac": 0.02,
            "rate_evidence": "per-run inter-sample simulated-time deltas",
        },
        "disturbance": {
            "model": "control_loop.logic.noise_model.JointStateNoiseModel",
            "injection_point": "joint-state feedback path, pre-filter",
            "vibration_amplitude_rad": 0.3,
            "vibration_freq_hz": 25.0,
            "vibration_phase_rad": 0.0,
            "awgn_sigma_rad": 0.1,
            "rng": "numpy.random.default_rng(seed)",
        },
        "filter": {
            "implementation": "control_loop.logic.filter_stage.FilterStage",
            "path": "causal only (s2r_dsp.apply_filter_realtime); "
                    "the zero-phase offline path is never in the loop",
            "filtered_kind": "iir",
            "filtered_order": 4,
            "cutoff_hz": 5.0,
            "unfiltered_kind": "passthrough",
            "unfiltered_response": "identity b=[1], a=[1] (flat 0 dB)",
            "sample_rate_hz": 200.0,
        },
        "controller": {
            "implementation": "control_loop.logic.waypoint_tracker.WaypointTracker",
            "kp": 0.8,
            "max_step_rad": 0.05,
            "tolerance_rad": 0.02,
            "waypoint_timeout_s": 10.0,
            "joint_limits": "control_loop.logic.franka_limits.limits_for(ARM_JOINT_NAMES)",
            "waypoints_flat": [
                0.2, -0.6, 0.0, -2.2, 0.0, 1.8, 0.6,
                -0.2, -0.4, 0.2, -2.0, 0.2, 1.6, 0.9,
            ],
            "joint_names": [f"panda_joint{i}" for i in range(1, 8)],
        },
        "run_contract": {
            "start_pose_rad": list(START_POSE_RAD),
            "reset_tolerance_rad": 0.02,
            "reset_max_steps": 6000,
            # Every run is the SAME length regardless of when (or whether) the
            # tracker converges. A run that stopped at DONE would give the
            # filtered arm shorter records than the unfiltered arm and make the
            # spectra incomparable, which would silently bias the attenuation
            # metric toward the condition that converges.
            "samples_per_run": 2000,
            "run_duration_sim_s": 10.0,
            "step_cap_per_run": 20000,
            "representative_joint": REPRESENTATIVE_JOINT,
            # EXOGENOUS by construction. The reference must not depend on the
            # treatment: scoring each arm against the waypoint its own
            # controller happens to have reached means the two arms are graded
            # against different signals, and an arm that never advances presents
            # a zero-span reference — which silently changes the denominator of
            # overshoot_pct. Observed in the pilot; removed before freezing.
            "reference_signal": (
                "exogenous, time-parameterized: waypoint k is the reference "
                "for elapsed simulated time in [k*T/K, (k+1)*T/K), with "
                "T=run_duration_sim_s and K=len(waypoints). Identical in both "
                "arms and for every seed; independent of controller progress."
            ),
            "reference_segment_s": 5.0,
            "reset_between_runs": [
                "articulation commanded back to start_pose_rad and verified "
                "within reset_tolerance_rad before the run begins",
                "WaypointTracker reconstructed per run",
                "FilterStage reconstructed per run (zero delay-line state)",
                "JointStateNoiseModel reconstructed per run from the run seed",
                "joint-state sample buffer cleared per run",
                "telemetry accumulators reconstructed per run",
            ],
        },
        "design": {
            "conditions": ["filtered", "unfiltered"],
            "seeds": seeds,
            "runs_per_condition": len(seeds),
            "scheduled_runs": len(plan),
            "pairing": "same seed in both conditions -> identical disturbance "
                       "realization -> paired differences are meaningful",
            "arm_order_policy": "even seed: filtered first; odd seed: "
                                "unfiltered first (balanced, frozen pre-run)",
            "execution_plan": plan,
            "no_replacement_rule": "a failed or invalid run stays in the "
                                   "denominator; it is never replaced by "
                                   "another seed and never silently dropped",
            "exclusion_rules": [
                "reset_failed: start pose not reached within reset_max_steps",
                "rate_out_of_tolerance: measured per-run sample rate differs "
                "from 200.0 Hz by more than rate_tolerance_frac",
                "insufficient_samples: fewer than samples_per_run rows "
                "collected before step_cap_per_run",
                "harness_error: an exception during the run",
            ],
            "excluded_runs_are_reported": True,
        },
        "evidence": {
            "gauntlet_run_log": "logs/<run_id>/{run_meta.json,telemetry.csv}",
            "telemetry_columns": ["t", "reference", "measured", "noisy"],
            "raw_packet": "logs/<run_id>/raw_evidence.json",
            "graded_packet": "evidence/run-<run_id>.json",
            "integrity": "sha256 per file, recorded in raw_evidence.json and "
                         "in the campaign integrity index",
            "immutability": "committed packets are records, never edited; "
                            "a correction is a new run id (AGENTS.md §2)",
        },
        "analysis": {
            "primary_metric": "tracking_rms_error",
            "metrics": [
                "tracking_rms_error",
                "settling_time_s",
                "overshoot_pct",
                "filter_attenuation_db",
            ],
            "secondary_diagnostics": [
                "peak_tracking_error_rad",
                "true_tracking_rms_error_rad",
                "limit_clamp_cycles",
                "measured_sample_rate_hz",
                "controller_cycles",
                "tracker_status",
                "waypoints_reached",
            ],
            "paired_analysis": "per-seed filtered-minus-unfiltered differences",
            "uncertainty": "deterministic BCa-free percentile bootstrap, "
                           "10000 resamples, seeded with bootstrap_seed",
            "bootstrap_seed": 20260814,
            "bootstrap_resamples": 10000,
            "significance_policy": "no null-hypothesis significance claim is "
                                   "made from n=20; intervals and raw "
                                   "distributions are reported instead",
        },
        "non_claims": [
            "simulation only; no physical hardware was involved",
            "one Franka joint-space scenario; no generalization is claimed",
            "no sim-to-real transfer is demonstrated or claimed",
            "no robot safety claim",
            "no certification or compliance claim",
            "no production-readiness claim",
        ],
    }
    manifest["manifest_sha256"] = manifest_hash(manifest)
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Structural + self-consistency validation. Raises :class:`CampaignError`."""
    if not isinstance(manifest, dict):
        raise CampaignError(
            f"manifest must be an object, got {type(manifest).__name__}"
        )
    missing = [k for k in _REQUIRED_TOP_LEVEL if k not in manifest]
    if missing:
        raise CampaignError(f"manifest missing required fields: {missing}")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise CampaignError(
            f"unsupported manifest schema_version {manifest['schema_version']!r} "
            f"(expected {SCHEMA_VERSION})"
        )

    design = manifest["design"]
    seeds = design["seeds"]
    if len(set(seeds)) != len(seeds):
        raise CampaignError("manifest seed list contains duplicates")
    expected_plan = execution_plan(seeds)
    if design["execution_plan"] != expected_plan:
        raise CampaignError(
            "manifest execution_plan does not match the deterministic plan "
            "derived from its own seed list and arm-order policy"
        )
    if design["scheduled_runs"] != len(expected_plan):
        raise CampaignError(
            f"scheduled_runs={design['scheduled_runs']} disagrees with the "
            f"{len(expected_plan)}-run execution plan"
        )

    # The sampling contract must be internally consistent, and consistent with
    # the guard the runtime slice committed. A manifest that freezes a config
    # the guard would reject must never be runnable.
    sampling = manifest["sampling"]
    fs = float(sampling["sample_rate_hz"])
    vib = float(manifest["disturbance"]["vibration_freq_hz"])
    cut = float(manifest["filter"]["cutoff_hz"])
    if not 0.0 < cut < vib < 0.5 * fs:
        raise CampaignError(
            f"manifest sampling contract is incoherent: need "
            f"0 < cutoff({cut}) < vibration({vib}) < Nyquist({0.5 * fs})"
        )
    if float(manifest["filter"]["sample_rate_hz"]) != fs:
        raise CampaignError("filter sample_rate_hz disagrees with sampling block")

    # The run length must be exactly the sample count the rate implies, and the
    # reference schedule must tile it evenly. A mismatch here would mean the
    # committed reference signal is not the one the driver actually emits.
    rc = manifest["run_contract"]
    ctrl = manifest["controller"]
    n_joints = len(ctrl["joint_names"])
    n_waypoints, remainder = divmod(len(ctrl["waypoints_flat"]), n_joints)
    if remainder or n_waypoints < 1:
        raise CampaignError(
            f"waypoints_flat length {len(ctrl['waypoints_flat'])} is not a "
            f"positive multiple of {n_joints} joints"
        )
    if int(rc["samples_per_run"]) != round(float(rc["run_duration_sim_s"]) * fs):
        raise CampaignError(
            f"samples_per_run={rc['samples_per_run']} disagrees with "
            f"{rc['run_duration_sim_s']} s at {fs} Hz"
        )
    if float(rc["reference_segment_s"]) != float(rc["run_duration_sim_s"]) / n_waypoints:
        raise CampaignError(
            f"reference_segment_s={rc['reference_segment_s']} does not tile "
            f"{rc['run_duration_sim_s']} s across {n_waypoints} waypoints"
        )

    if "manifest_sha256" in manifest:
        expected = manifest_hash(manifest)
        if manifest["manifest_sha256"] != expected:
            raise CampaignError(
                "manifest_sha256 does not match the manifest body "
                f"(stored={manifest['manifest_sha256']}, computed={expected}) — "
                "the frozen design was edited after it was hashed"
            )
    return manifest


def dumps_manifest(manifest: Dict[str, Any]) -> str:
    """Deterministic serialization of a validated manifest."""
    validate_manifest(manifest)
    return canonical_json(manifest)


def load_manifest(path) -> Dict[str, Any]:
    """Load and validate a manifest file; raises on any defect."""
    path = Path(path)
    if not path.is_file():
        raise CampaignError(f"campaign manifest not found: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise CampaignError(f"corrupt campaign manifest {path}: {e}") from e
    return validate_manifest(manifest)


def write_manifest(manifest: Dict[str, Any], path) -> Path:
    """Write a validated manifest; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_manifest(manifest), encoding="utf-8")
    return path


def file_sha256(path) -> str:
    """sha256 of a file's bytes (evidence integrity)."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sampling_rate_valid(
    measured_hz: Optional[float],
    target_hz: float = 200.0,
    tolerance: float = 0.02,
) -> bool:
    """True when a run's measured sample rate is inside the frozen tolerance."""
    if measured_hz is None or measured_hz <= 0.0:
        return False
    return abs(measured_hz - target_hz) / target_hz <= tolerance
