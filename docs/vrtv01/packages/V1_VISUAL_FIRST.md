# Package V1 — VISUAL FIRST

Read `00_COMMON.md` for binding rules, SHAs, and schemas. Run in a fresh session.

## Allowed inputs

**Stage 1 — images only:**
```
docs/vrtv01/views/view_a_system_topology.png
docs/vrtv01/views/view_b_evidence_provenance.png
docs/vrtv01/views/view_c_controls_and_history.png
docs/vrtv01/views/view_d_claim_boundary.png
```
Plus the legend below. **Verify each PNG's sha256 against `docs/vrtv01/VIEW_HASHES.txt` before supplying it.**

### Two distinct runs

| Run | Images supplied |
|---|---|
| `V1-CLEAN` | the four clean PNGs above — **primary comparison** |
| `V1-SEEDED` | `docs/vrtv01/seeded/view_a_system_topology_seeded.png`, `docs/vrtv01/seeded/view_b_evidence_provenance_seeded.png`, plus **clean** C and D — **robustness control only** |

Verify seeded PNGs against `docs/vrtv01/SEEDED_HASHES.txt`. The reviewer is never told that seeding exists, that two runs exist, or which packet it received.

`V1-SEEDED` output is scored for seeded-defect detection only and must not be pooled into the primary representation comparison.

Both runs use the same provider, model/version and configuration as V0-CLEAN and V2 — see the binding model-control rule in `docs/vrtv01/EXECUTION_CONTROL.md`.

**Stage 2 — the frozen source set.**

## Forbidden information
- **Mermaid source text, in any form.** V1 receives rendered images only. Supplying `.mmd` content invalidates the condition.
- The frozen source set during stage 1.
- `docs/VISUAL_ROUND_TRIP_EXPERIMENT_01.md`, `docs/vrtv01/packages/`, the per-view provenance table, the seeded-defect list, the View C pre-disclosure list.
- Any finding produced by another condition.

## Legend supplied with the images — verbatim

```text
These four images are non-authoritative projections of a completed simulation campaign. They were hand-authored from prose documentation, not mechanically derived. They may omit information and they may contain errors. They are not the system and they are not evidence.
```

Do **not** tell the reviewer the representation class of each view or its omissions list beyond this legend.

## Stage 1 prompt — verbatim

```text
You are a skeptical technical reviewer. You have been given four visual projections of a completed simulation campaign.

Identify suspicious topology, evidence-chain, experiment-design, or claim-boundary relationships that deserve source verification. Do not assume the diagrams are correct.

Return hypotheses only. For every item, name the exact source information you would request to confirm or refute it. Do not propose new features.

Return a JSON array using the candidate finding schema you have been given.
```

## Stage 2 prompt — verbatim

```text
Here is the complete frozen source set. For each hypothesis you produced in stage 1, determine whether the committed source confirms it, rejects it, or leaves it unresolved. Cite the exact file and field you consulted.
```

## Critical ordering requirement
**Stage 1 output must be written to disk and closed before any source file is supplied.** If source reaches the reviewer before stage 1 is saved, the run is void — discard it and start a new session. Record the void.

## Record
As V0, plus: which packet (clean or seeded), and the sha256 of each image actually supplied.
