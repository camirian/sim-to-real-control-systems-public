# VRTV closure record — experiment retired unexecuted

**Status:** CLOSED, UNMERGED, zero results
**Applies to:** PR #16 (`docs/m4-visual-round-trip-experiment`), head `d3c2789310a9c274b4e79b510a003ce26912a687`
**Source baseline:** `f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29` (unchanged by this experiment)
**Date closed:** 2026-08-16

## 1. What this record is

This closes the Visual Round-Trip Verification (VRTV) line of work on the frozen
M4 campaign. It is a **disposition record, not a result**. No scientific finding
about visual versus textual representation was obtained, and none may be cited
from this branch.

## 2. Disposition of each experiment

### VRTV-01 — pre-treatment design infeasibility

VRTV-01 was preregistered (`0369dab`) and then found **not executable as
designed**. Its frozen source set measures **3,621,822 tokens** (`tiktoken
o200k_base`) against the selected treatment model's **922,000** input maximum —
**3.93× over capacity**. 97% of that load is per-sample raw telemetry (40 runs ×
2,002 rows × two CSV files).

This is a **design infeasibility discovered before treatment**, not a negative
result. Zero reviewer conditions were run. The preregistration remains frozen and
unmodified at `0369dab` as the record of a design that could not run.

### VRTV-02 — corrected, staged, never executed

VRTV-02 (`docs/vrtv02/VRTV02_PREREGISTRATION.md`) made the smallest defensible
correction: it replaced "the whole committed evidence directory" with a
**bounded, deterministically enumerated authoritative review corpus** of
**129 files · 311,674 bytes · 109,188 tokens (`o200k_base`)**, a pure function of
a commit and a fixed allow-list rule set — not retrieval, not ranking.

VRTV-02 reached **preregistered, not executed**. Its harness, prompts, corpus
manifest and coverage report are staged; **no condition was ever run**.

## 3. Execution ledger — zero treatments

| Condition | Description | Executions |
|---|---|---:|
| V0 | source/text-only baseline | **0** |
| V1 | visual packet first | **0** |
| V2 | source + visual | **0** |
| V3 | fresh cross-representation verifier / blind adjudicator | **0** |

**Total treatment executions across VRTV-01 and VRTV-02: 0.**

Consequently there is **no visual-vs-text scientific conclusion**, no effect size,
no comparison, and no evidence about representation. Nothing about the
representation hypothesis was learned, confirmed, or refuted.

## 4. Why this branch is not merged

The branch contains **deliberately seeded incorrect diagrams**
(`docs/vrtv01/seeded/`) and an operator-only answer key. These were transformation
controls for an experiment that never ran. They are **defective by construction**
and must never reach `main`, where a reader could mistake them for descriptive
architecture.

Merging staged scaffolding for an unexecuted experiment would also add
experiment-shaped documentation to the public surface that no result supports.

## 5. Design lessons preserved

These are **methodological lessons, not findings**. They cost real design effort
and are worth keeping:

1. **Measure the corpus against the context budget during preregistration**, not
   after freezing. Feasibility is part of experimental design.
2. **Raw per-sample telemetry dominates evidence corpora.** 97% of the load came
   from CSV rows that a reviewer would never read line-by-line. Bounded
   allow-lists beat "include the evidence directory."
3. **The obvious fixes are confounds.** RAG/retrieval, source-on-demand, and
   telemetry downsampling each solve the capacity problem while destroying the
   thing under test — retrieval failure is indistinguishable from reviewer
   failure, and summarising the baseline silently converts the control condition
   into a treatment condition.
4. **Do not assume visual superiority.** IsoBench-style counterevidence means the
   text baseline is a genuine competitor, not a strawman.
5. **Seeded controls need blinding guards.** Filename leakage (`*_seeded.*`)
   defeats the control; this was caught pre-execution (`e7e1a06`).
6. **Preregistration discipline held.** Infeasibility was recorded as
   infeasibility rather than being reinterpreted into a result. That is the
   correct outcome and the process worked.

## 6. Why close now

M4's technical baseline is complete. The remaining M4 lane is **public
explanation and distribution** of a finished proof. Portfolio value now favours
shipping the completed M4 case study over continuing a meta-experiment about
review methodology that has produced zero results after multiple redesigns.

## 7. Preservation

- PR #16 is closed **unmerged**.
- The branch `docs/m4-visual-round-trip-experiment` and its full commit history
  are **retained**, not deleted.
- If the representation question is resumed, it starts as a **new experiment
  version** against a fresh preregistration — not by reviving this branch's
  staged state.

## 8. Citation boundary

**No artifact on this branch may be cited as a result, finding, or measurement.**
VRTV-01 and VRTV-02 produced experimental designs and one measured *capacity*
fact (corpus token counts). That is the complete set of what exists.
