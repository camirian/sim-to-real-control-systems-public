# Package V0 — SOURCE ONLY

Read `00_COMMON.md` for binding rules, SHAs, and schemas. Run in a fresh session.

## Allowed inputs
The frozen source set only. Read-only.

## Forbidden information
- Any rendered view, diagram, image, or Mermaid source.
- `docs/VISUAL_ROUND_TRIP_EXPERIMENT_01.md` and everything under `docs/vrtv01/`.
- Any knowledge that this is an experiment, that other conditions exist, or that representations are being compared.
- Any finding produced by another condition.

## Stage 1 prompt — verbatim

```text
You are a skeptical technical reviewer. You have been given the committed source and evidence for a completed simulation campaign.

Identify concrete defects, contradictions, provenance gaps, misleading claims, missing limitations, or architecture/evidence inconsistencies.

Separate findings you believe are valid from hypotheses you cannot yet confirm. For every item, cite the exact source artifact or field that would confirm or refute it. Do not propose new features. Do not suggest improvements; find problems.

Return a JSON array using the candidate finding schema you have been given.
```

## Stage 2 prompt — verbatim

```text
Here is the complete frozen source set again. For each item you produced in stage 1, determine whether the committed source confirms it, rejects it, or leaves it unresolved. Cite the exact file and field you consulted.
```

## Record
Model/provider/version; stage 1 and stage 2 wall-clock separately; time to first item; tokens/cost; exact file list supplied.

## Contamination rule
If the reviewer requests a diagram, architecture picture, or visual summary, **refuse and record the request as an event.** Do not supply one. The request itself is data.
