# AGENTS.md — Operating Guide (any agent, any model)

Applies to every coding agent working this repo — Google Antigravity, Claude, local
models on the MSI EdgeXpert, or humans. No tool-specific features are assumed.
Read [MASTER_PLAN.md](MASTER_PLAN.md) first: intent, architecture, REQ IDs,
milestones, and the binding Franka joint-space scenario decision.

## 1. The Loop

Every unit of work follows **INTENT → BUILD → EVAL → VERIFY → DOCUMENT → SHIP**:

1. **INTENT** — name the milestone lane and REQ ID(s). No REQ covers it? STOP and
   propose the REQ in a docs-only PR first. No untraced work.
2. **BUILD** — smallest shippable slice on a lane branch. Respect the environment
   split: code that needs live Isaac Sim runs only on the EdgeXpert; everything else
   must be buildable and testable anywhere.
3. **EVAL** — run the gates locally: `pytest dsp/` (and `pytest gauntlet/`,
   `colcon build && colcon test` in `ros2-ws/` once they exist). Sim-dependent
   changes: run the launch walkthrough on the EdgeXpert before calling it done.
4. **VERIFY** — adversarial pass, ideally a different agent than the builder: wrong
   seeds, degenerate trajectories, NaN/dropout in sensor streams, filter fed
   out-of-band noise, evidence packets with missing fields. Record what you tried
   in the PR.
5. **DOCUMENT** — same PR updates README/launch docs/this file. Doc drift is a defect.
6. **SHIP** — PR to `main` with the §5 checklist. CI green is a hard gate.

## 2. Ground rules

- Determinism is the product: every stochastic element (noise, campaigns) is seeded
  and reproducible; evidence packets embed the seed and versions.
- The causal filter path (`apply_filter_realtime`) is the only one allowed in-loop;
  zero-phase filtering is for offline analysis only.
- Pin versions — never "latest". Two pins coexist and must not be conflated:
  - **Empirical runtime — governs all M4 evidence.** Isaac Sim
    `6.0.1-rc.7+release.42383.32955d8d.gl`, with the ROS 2 Jazzy environment
    supplied by Isaac itself (no system ROS 2 on the campaign host). Every
    campaign run and every published number came from this build. It is a
    *release candidate*; Isaac Sim 6.0.1 GA is a distinct, later release that
    this project has not evaluated and claims no equivalence to.
  - **Legacy DevContainer / `scripts/` path.** ROS 2 Humble, Isaac Sim 4.5.0.
    Still valid for building `ros2-ws/` and the standalone Isaac runner scripts
    under `scripts/`. **No empirical result in this repository was produced on
    it.**
- Isaac Sim never becomes a CI dependency.
- Committed evidence packets are immutable records — regenerate under a new run id,
  never edit.

## 3. Parallel lanes (sub-agents)

| Lane | Owns | Must not touch |
|------|------|----------------|
| dsp | `dsp/` | `ros2-ws/`, `scripts/` |
| ros-nodes | `ros2-ws/src/control_loop/` | `dsp/` internals (import only), `scenes/` |
| sim | `scripts/`, `scenes/` | node logic |
| gauntlet | `gauntlet/`, `evidence/` | node logic (consumes logs only) |
| docs/ci | `*.md`, `.github/` | code logic |

Rules: one branch per lane (`feat/m2-ros-nodes-noise-injector`, …); integration
steps (live-sim runs) are sequential on the EdgeXpert and happen AFTER the lanes
they depend on merge; rebase on `main` before review; two lanes needing the same
file = one lane.

## 4. Git / PR / SDLC

- Branch from `main`; names `feat/<milestone>-<lane>-<slug>`, `fix/<slug>`,
  `docs/<slug>`.
- Commits: imperative subject ≤ 72 chars; body explains *why*; reference REQ IDs.
- PR template: **Intent** (milestone/lane/REQ IDs) · **What changed** ·
  **Eval evidence** (test output; for sim work, the run id + evidence packet) ·
  **Verify evidence** (adversarial pass notes) · **Docs touched**.
- CI must be green once M3-B lands it; add gates in the same PR as the feature they
  gate. No force-push to `main`; PRs reviewable in 10 minutes.

## 5. Definition of done (per PR)

- [ ] Traces to REQ ID(s); milestone named
- [ ] Gates pass locally; CI green (post-M3)
- [ ] Sim-dependent work demonstrated on the EdgeXpert (run id cited)
- [ ] Adversarial verify pass recorded
- [ ] Docs updated in the same PR
- [ ] A stranger could resume the repo with no hidden context
