# Package V2 — SOURCE + VISUAL

Read `00_COMMON.md` for binding rules, SHAs, and schemas. Run in a fresh session.

## Allowed inputs
The frozen source set **and** four rendered PNGs together, from an isolated stage-1
directory. Hash-verify every image before supplying it. The repository, packages, Mermaid
sources, and answer key are unavailable to the reviewer, as is reviewer tool/data network
access (`00_COMMON.md` rule 3b). Model-provider transport may remain open — a cloud-hosted
pinned model is permitted.

### Two distinct runs

| Run | Images supplied |
|---|---|
| `V2-CLEAN` | the four clean PNGs — **primary comparison** |
| `V2-SEEDED` | seeded A + seeded B + **clean** C and D — **robustness control only** |

The reviewer is never told that seeding exists, that two runs exist, or which packet it received. `V2-SEEDED` is scored for seeded-defect detection only and must not be pooled into the primary representation comparison.

Both runs use the same provider, model/version and configuration as V0-CLEAN and V1 — see `docs/vrtv01/EXECUTION_CONTROL.md`.

## Forbidden information
- Mermaid source text.
- `docs/VISUAL_ROUND_TRIP_EXPERIMENT_01.md`, `docs/vrtv01/packages/`, provenance table, seeded list, pre-disclosure list.
- Any finding produced by another condition.

## Stage 1 prompt — verbatim

```text
You are a skeptical technical reviewer. You have been given the committed source and evidence for a completed simulation campaign, together with four visual projections of it.

The images are non-authoritative projections. They were hand-authored from prose documentation, not mechanically derived. They may omit information and they may contain errors.

Identify concrete defects, contradictions, provenance gaps, misleading claims, missing limitations, or architecture/evidence inconsistencies.

Separate findings you believe are valid from hypotheses you cannot yet confirm. For every item, cite the exact source artifact or field that would confirm or refute it. Do not propose new features.

Return a JSON array using the candidate finding schema you have been given. Set derived_from to record whether each item came from source, a specific view, or both.
```

## Stage 2 prompt — verbatim
Identical to V0 stage 2.

## Note on symmetry
V2's stage 1 prompt is V0's with one added paragraph naming the images and repeating the same non-authoritative legend V1 receives. **No condition-specific quality instruction** — such as "trace it back to the source before accepting" — may be added here. That would confound representation access with prompt quality.

## Record
As V1.
