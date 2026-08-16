# Reproducing and verifying the M4 campaign

There are two different things a reader might want to do, and they have very
different requirements. Keeping them apart is deliberate.

| | Needs | Time |
|---|---|---|
| **A. Verify the committed evidence** | a clone and Python. No GPU, no ROS, no Isaac at all. | seconds |
| **B. Re-run the campaign** | an Isaac Sim 6.x host with a GPU; for the *validated* configuration specifically, `6.0.1-rc.7+release.42383.32955d8d.gl` | ~45 min |

Most review is **A**. The claim "these numbers came from this evidence" should
be checkable without the machine that produced it, and it is.

> **Which build the original campaign ran on, and what that means for you.**
> Every run in the committed evidence was executed on Isaac Sim
> **`6.0.1-rc.7+release.42383.32955d8d.gl`** — a *release candidate*. To
> reproduce the exact validated configuration, that is the build to install.
>
> NVIDIA's Isaac Sim **6.0.1 GA is a distinct, later release**, and this project
> has **not** shown it equivalent to the RC. Running this harness on GA is a
> **new runtime-compatibility and reproduction attempt** — a fresh experiment
> whose outcome is unknown. It is *not* evidence that the original campaign ran
> on GA, and nothing here asserts GA would produce the same behaviour.
>
> Path **A** is unaffected by any of this: verifying the committed evidence
> requires no Isaac Sim of any version.

---

## A. Verify the committed evidence (offline)

```bash
git clone <this repo> && cd sim-to-real-control-systems-public
python -m venv .venv && . .venv/bin/activate
pip install -e dsp/ && pip install numpy scipy pytest usd-core
```

### A1. Run every test

```bash
python -m pytest dsp/ gauntlet/ campaign/ -q
python -m pytest scenes/ -q
PYTHONPATH=ros2-ws/src/control_loop python -m pytest ros2-ws/src/control_loop/test -q
```

`campaign/test/test_committed_campaign.py` is the one that checks the campaign
itself. It re-hashes every evidence file against the digest recorded in that
run's own packet, re-derives the execution plan from the frozen manifest, and
asserts that every scheduled run is present, cites the frozen manifest hash,
started from the declared pose, and held the rate contract. A run that was
deleted, edited, or produced against a different manifest fails it.

### A2. Regenerate the results document

```bash
python scripts/build_results.py --check \
    --logs-root campaign/results/m4-franka-filtered-vs-unfiltered-v1 \
    --manifest campaign/manifests/m4-franka-filtered-vs-unfiltered-v1.json \
    --out RESULTS.md

git status --porcelain   # must be empty
```

Expected:

```
valid 40/40  integrity_passed=True
read-only check: 42/42 artifacts reproduced byte-for-byte
CHECK PASSED — nothing in the repository was modified.
```

This re-grades every run from its raw telemetry through the same gauntlet checks
the certification path uses, recomputes the paired differences and bootstrap
intervals, and rebuilds all 42 derived artifacts — the 40 gauntlet packets under
`evidence/`, `campaign_results.json`, and `RESULTS.md`.

**`--check` writes everything to a temporary directory** and compares
byte-for-byte, so verifying the records cannot modify them. It exits non-zero on
any mismatch, which is exactly the failure this is designed to surface: no number
in `RESULTS.md` is hand-entered, so a mismatch means the document and the
evidence disagree.

> Omit `--check` only when you intend to *regenerate* the committed artifacts
> after a fresh campaign. In that mode the script writes in place, and
> `--timestamp` must be supplied — leaving it out records `generated_at: null`
> in all 40 packets.

### A3. Confirm the design was frozen before the runs

```bash
git log --oneline --follow campaign/manifests/
git log --oneline campaign/results/
```

The manifest commit precedes every evidence commit. The manifest carries a
sha256 over its own body; `campaign.manifest.validate_manifest` recomputes it, so
editing any frozen value after the fact fails validation rather than passing
quietly.

---

## B. Re-run the campaign (needs an Isaac Sim host)

### B0. Prerequisites

- Isaac Sim installed to a user-writable directory. For the **exact validated
  configuration**, that means the tested build
  **`6.0.1-rc.7+release.42383.32955d8d.gl`** — the release candidate every
  committed run was executed on. Any other build, **including 6.0.1 GA**, makes
  this a new runtime-compatibility attempt rather than a replay of the recorded
  campaign; this project has not established that GA behaves identically. No
  `sudo`, no `apt`, no Docker group membership, and no system ROS 2 installation
  are required or used — the ROS 2 Jazzy libraries come from inside Isaac.
- A CUDA-capable NVIDIA GPU. The reference runs used an NVIDIA GB10 (DGX Spark
  class), aarch64.

### B1. Source the internal ROS 2 environment — not optional

```bash
source <isaac-root>/setup_ros_env.sh
```

Skip this and `rclpy` will not import: the internal libraries fail with
`libament_index_cpp.so: cannot open shared object file`. This is the single most
common way to lose an hour here.

### B2. Validate the runtime before trusting it

```bash
cd <isaac-root>
./python.sh <repo>/scripts/validate_isaac6_runtime.py \
    --scene <repo>/scenes/franka_ros2_bridge_scene.usd \
    --repo <repo> --target-hz 200
```

Expect `M4_RUNTIME_GATE_PASS` and a measured `/joint_states` rate within 2% of
200 Hz. `--target-hz` means the desired *publication* rate; the script sets
`dt = 1/(2*target)` because the OmniGraph publisher ticks once every **two**
physics steps. That factor of 2 was measured, not derived — see
`docs/M4_RUNTIME_VALIDATION.md`.

If the rate comes back near 30 Hz you are running the scene's default graph.
**Do not proceed.** At 30 Hz the 25 Hz disturbance is above Nyquist and aliases
onto the 5 Hz cutoff, and the campaign would compare an artifact.

### B3. Run the campaign

```bash
cd <isaac-root>
./python.sh <repo>/scripts/run_campaign_isaac.py \
    --scene <repo>/scenes/franka_ros2_bridge_scene.usd \
    --repo <repo> \
    --manifest <repo>/campaign/manifests/m4-franka-filtered-vs-unfiltered-v1.json \
    --logs-root <out>
```

The driver refuses to start if preflight measures a rate outside the frozen
tolerance, and marks any individual run invalid — with its exact reason — if
that run's own rate, sample count, or reset check fails. Failed runs stay in the
denominator; they are never replaced.

To smoke-test the harness without touching campaign seeds:

```bash
./python.sh <repo>/scripts/run_campaign_isaac.py ... --pilot-seed 9001
```

Pilot seeds must not be campaign seeds (the driver enforces this), and pilot
output is written to a separate tree. **Pilot runs are not campaign evidence.**

### B4. Build the results

Same as **A2**, pointing `--logs-root` at your output directory.

---

## What will and will not reproduce exactly

**Bit-identical:** the frozen manifest and its hash; the seed schedule and
execution order; every derived artifact in step A (grading, aggregation,
bootstrap intervals) given the same evidence files.

**Not bit-identical:** a fresh campaign's telemetry. The disturbance is seeded
and deterministic, but PhysX stepping and the ROS transport are not
bit-reproducible across runs or hosts, so per-run metrics will differ slightly.
The comparison is designed to survive that — which is what the paired seeds and
the reported intervals are for.

**Deliberately not reproducible from the `.usd` bytes:** the scene is identified
by `scenes.scene_contract.graph_fingerprint` (a hash over its graph structure),
not a file hash. USD crate re-saves are not byte-stable, so a file hash would
churn without the experiment changing.

---

## Non-claims

Reproducing any of the above demonstrates that this simulated experiment is
internally consistent and that its evidence is intact. It does **not**
demonstrate real-world transfer, hardware behavior, robot safety, certification
or compliance, or production readiness. No physical robot was involved at any
point.
