# VRTV-02 — Cross-representation review of the frozen M4 campaign, bounded corpus

**Status:** preregistered, not executed
**Supersedes for execution purposes:** VRTV-01 (`0369dab5b83cedcc92847088ba939de092c295c0`)
**Source baseline:** `f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29` (unchanged)
**Technical campaign:** frozen `m4-franka-filtered-vs-unfiltered` v1 — no new simulation runs

## 1. Why VRTV-02 exists

VRTV-01 was **not executable as preregistered**. Its frozen source set measures
**3,621,822 tokens** (`tiktoken o200k_base`) against the selected treatment model's
**922,000** input maximum — **3.93× over**. 97% of that load is per-sample raw telemetry:
40 runs × 2,002 rows × two CSV files.

**VRTV-01 is recorded as a pre-treatment design infeasibility, not a treatment result.**
Zero reviewer conditions were executed. It produced no finding, no comparison, and no
evidence about representation. Nothing about the representation hypothesis was learned or
refuted, and no VRTV-01 artifact may be cited as a result.

The VRTV-01 preregistration is **not modified or reinterpreted**. It remains frozen at
`0369dab` as the record of a design that could not run.

## 2. The single change

VRTV-02 makes the **smallest scientifically defensible correction**: it preregisters a
**bounded authoritative review corpus** in place of "the whole committed evidence
directory."

That is the only change. Everything else is inherited from VRTV-01 unchanged.

### Not adopted, deliberately

The following would each solve the context problem and are each rejected, because they
would add an experimental variable to an experiment whose entire purpose is to isolate
**representation access**:

- **RAG / vector database / retrieval.** Retrieval is a fallible subsystem. A missed
  chunk is indistinguishable from a reviewer failing to notice something, which would
  confound the primary measurement outright.
- **Source-on-demand.** Reintroduces a reviewer tool and violates the Class 1 network and
  tool denial.
- **Telemetry downsampling or summarisation.** Inserts a *derived representation* into
  what is supposed to be the authoritative baseline, quietly converting V0 from a source
  condition into a representation condition — the precise thing under test.
- Multi-agent debate, a second judge, or new metrics because recent literature suggests
  them. Those are future CRV experiments; none is required to recover this one.

## 3. Bounded authoritative review corpus

Deterministically enumerated by `docs/vrtv02/build_corpus.py` from
`SOURCE_BASELINE_SHA`. It is a **fixed preregistered allow-list**, a pure function of a
commit and a rule set — not a search, not a ranking, not a retrieval.

Full manifest with per-file byte counts and SHA-256: `docs/vrtv02/CORPUS_MANIFEST.json`.
Token measurement: `docs/vrtv02/CORPUS_TOKENS.json`.

**129 files · 311,674 bytes · 109,188 tokens (`o200k_base`)**

| Included category | Files | Rationale |
|---|---:|---|
| `authoritative_docs` | 5 | README, RESULTS, MASTER_PLAN, M4 runtime validation, reproduce-campaign. Carry the campaign narrative, reported statistics, claim boundary and pre-campaign validation history. |
| `campaign_manifest` | 1 | Design, disturbance, filter, sampling, controller, evidence policy, non-claims, provenance. |
| `campaign_rollup` | 3 | `campaign_results`, `campaign_summary`, `preflight`: scheduled/valid/invalid/failed counts, integrity index, per-condition aggregates. |
| `per_run_evidence` | 40 | Per-run checks, thresholds, environment, `overall_passed`. |
| `per_run_raw_evidence` | 40 | Per-run controller/filter/rate/reset/signals summary, start state, seed, condition, status, file hashes, `manifest_sha256`. No per-sample data. |
| `per_run_metadata` | 40 | `run_id`, `scenario`, `seed`. |

| Excluded category | Files | Rationale |
|---|---:|---|
| `raw_high_frequency_telemetry` (`telemetry.csv`) | 40 | ~2,079,029 tokens, 57% of the infeasible corpus. Raw 200 Hz per-sample traces. |
| `raw_ground_truth_traces` (`truth.csv`) | 40 | ~1,433,605 tokens, 40%. Raw per-sample reference traces. |

**Excluded ≠ non-authoritative.** Both classes remain committed, hashed, authoritative
evidence in the repository. They are excluded from the *treatment model context* only.

## 4. Terminal state for claims requiring excluded evidence

Any candidate finding that genuinely requires excluded raw per-sample evidence must
terminate as:

```
NOT_CHECKABLE_FROM_REVIEW_CORPUS
```

It must **not** be guessed, inferred, or silently marked SUPPORTED or REFUTED. This state
is distinct from `UNRESOLVED` (the corpus is insufficient in principle) and from
`NOT_CHECKABLE_FROM_AVAILABLE_EVIDENCE` (the repository lacks the artifact entirely).
Here the artifact exists and was deliberately withheld from context.

The count of `NOT_CHECKABLE_FROM_REVIEW_CORPUS` terminations is itself a reportable
outcome: a high count means the bounded corpus was drawn too tightly and VRTV-03 should
widen it, not that the reviewers underperformed.

## 5. Fairness gate — visual-to-source coverage

Before freezing, every material factual assertion encoded in the **clean** V1/V2 visual
stimuli was required to be verifiable from this corpus. If a visual asserted something a
reviewer could not check, V1/V2 would be shown unverifiable claims while V0 was not.

`docs/vrtv02/coverage_check.py` enumerates 36 material assertions across clean Views A–D
and requires each to be supported by at least one corpus artifact. Report:
`docs/vrtv02/COVERAGE_REPORT.json`.

**Result: 36/36 supported. PASS.** The eight lowest-support assertions were additionally
inspected by hand and confirmed on-point, not spurious regex matches.

This gate checks **corpus coverage, not diagram correctness.** Whether the source agrees
with a diagram is the reviewers' job; this proves only that they are able to look.

## 6. Inherited unchanged from VRTV-01

- **Visual stimuli.** Clean Views A–D and both seeded variants remain **byte-identical**,
  verified against `VIEW_HASHES.txt` and `SEEDED_HASHES.txt`.
- **Conditions and matrix.** V0-CLEAN, V1-CLEAN, V1-SEEDED, V2-CLEAN, V2-SEEDED, V3.
  Primary comparison remains V0-CLEAN vs V1-CLEAN vs V2-CLEAN; seeded runs remain a
  transformation-error robustness control and are not pooled.
- **Prompts.** Verbatim, unchanged, in `docs/vrtv01/packages/`.
- **Two-stage protocol** and the requirement that V1 stage-1 output is closed before any
  source is supplied.
- **Scoring and metrics**, including the View C pre-disclosure exclusion.
- **Decision rule:** `PROMOTE_FOR_SECOND_DOGFOOD`, `PUBLIC_COMMS_ONLY`,
  `REVISE_AND_REPEAT`, `STOP_NO_LIFT`.
- **Isolation:** §5b Class 1 reviewer tool/data network denial; Class 2 model transport
  only; guards G1–G7.
- **Model control:** one provider, model and configuration across all five treatment runs.
- **Claim boundary and the frozen M4 campaign**, untouched.

## 7. Preserving the experimental variable

Wherever a condition receives source, it receives **exactly this corpus** — same files,
same bytes, same hashes. V0-CLEAN, V2-CLEAN, V2-SEEDED stage-1 and stage-2 of every
condition draw from one enumeration, so V0/V1/V2 still differ only in representation
access.

## 8. V3

V3 remains independent, source-grounded adjudication and inherits the same bounded
evidence-access contract, so its claim scope matches what the reviewers could actually
check. V3 additionally adopts `NOT_CHECKABLE_FROM_REVIEW_CORPUS` as a terminal verdict.
V3 still must not learn which condition produced a finding, nor that seeding exists.

## 9. Freeze

This document is the VRTV-02 preregistration. Once any reviewer condition executes, no
view, prompt, corpus rule, metric or threshold may change. The frozen VRTV-02
preregistration is this file's commit SHA recorded in the execution record, together with
`CORPUS_MANIFEST.json`, `CORPUS_TOKENS.json`, `VIEW_HASHES.txt` and
`SEEDED_HASHES.txt`. Material change after execution creates VRTV-03.

## 10. Cost estimate

Measured corpus, official `gpt-5.6-sol` pricing ($5.00/M input, $30.00/M output). Every
request sits below the 272,000-token long-context threshold, so standard pricing applies
throughout. Largest single request is 119,588 tokens — **13.0% of the 922,000 maximum**.

| Run | stage-1 in | stage-2 in | low | expected | conservative |
|---|---:|---:|---:|---:|---:|
| V0-CLEAN | 109,588 | 113,588 | $1.33 | $1.54 | $2.47 |
| V1-CLEAN | 10,400 | 113,588 | $0.83 | $1.04 | $1.97 |
| V1-SEEDED | 10,400 | 113,588 | $0.83 | $1.04 | $1.97 |
| V2-CLEAN | 119,588 | 113,588 | $1.38 | $1.59 | $2.52 |
| V2-SEEDED | 119,588 | 113,588 | $1.38 | $1.59 | $2.52 |
| **TOTAL (5 treatments)** | | | **$5.74** | **$6.79** | **$11.44** |

**Conservative upper bound including one voided rerun and image-token estimation error:
~$14.30.**

Image tokens are estimated at ~10,000 for the four-view packet, scaled from the measured
preflight anchor (1600×600 ≈ 1,190 tokens). Estimate only — the views were deliberately
**not** sent to the model to measure them.

**V3 is not included.** It runs on Anthropic `claude-opus-4-8`, a separate provider with
separate billing.

**Account balance: NOT AVAILABLE.** The project key lacks the `api.usage.read` scope and
`/dashboard/billing/*` requires a browser session key. Not inferred.
