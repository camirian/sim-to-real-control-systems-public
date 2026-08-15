# VRTV-01 minimal API execution harness

Three scripts. No orchestration, no retries, no finding parsing, no reasoning.
Anything that cannot be verified fails closed.

| Script | Purpose |
|---|---|
| `pin_model_id.py` | Query the provider Models endpoint and resolve the exact treatment model ID. Writes `MODEL_PIN.json`. |
| `synthetic_preflight.py` | Verify auth, image ingestion, JSON output, model identity, reasoning config, zero tools, and transport — using a self-generated synthetic image and sentence. Writes `PREFLIGHT_RESULT.json`. |
| `run_condition.py` | Submit one staged condition stage and save the raw response plus identity metadata. |

## Order

```
1. pin_model_id.py            -> MODEL_PIN.json          (needs OPENAI_API_KEY)
2. synthetic_preflight.py     -> PREFLIGHT_RESULT.json   (must PASS)
3. stage_runs.py              -> staging tree            (outside the repo)
4. run_condition.py           -> raw response + metadata (per run, per stage)
```

## Zero tools

The `tools` key is **never sent**. An empty `tools: []` still advertises tool capability
to some providers, so the key is omitted entirely. `run_condition.py` records
`tools_registered: []` in metadata, and the preflight asserts `tools_key_sent == false`.

## Fail-closed guards (all verified by test)

`run_condition.py` refuses to run when:

| Guard | Condition |
|---|---|
| G1 | `MODEL_PIN.json` missing — the model ID must come from the provider, not memory |
| G2 | a forbidden artifact is staged (answer key, preregistration, execution control, package) |
| G3 | Mermaid source (`.mmd`) is staged — V1/V2 receive rendered images only |
| G4 | the repository is visible from the staging root (any `.git` in the path) |
| G5 | the output directory is inside the staging tree |
| G6 | an input has an unexpected extension (anything outside `.md/.txt/.json/.yaml/.yml/.png`) |

It also refuses symlinked inputs and empty stage directories, and warns loudly when
`returned_model != requested_model` so the operator can void the run per
`EXECUTION_CONTROL.md` §4.

## Synthetic preflight isolation

`synthetic_preflight.py` builds its own 2×2 checkerboard PNG in-process (75 bytes, no
external dependencies) and uses a fixed synthetic sentence. It reads **nothing** from the
repository, the staging tree, the views, the prompts, or any finding. It cannot expose the
selected model to a VRTV artifact because it never opens one.

## What the harness does not do

It does not select a model, launch a reviewer automatically, interpret output, score
findings, or normalize/blind anything. Those are operator steps with their own controls.
