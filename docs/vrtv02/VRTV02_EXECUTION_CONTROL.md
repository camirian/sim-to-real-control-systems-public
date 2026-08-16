# VRTV-02 execution control — AUTHORITATIVE OPERATOR SURFACE

**Read this before executing anything. It supersedes `docs/vrtv01/EXECUTION_CONTROL.md`
and `docs/vrtv01/packages/` for execution purposes.**

> ## Do not follow the VRTV-01 operator instructions
>
> `docs/vrtv01/EXECUTION_CONTROL.md` and `docs/vrtv01/packages/*.md` are **preserved
> historical records of a design that could not run.** Their staging commands
> (`docs/vrtv01/stage_runs.py`) build the **3,621,822-token** source set, which exceeds
> the model's 922,000 input maximum by 3.93×. Following them will fail, and if it did not
> fail it would run a different experiment.
>
> They are deliberately **not rewritten**, because they are the record of what was frozen
> at the time. Their superseded status is documented here instead.

## 1. Canonical pointers

| What | Path |
|---|---|
| VRTV-02 preregistration | `docs/vrtv02/VRTV02_PREREGISTRATION.md` |
| Corpus enumerator | `docs/vrtv02/build_corpus.py` |
| Corpus manifest (129 files, per-file SHA-256) | `docs/vrtv02/CORPUS_MANIFEST.json` |
| Corpus token measurement | `docs/vrtv02/CORPUS_TOKENS.json` |
| Coverage gate + report | `docs/vrtv02/coverage_check.py`, `COVERAGE_REPORT.json` |
| **Staging (VRTV-02)** | `docs/vrtv02/stage_runs_v2.py` — **not** `docs/vrtv01/stage_runs.py` |
| Exact model-visible prompts | `docs/vrtv02/prompts/` |
| Prompt hashes | `docs/vrtv02/prompts/PROMPT_HASHES.txt` |
| Continuation tests | `docs/vrtv02/test_continuation.py` |
| Runner + model pin + preflight | `docs/vrtv01/harness/` (still current) |
| Visual stimuli + hashes | `docs/vrtv01/views/`, `seeded/`, `VIEW_HASHES.txt`, `SEEDED_HASHES.txt` (frozen, byte-identical) |
| Seeded answer key | `docs/vrtv01/SEEDED_ANSWER_KEY.OPERATOR_ONLY.md` — **operator only** |

**Identities.** `SOURCE_BASELINE_SHA` = `f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29`.
`VRTV01_PREREGISTRATION_SHA` = `0369dab5b83cedcc92847088ba939de092c295c0` (historical;
infeasible design). `VRTV02_PREREGISTRATION_FREEZE_SHA` = the commit recorded in issue
#17 immediately before V0-CLEAN runs — record it there, and never cite a PR head as it.

## 2. Exact model-visible prompts — frozen

These files are the **complete** text each reviewer receives. Each Stage-1 form contains
the full candidate-finding output schema inline, because reviewers may not receive
`docs/vrtv01/packages/00_COMMON.md`. Only the provided-material sentence differs between
Stage-1 forms.

| Prompt | SHA-256 |
|---|---|
| `PROMPT_HASHES.txt` | `7d99a7ea5bb8ac070fdc19ba4292191026fb30dd2150a24f93d02f7ae2036877` |
| `stage1_V0.txt` | `8a1caaa5e5d304a8b863018087adbe76c5863c85034dbf18cc28f0cb53c10ce7` |
| `stage1_V1.txt` | `85ee3d05a75e438f47b542b0b631438ca82d892b621360fe3ef98b8b5d4f218d` |
| `stage1_V2.txt` | `61f1fa3ea18929e91565c7db92b5dc8a952743005794ee5dd5e57c875c747b5e` |
| `stage2.txt` | `7109c5dae3293b97c23f5646c2c880be92fde1de4f94d025e721315d2621467a` |
| `v3_adjudicator.txt` | `b2dca91416fd0636e7c8c6c6410844ebb665db1dc158d45414339c31dbae452b` |

Verify with `sha256sum -c` against `prompts/PROMPT_HASHES.txt` before every run. If a
hash differs, stop: the model-visible text changed.

| Run | Stage-1 prompt |
|---|---|
| V0-CLEAN | `prompts/stage1_V0.txt` |
| V1-CLEAN, V1-SEEDED | `prompts/stage1_V1.txt` |
| V2-CLEAN, V2-SEEDED | `prompts/stage1_V2.txt` |
| all five, stage 2 | `prompts/stage2.txt` |
| V3 | `prompts/v3_adjudicator.txt` |

Prompts contain no condition name, no clean/seeded identity, no mention of other
conditions, no answer-key content, no preregistration commentary and no scoring language.

## 3. Two-stage continuation

The Responses API is stateless and runs use `store: false`, so continuation is **explicit
history replay**, not provider-side state.

```
stage 1: input = [user(stage1 prompt + staged inputs)]
         -> save raw response AND the exact request
stage 2: input = [ user(stage-1 prompt, verbatim),
                   *stage-1 response.output items (verbatim, incl. reasoning),
                   user(stage2 prompt + bounded corpus) ]
```

Per OpenAI's manual-conversation-state guidance the **complete `output` array** is
replayed, not just its text, so reasoning items survive into stage 2.

`stage_runs_v2.py --advance-stage2 <RUN> --stage1-response <path>` builds stage 2 and
writes `STAGE1_CONTINUATION.json` (operator-only; excluded from model input).

**Fail-closed:** stage 2 refuses to build or run on a missing, empty, text-less,
hash-mismatched, or wrong-run stage-1 output. Verified by `test_continuation.py`.

## 4. Execution order

1. `sha256sum -c docs/vrtv02/prompts/PROMPT_HASHES.txt`
2. `sha256sum -c` both view hash manifests (12/12).
3. `python3 docs/vrtv02/coverage_check.py --corpus-dir <corpus>` → 36/36.
4. `python3 docs/vrtv02/test_continuation.py` → all pass.
5. `python3 docs/vrtv02/stage_runs_v2.py --repo . --stage-root <outside-repo>`
6. `pin_model_id.py`, then `synthetic_preflight.py` → PASS.
7. Stage 1 for each run, one fresh session each, saving raw response + request.
8. `--advance-stage2` per run, then stage 2 per run.
9. Normalize and blind; run V3 on the independent model.
10. Rejoin, apply View C pre-disclosure and seeded exclusions, decide.

## 5. Verdict vocabulary

Stage 2 (reviewer, self-verdict): `CONFIRMED`, `REJECTED`, `UNRESOLVED`,
`NOT_CHECKABLE_FROM_REVIEW_CORPUS`.

V3 (adjudicator): the same four plus `NOT_CHECKABLE_FROM_AVAILABLE_EVIDENCE`.

- `UNRESOLVED` — the corpus contains the relevant evidence surface but does not decide it.
- `NOT_CHECKABLE_FROM_REVIEW_CORPUS` — deciding it needs an authoritative artifact
  deliberately excluded from the model-visible corpus. The artifact exists; it was withheld.
- `NOT_CHECKABLE_FROM_AVAILABLE_EVIDENCE` — the evidence does not exist at all, or cannot
  decide the question even in principle. **V3 only**, since only V3 adjudicates against
  the repository rather than the bounded corpus.

A high `NOT_CHECKABLE_FROM_REVIEW_CORPUS` count means the corpus was drawn too tightly
and VRTV-03 should widen it — not that reviewers underperformed. It is the only new metric
this correction introduces.

## 6. Corrections to obsolete descriptions elsewhere

| Obsolete statement | Where | Correct as of VRTV-02 |
|---|---|---|
| Preflight uses a 2×2 synthetic PNG and checks only that a JSON key exists | earlier `EXECUTION_CONTROL.md` §4 narrative | It uses a **1600×600** synthetic image with a printed word, printed number and colour blocks, and **fails unless the model reproduces all of them**. The 2×2 version produced a false PASS. |
| G7 scans the serialized payload for any occurrence of `seeded` | earlier harness README | G7 inspects **payload structure**, checking image filenames and harness-added `--- FILE:` labels only. Content scanning produced false positives on V0-CLEAN — a condition with no images — because the corpus legitimately says "Seeded disturbance 25 Hz + AWGN". |
| `docs/vrtv01/stage_runs.py` is the staging command | VRTV-01 packages and control record | Use `docs/vrtv02/stage_runs_v2.py`. The VRTV-01 stager builds the infeasible 3.62M-token source set. |
| Stage-1 prompt refers to "the schema you have been given" | VRTV-01 packages | VRTV-02 prompts carry the full schema **inline**. |

## 7. Unchanged

Model pin `gpt-5.6-sol`, effort `high`, `store:false`, zero registered tools, §5b Class 1
reviewer network denial with Class 2 transport permitted, guards G1–G7, the execution
matrix and primary comparison, seeded runs as robustness control only, the View C
pre-disclosure exclusion, the decision rule, the visual stimuli bytes, and the claim
boundary. V3 remains `claude-opus-4-8`, visibility to be confirmed before V3.
