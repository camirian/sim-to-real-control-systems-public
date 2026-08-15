# SEEDED DEFECT ANSWER KEY — OPERATOR ONLY

> **DO NOT SUPPLY THIS FILE, ITS CONTENTS, OR ANY PARAPHRASE OF IT TO V0, V1, V2, OR V3.**
>
> This file is an input to **no** reviewer condition. It is consumed only by the human
> operator, and only **after** V3 has returned its verdicts and the blinding map has been
> rejoined. Supplying it — or naming the number of seeded defects — to any model session
> voids the affected run.
>
> V3 in particular must not know that seeding exists. V3 adjudicates findings on their
> merits against source; the operator, not V3, decides afterwards which findings
> correspond to planted defects.

Superseding note: §3.3 of the frozen preregistration (`0369dab`) says the seeded defect
list is "held by the adjudicator only." "Adjudicator" there means the **human operator
performing adjudication**, not the V3 model session. This file states that explicitly.
The frozen preregistration text is not edited; this is a downstream clarification.

## Seeded defect 1 — View A

**Artifact:** `docs/vrtv01/seeded/view_a_system_topology_seeded.mmd` / `.png`

**Alteration:** the seeded disturbance node was moved from **before** the condition split
to **after** it, and onto the filtered arm only.

- Clean topology: `ISAAC -> NOISE -> CONDITION -> {FILTER, PASS}`
- Seeded topology: `ISAAC -> CONDITION -> {NOISE -> FILTER, PASS}`

**What it contradicts:** the campaign injects one seeded disturbance into the feedback
path *before* the condition split, so both arms receive the same disturbed feedback and
differ only in the filter. The seeded view depicts the unfiltered arm receiving *clean*
feedback, which would make the two arms differ in two places and would invalidate the
comparison entirely.

**Correct detection looks like:** the reviewer states that the unfiltered arm appears to
receive undisturbed feedback, that this would confound the experiment, and requests the
disturbance-injection point in source.

**Do not credit:** a generic remark that the diagram "looks asymmetric" with no statement
of what the asymmetry implies.

## Seeded defect 2 — View B

**Artifact:** `docs/vrtv01/seeded/view_b_evidence_provenance_seeded.mmd` / `.png`

**Alteration:** exactly one edge redirected. `HASH -> AGG` became `RAW -> AGG`.

**What it contradicts:** aggregation runs over verified evidence packets, downstream of
manifest/hash verification. The seeded view routes `scripts/build_results.py` directly
from raw telemetry, so `RESULTS.md` and every public claim derived from it would bypass
hash verification. `HASH` becomes a dangling terminal node.

**Correct detection looks like:** the reviewer states that the aggregation/claim path
bypasses hash verification, or that the verification step is not on the path to
`RESULTS.md`, and requests the aggregation input in source.

**Do not credit:** noticing only that `HASH` has no outgoing edge, without stating the
consequence for the claim path.

## Scoring

- Seeded runs are scored **only** for `seeded_defects_caught` / `seeded_defects_planted`
  (denominator 1 per seeded view actually supplied).
- Seeded runs are a **transformation-error robustness control**. Their findings must not
  be pooled with clean-condition outcomes in the primary representation comparison.
- A seeded run that produces the planted finding **and** a genuine source finding may have
  the source finding recorded, flagged `from_seeded_run: true`, and excluded from the
  primary comparison.
