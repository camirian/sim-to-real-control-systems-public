# M4 baseline, defects, and the campaign blocker

What was actually true before this branch, what changed, and what is still
blocked — recorded so a reviewer can tell verified work from authored work
without taking anyone's word for it.

Baseline commit: `a69189e`. All commands below were run from a clean worktree
of that commit unless stated otherwise.

## 1. Environment — established, not assumed

Two machines were probed. Neither can run the M4 campaign.

| Capability | Workstation | Sim-box candidate |
|---|---|---|
| Architecture | x86_64 | aarch64 |
| GPU | NVIDIA RTX (Turing, 8 GB) | integrated (DGX-class ARM node) |
| **Isaac Sim 4.5.0** | **absent** | **absent** |
| ROS 2 | Jazzy — repo pins **Humble** | none installed |
| `colcon` | not installed | not installed |
| Python | 3.12 — CI pins 3.10 | — |

How this was established (not inferred from docs):

```bash
ls /opt/ros                 # workstation: jazzy        sim-box: no such directory
find / -maxdepth 4 -iname "*isaac*sim*"    # no hits on either machine
find / -maxdepth 5 -name "python.sh"       # no Isaac Sim python entry point
docker images               # no Isaac container on either machine
uname -m                    # x86_64 / aarch64
```

**Consequence:** every `EDGEXPERT-VERIFY` item in
[RUN_ON_EDGEXPERT.md](RUN_ON_EDGEXPERT.md) §7 remains unverified, and the
20+20 seeded campaign has not been executed. This is a `RUNTIME_BLOCKER`. It
has **not** been worked around, simulated, approximated, or substituted with a
plain-Python plant model — an environment failure must not become an
experiment result.

### 1a. The blocker is the version pin, not the hardware

An earlier draft of this document claimed the ARM node "is not a candidate host
regardless of installation effort." **That was wrong**, and the correction
matters enough to state plainly rather than quietly edit.

Isaac Sim 4.5.0 ships no aarch64 build — that part is true
([4.5.0 requirements](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/requirements.html)
lists only Ubuntu 20.04/22.04 and Windows). But aarch64 support arrived in
**5.1.0**, and 6.0.x added full container and livestreaming support. NVIDIA
supports exactly one aarch64 platform:

> "aarch64: NVIDIA DGX Spark with DGX OS 7 only"
> — [Isaac Sim 6.0 requirements](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/installation/requirements.html)

The ARM node **is** a DGX Spark running DGX OS 7.5.0 (Ubuntu 24.04, GB10,
driver 580.173.02, Docker 29.2.1, 3.3 TB free). It meets that requirement.

Meanwhile the x86 workstation fails on two independent counts: its RTX 2070
Super (Turing, 8 GB) is below the stated minimum for *both* versions (4.5.0
asks RTX 3070/8 GB, 6.0 asks RTX 4080/16 GB), and its ROS 2 Jazzy install is
incompatible with the Humble-only 4.5.0 pin.

So the honest statement of the blocker is: **the campaign is blocked by the
4.5.0 pin, on hardware that could run a newer Isaac Sim.** Unpinning is a
documented decision, not a workaround — see §7.

## 2. Test baseline at `a69189e` — green before any edit

```bash
pip install -e "dsp/[test]"
python -m pytest dsp/ gauntlet/ campaign/ -q            # 118 passed
PYTHONPATH=ros2-ws/src/control_loop \
  python -m pytest ros2-ws/src/control_loop/test -q     # 47 passed
python -m py_compile ros2-ws/src/control_loop/control_loop/*_node.py \
  ros2-ws/src/control_loop/launch/*.launch.py \
  ros2-ws/src/control_loop/setup.py campaign/run_campaign.py   # OK
```

The aggregation smoke test (synthetic packets → `results_table.md`) also passed
at baseline, exit 0. Nothing was broken going in; the defects below were
latent, not failing.

`colcon build` was **not** run: `colcon` is not installed and the workspace
pins ROS 2 Humble while the only available distro is Jazzy. Installing a
second ROS distro to satisfy a build check was out of scope. This is a
`RUNTIME_BLOCKER` for the "ROS 2 build" verification item, distinct from the
Isaac one. The nodes are covered by the `py_compile` gate and by 65 pure-logic
tests that run without `rclpy`.

## 3. Defects found and classified

| # | Defect | Class | Status |
|---|---|---|---|
| D1 | Scene has no `/joint_command` subscriber or articulation controller — the loop was open | `CONFIG_DEFECT` | **fixed** |
| D2 | `filter_kind:=passthrough` emitted by the campaign is rejected by the filter node | `CODE_DEFECT` | **fixed** |
| D3 | Publisher `inputs:topicName` unauthored — `/joint_states` came from a node default | `CONFIG_DEFECT` | **fixed** |
| D4 | Publisher `inputs:timeStamp` had no simulation-time source | `CONFIG_DEFECT` | **fixed** |
| D5 | No joint-limit bound on commanded positions | `CODE_DEFECT` | **fixed** |
| D6 | Filter `sample_rate_hz` default (200 Hz) vs. the scene's tick rate | `UNKNOWN` | **open — see §5** |

### D1 — the loop was open (the M4 blocker)

`README.md` and `RUN_ON_EDGEXPERT.md` §3 both stated this. It was verified
rather than trusted, by dumping the committed USD: `/World/ActionGraph`
contained exactly two nodes, `on_playback_tick`
(`omni.graph.action.OnPlaybackTick`) and `ros2_publish_joint_state`
(`isaacsim.ros2.bridge.ROS2PublishJointState`, `inputs:targetPrim` → `/Franka`).
No subscriber, no articulation controller. `waypoint_controller` published
`/joint_command` into nothing.

Fixed by `scripts/author_joint_command_graph.py`, which authors the subscriber,
an articulation controller, and a simulation-time source as **data** via
`usd-core` — no Isaac Sim, no GUI step, and reviewable as a script rather than
an opaque binary re-save.

### D2 — the unfiltered arm of the campaign could not start

`campaign/run_campaign.py:98` emits `filter_kind:=passthrough` for every
unfiltered run (there is a test asserting exactly that string). But
`FilterSpec._VALID_KINDS` was `("fir", "iir")` and `validate()` raised
`ValueError` on that token. All 20 unfiltered runs would have died at node
startup — half the money table was unreachable. Found by reading both sides of
the boundary, not by running the campaign.

### D4 — no simulation clock into the published timestamp

The committed publisher had `inputs:timeStamp` unauthored (verified:
`HasAuthoredValue() == False`), and the graph had no `ReadSimulationTime` node.
The Isaac 4.5.0 OGN reference documents the attribute's default as `0.0`, and
the official manipulation tutorial always wires `ReadSimTime` into it.

**Careful about the consequence.** `waypoint_controller_node.py:107` derives
its clock from `msg.header.stamp`, and the tracker's timeout logic is driven by
that clock. *If* an unwired publisher stamps every message `0.0`, elapsed time
is always zero and `waypoint_timeout_s` can never fire. The OGN docs do not
state what the outgoing `header.stamp` contains when nothing is wired, so that
consequence is **inference, not established fact**. The wiring was added
because it matches the canonical tutorial; the timeout claim stays unproven
until someone runs `ros2 topic echo /joint_states --field header.stamp` on a
sim box and records the reading.

## 4. What is now protected

`scenes/scene_contract.py` + `scenes/test/` (new CI job) statically verify the
scene's ROS 2 graph: node types and versions, topic names, the `/Franka`
binding, and every connection the loop depends on. It reads the `.usd` as an
`Sdf` layer instead of composing a `Usd` stage, so it needs **no network and no
Isaac** — a fresh clone can validate the scene offline.

Run against the pre-fix scene it reports exactly the five violations this
branch fixes:

```
pre-fix  graph fingerprint b637c66b…  -> 5 violations
post-fix graph fingerprint a4df3496…  -> 0 violations
```

The check also pins the scene's topic names against the ROS node parameter
defaults, parsed statically with `ast` (the node modules import `rclpy`, which
CI does not have), so the two halves of the bridge cannot drift apart.

Note on hashes: re-saving a USD crate layer is **not** byte-reproducible — the
same graph authored twice yields different file hashes. Run manifests should
therefore cite `scene_contract.graph_fingerprint()`, a hash over the normalized
graph structure, rather than the `.usd` file hash.

Scope limit, stated plainly: this verifies the **scene-side** contract. That
the ROS 2 bridge extension loads, that Isaac instantiates these nodes, that the
arm moves, and that `/joint_command` is received at all are runtime facts this
check cannot reach. They stay `EDGEXPERT-VERIFY`.

## 5. D6 — the open question, deliberately not "fixed"

The scene's publisher is driven by `OnPlaybackTick`, i.e. once per app frame,
and the stage authors `timeCodesPerSecond = 60`. The filter node defaults to
`sample_rate_hz = 200.0` (`dsp_filter_node.py`, `closed_loop.launch.py`), and
the launch injects vibration at 25 Hz.

If `/joint_states` actually publishes at 60 Hz, then: the filter designs its
cutoff against the wrong Nyquist (a 5 Hz cutoff specified at 200 Hz is a ~1.5 Hz
cutoff applied to a 60 Hz stream), and the 25 Hz vibration sits at 0.83 of a
30 Hz Nyquist — representable, but a poor place to measure attenuation.

This was **not** silently "corrected", because the real publish rate cannot be
measured without a running sim, and changing a filter parameter to match a rate
nobody has observed would be inventing the answer. The resolution is one
command on a sim box:

```bash
ros2 topic hz /joint_states     # record the observed rate
```

Then set `sample_rate_hz` to the measured value and re-derive the filter spec.
Until then D6 is `UNKNOWN` and the campaign should not be run — a rate mismatch
would bias every filtered run in the same direction, which is exactly the kind
of systematic error a paired comparison cannot detect.

## 6. Campaign status

**Not run.** Not started, not partially run, no runs excluded, no evidence
packets generated. The `evidence/` directory contains no real runs, and
`campaign/example/` remains what it always was: a synthetic rendering carrying
the `-synthetic` scenario suffix.

Blocking items, in order:

1. `RUNTIME_BLOCKER` — no Isaac Sim 4.5.0 host is available (§1).
2. `RUNTIME_BLOCKER` — no ROS 2 Humble environment; `colcon build` unverified.
3. `UNKNOWN` — D6 sample-rate question must be settled on a live topic (§5).
4. `EDGEXPERT-VERIFY` — the scene-side fix in this branch has not been loaded
   by Isaac. The static contract passing is necessary, not sufficient.

The run manifest, exclusion rules, `RESULTS.md`, uncertainty summaries, and the
demo outline are deliberately **not** written yet. Authoring them now would
produce a document describing runs that do not exist, and a preregistration
written after the fact is not a preregistration.

## 7. The unpin decision (proposed, not taken)

AGENTS.md §2 pins Isaac Sim 4.5.0 and forbids "latest"; the M4 issue allows
changing a pinned version only when "a concrete blocker requires a documented
decision." §1a is that concrete blocker. This section is the documented
decision, offered for owner review — **nothing here has been executed.**

**Proposal:** retire the 4.5.0 pin in favour of **Isaac Sim 6.0.1** on the DGX
Spark, via the multi-arch container (`nvcr.io/nvidia/isaac-sim:6.0.1`, ~9.96 GB
compressed, run with `--aarch64`).

Why 6.0.1 and not 5.1.0, the first aarch64 release: 5.1.0 lacks full DGX Spark
container and livestreaming support, both added in 6.0. Stopping at 5.1.0 buys
one migration and then needs another.

**Migration cost is smaller than it looks.** All four OmniGraph node type
tokens this repo authors survive verbatim into 6.0.1 — the *extension* that
provides them was renamed (`isaacsim.ros2.bridge` → `isaacsim.ros2.nodes`) but
the `node:type` strings are unchanged, confirmed against the 6.0.1 OGN
reference and the 6.0.1 Franka manipulation tutorial. Concretely:

1. Enable `isaacsim.ros2.nodes` rather than `isaacsim.ros2.bridge`
   (`scripts/run_franka_headless.py` extension id).
2. Insert an **Isaac Read Joint State** node upstream of the joint-state
   publisher: in 6.0 the ROS 2 publishers no longer resolve USD prims
   internally, so `inputs:targetPrim` on the publisher is deprecated in favour
   of wired `jointNames`/`jointPositions`/… inputs
   ([6.0 OmniGraph migration guide](https://docs.isaacsim.omniverse.nvidia.com/6.0.1/migration_guides/isaac_sim_6_0/ros2_omnigraph_migration.html)).
   `scenes/scene_contract.py` encodes the 4.5.0 shape and would need updating
   in the same change — which is the check doing its job.
3. ROS 2: 6.0.1 supports **both Humble and Jazzy**, so this also removes the
   Humble-only constraint.

**Known risks, not hidden.** GB10 has open NVIDIA forum reports on this exact
stack: PhysX GPU not working under 5.1.0, and a 6.0.1 GPU crash reported
2026-07-24 against driver 595.71.05. This box is on 580.173.02, so it is not
the reported-crashing driver, but the minimum driver for 6.0.1 has not been
verified here. Isaac Lab on this platform additionally wants CUDA ≥ 13.

**Recommended first step is a throwaway, not a port:** pull the container and
run a stock Franka sample on the DGX Spark. If that smoke test fails, the
pin question is moot and nothing in this repo was touched. Only after it
passes is it worth migrating repo code, re-authoring the scene for 6.0, and
settling D6 with a real `ros2 topic hz` reading.
