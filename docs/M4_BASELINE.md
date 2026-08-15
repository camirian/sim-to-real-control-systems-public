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

Isaac Sim 4.5.0 ships no aarch64 desktop build, so the ARM node is not a
candidate host regardless of installation effort.

**Consequence:** every `EDGEXPERT-VERIFY` item in
[RUN_ON_EDGEXPERT.md](RUN_ON_EDGEXPERT.md) §7 remains unverified, and the
20+20 seeded campaign cannot be executed. This is a `RUNTIME_BLOCKER`. It has
**not** been worked around, simulated, approximated, or substituted with a
plain-Python plant model — an environment failure must not become an
experiment result.

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
