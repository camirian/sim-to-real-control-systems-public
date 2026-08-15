# VRTV-01 execution packages — common header

## Three distinct SHAs — do not conflate

| Identity | SHA |
|---|---|
| `SOURCE_BASELINE_SHA` | `f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29` |
| `PREREGISTRATION_SHA` | `0369dab5b83cedcc92847088ba939de092c295c0` |
| `CURRENT_EXECUTION_PACKAGE_HEAD` | `bb821bb55d730cfdf0340743826cedcc914e7103` at this review; re-verify PR #16 before execution |

**`PREREGISTRATION_SHA` is `0369dab`.** Later commits on this branch add execution
artifacts and do not move it. Never cite the PR head as the preregistration SHA.

**Control plane:** `docs/vrtv01/EXECUTION_CONTROL.md` — execution matrix, binding
model-control rule, and the model selection record that must be completed before V0 runs.

**View hash manifests:** `docs/vrtv01/VIEW_HASHES.txt` (clean), `docs/vrtv01/SEEDED_HASHES.txt` (seeded)
**Execution record:** issue #17

## Execution matrix — one instance each

`V0-CLEAN` · `V1-CLEAN` · `V1-SEEDED` · `V2-CLEAN` · `V2-SEEDED` · `V3`

Primary representation comparison is **`V0-CLEAN` vs `V1-CLEAN` vs `V2-CLEAN`**. The
seeded runs are a transformation-error robustness control and must not be counted as
ordinary clean-condition outcomes.

## Binding model control

All five reviewer runs use the **same provider, model/version, and materially identical
configuration**. Only the input packet and clean/seeded assignment may vary. A run that
cannot meet this is void — record it and rerun. V3 may use a different independent model.
V0 must run on the same multimodal-capable model as V1/V2, not a text-only model.

## Rules binding every package

1. **One fresh session per condition.** V0, V1, V2 and V3 must not share a session, a context window, or a conversation history.
2. **No cross-condition disclosure.** No reviewer may be told what another condition found, how many findings exist, or that other conditions exist.
3. **Fail-closed filesystem isolation.** Reviewers run outside the repository from a
   dedicated staging directory created by `stage_runs.py`; no `.git`, remote, symlink,
   parent path to the repository, answer key, preregistration, other package, or Mermaid
   source is available. A working directory alone is not sufficient.
   `docs/VISUAL_ROUND_TRIP_EXPERIMENT_01.md`, this file, and the other packages are
   forbidden inputs for V0/V1/V2.
3b. **Network boundary — two classes, do not conflate.** Full definition in
   `docs/vrtv01/EXECUTION_CONTROL.md` §5b.
   - **Reviewer tool/data network access: DENIED.** No web browsing; no GitHub or any git
     remote; no fetching repository files by any path or protocol; no arbitrary
     HTTP/HTTPS/DNS/socket tools; no search, retrieval, code-execution, or file-download
     affordance that could surface forbidden experiment material. **If the reviewer can
     name a URL and receive its contents, the run is void.**
   - **Model transport: MAY be allowed**, as the minimum network path required to reach
     the preselected provider/API for the pinned model. **A cloud-hosted treatment model
     is permitted.** This is inference transport, not reviewer capability.
   - **Invariant:** the reviewer sees **only** the files in its staged input directory.
     Transport does not widen that set.
   - If the harness cannot separate the two — e.g. it exposes network to the model as a
     *tool* — then use a harness that can (typically a plain API client with **no tools
     registered**, not an agentic harness with web/file tools available), or use a
     sufficiently capable **local** multimodal model. Apply the chosen route identically
     to all five treatment sessions; a transport difference between conditions is a
     configuration difference and voids the affected run.
4. **Two-stage protocol for V0/V1/V2.** Stage 1 output must be saved before stage 2 material is supplied.
5. **Record for every condition:** model + provider + version, session start/end timestamps, wall-clock per stage, total tokens or cost if the provider reports it, and the exact input file list.
6. **Preserve failures.** Do not delete, retry, or clean up a poor reviewer run. A weak run is data.
7. **The builder of the views may not adjudicate.** V3 must be run by a session that did not produce the views or any V0/V1/V2 output.
8. **This session that authored the preregistration is contaminated** and may not serve as any reviewer condition.

The exact input file list and SHA-256 values are recorded in the staging manifest. Any
extra file, symlink, repository visibility, or **reviewer-accessible** network capability
voids the run. Model-provider transport does not.

## Frozen source set (V0, V2, and stage 2 of all conditions)

```
README.md
RESULTS.md
MASTER_PLAN.md
docs/M4_RUNTIME_VALIDATION.md
docs/REPRODUCE_CAMPAIGN.md
campaign/manifests/m4-franka-filtered-vs-unfiltered-v1.json
campaign/results/m4-franka-filtered-vs-unfiltered-v1/
```

## Candidate finding schema (stage 1 output, all of V0/V1/V2)

```json
{
  "local_id": "string, unique within this condition only",
  "claim": "one sentence, falsifiable, no hedging",
  "rationale": "why the reviewer believes it",
  "severity_if_true": "CRITICAL | MAJOR | MINOR | NOTE",
  "requested_source_check": "exact file path and field/line that would confirm or refute",
  "reviewer_confidence": "HIGH | MEDIUM | LOW",
  "derived_from": "SOURCE | VIEW_A | VIEW_B | VIEW_C | VIEW_D | COMBINED"
}
```

## Stage 2 output schema (all of V0/V1/V2)

```json
{
  "local_id": "matching stage 1",
  "self_verdict": "CONFIRMED | REJECTED | UNRESOLVED",
  "evidence_path": "exact file and field consulted",
  "notes": "string"
}
```
