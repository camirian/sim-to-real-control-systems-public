# VRTV-01 execution control plane

Downstream of the frozen preregistration. **Nothing here edits `0369dab`.** These are
execution artifacts and controls; the experimental design they serve is fixed.

## 1. Identity model — three distinct SHAs

These are routinely conflated. They are not interchangeable and must be recorded separately.

| Identity | SHA | What it is |
|---|---|---|
| `SOURCE_BASELINE_SHA` | `f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29` | `main` at the time VRTV-01 opened. The frozen source set every condition reasons from. |
| `PREREGISTRATION_SHA` | `0369dab5b83cedcc92847088ba939de092c295c0` | The commit that froze the experimental design in `docs/VISUAL_ROUND_TRIP_EXPERIMENT_01.md`. **This is the preregistration. It is not superseded by later commits on this branch.** |
| `CURRENT_EXECUTION_PACKAGE_HEAD` | `bb821bb55d730cfdf0340743826cedcc914e7103` | The live PR head carrying the execution artifacts and fail-closed staging control. Re-verify this value against PR #16 before execution. **Never cite this as the preregistration SHA.** |

Adding execution artifacts does **not** move `PREREGISTRATION_SHA`. If the *design* ever
changes, that is VRTV-02 with its own preregistration — not a new head on this branch.

## 2. Bounded execution matrix

| Run | Packet | Counts toward |
|---|---|---|
| `V0-CLEAN` | frozen source set | **primary comparison** |
| `V1-CLEAN` | clean views A–D (PNG) | **primary comparison** |
| `V1-SEEDED` | seeded A + seeded B + clean C, D (PNG) | robustness control only |
| `V2-CLEAN` | frozen source + clean views A–D | **primary comparison** |
| `V2-SEEDED` | frozen source + seeded A + seeded B + clean C, D | robustness control only |
| `V3` | blinded normalized findings + frozen source | adjudication |

One instance each. Six sessions total.

**PRIMARY representation comparison: `V0-CLEAN` vs `V1-CLEAN` vs `V2-CLEAN`.**

**The seeded runs are a separate transformation-error robustness control.** They must not
be counted as ordinary clean-condition outcomes, pooled into per-condition finding counts,
or used to argue that a representation produced more or better findings. Their only
primary output is seeded-defect detection.

This supersedes the "half seeded / half clean" split sketched in the package drafts, which
assumed multiple instances per condition. With n=1 per cell, assignment is fixed as above.

### Statistical honesty

n=1 per cell. This matrix **cannot** support a quantitative claim about representation
effects. It can support: existence findings ("V1 surfaced something V0 did not"),
qualitative failure-mode attribution, and a go/no-go on whether a larger run is worth
funding. Any result stated as a rate, percentage, or comparison of magnitudes is
over-reading this design. `PROMOTE_FOR_SECOND_DOGFOOD` means *run a properly powered
experiment next* — it does not mean the effect is established.

## 3. Binding model-control rule

`V0-CLEAN`, `V1-CLEAN`, `V1-SEEDED`, `V2-CLEAN` and `V2-SEEDED` **must** use:

- the same provider;
- the same model and version string;
- materially identical model configuration (temperature/reasoning effort/sampling, tool
  access, system prompt scaffolding, context limits, filesystem permissions, and network
  posture — both the reviewer tool/data denial and the model-transport route, per §5b).

**Only the representation/input packet and the clean/seeded assignment may vary.**

If any reviewer session cannot meet this — provider outage, version rollover mid-run,
a multimodal-capability difference — the affected run is **void**. Record the void and
rerun on the pinned configuration. Do not silently substitute a different model; a model
difference and a representation difference are indistinguishable after the fact.

`V3` **may and should** use a different independent strong model/provider. V3's job is
independent adjudication, so provider diversity there is a feature, not a confound.

The selected treatment model must also satisfy all of these properties before V0:

- multimodal image understanding;
- enough context for the complete frozen source set;
- a reproducible, pinnable model identity;
- the same provider/model/configuration available for all five treatment sessions;
- no need for repository access: each session can run from its staged input directory with
  repository access denied and **reviewer tool/data network access denied** (§5b Class 1).
  Model-provider transport (§5b Class 2) may be open; a cloud-hosted model is permitted.

Note one unavoidable asymmetry: V1 and V2 require a multimodal model, V0 does not. The
rule resolves this by requiring the *same multimodal-capable model* for all five reviewer
runs, including V0. Do not run V0 on a text-only model.

## 4. Model selection record — complete BEFORE the first condition runs

No condition may start until this record is complete and committed.

**Decision recorded 2026-08-15. Model ID resolved against the authenticated OpenAI
Models endpoint on 2026-08-15T22:43Z. Synthetic preflight BLOCKED on provider quota —
see "Preflight status" below. This record is therefore COMPLETE for model identity and
INCOMPLETE for runtime capability confirmation.**

| Field | Value | Established how |
|---|---|---|
| Treatment provider | **OpenAI** | decision |
| Treatment family | **GPT-5.6 Sol** | decision |
| **Exact treatment model ID** | **`gpt-5.6-sol`** | **authenticated Models endpoint** |
| Pin basis | **`explicit-id-no-snapshot-published`** | authenticated — no `gpt-5.6-sol-<snapshot>` ID is published to this account |
| `gpt-5.6*` visible to this account | `gpt-5.6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra` (118 models total) | authenticated |
| Forbidden aliases rejected | `gpt-5.6`, `gpt-5.6-latest`, `gpt-5` | enforced in `harness/pin_model_id.py` |
| API | **OpenAI Responses API**, plain client — not Codex, ChatGPT, or any agent harness | harness contract |
| Reasoning effort | **high** | harness parameter |
| `store` | **false** | harness parameter |
| Registered tools | **NONE** | harness contract |
| Tools key sent | **false** — the key is omitted entirely, since `tools: []` still advertises capability | harness contract, asserted by preflight |
| Reviewer-accessible web | **DENIED** | §5b Class 1 |
| Reviewer-accessible GitHub | **DENIED** | §5b Class 1 |
| Reviewer-accessible arbitrary network | **DENIED** | §5b Class 1 |
| Model transport | **OpenAI API transport only** | §5b Class 2 |
| Multimodal image input | **UNCONFIRMED — preflight could not run (quota)** | must be confirmed before V0 |
| Frozen-source context capacity | **UNCONFIRMED — not measured against the selected model** | must be confirmed before V0 |
| Five-session pin availability | **NOT GUARANTEED BY THE API.** `gpt-5.6-sol` is an unversioned ID with no published snapshot, so the provider offers no contractual stability. Mitigation is detection, not prevention: every run records identity fields and any change voids the affected run. | honest limitation |
| Selected by | pre-execution operator under frozen VRTV-01 control | — |
| Selection timing | 2026-08-15, **before** any reviewer condition executed | — |
| Selection rationale | strong multimodal frontier reviewer; same model for all five treatment sessions; avoids a weak-local-model floor effect that would produce an uninformative null; representation is the intended independent variable | — |
| V3 provider | **Anthropic** | decision |
| V3 model | **`claude-opus-4-8`** | decision |
| V3 API visibility | **UNVERIFIED / TO BE CONFIRMED BEFORE V3** — no `ANTHROPIC_API_KEY` available at selection time | honest limitation |
| V3 API | plain Anthropic Messages API | decision |
| V3 registered tools | **NONE** | decision |
| V3 transport | Anthropic API only | decision |

Absence of Anthropic credentials does **not** block V0. V3 runs only after all five
treatment conditions and normalization, so its visibility check is due before V3, not now.

### Preflight status — BLOCKED on provider quota

`harness/synthetic_preflight.py` was run on 2026-08-15T22:43Z against `gpt-5.6-sol` and
returned:

```
HTTP 429  type=insufficient_quota  code=credit_balance_exhausted
"You have no credits remaining. Add credits to continue using the API"
```

No VRTV artifact was exposed: the request carried only the harness's self-generated 2×2
synthetic PNG and a fixed synthetic sentence. `vrtv_artifacts_exposed: false`.

Consequences, recorded rather than worked around:

- **multimodal image ingestion is unconfirmed** for the selected model;
- **JSON output conformance is unconfirmed**;
- **returned model identity and `system_fingerprint` are unobserved**, so the drift
  baseline every treatment run is compared against does not yet exist;
- **context capacity for the frozen source set is unmeasured**.

The preflight must PASS before V0. Billing was deliberately not modified — no credits
purchased, no payment method added, no auto-recharge enabled.

### Model ID resolution rule

The treatment model ID **must be derived from the provider Models endpoint, never typed
from memory.** Run `harness/pin_model_id.py` with the experiment API account; it writes
`harness/MODEL_PIN.json`.

1. If an immutable/snapshot-specific `gpt-5.6-sol-*` ID is published, **pin that**.
2. If no snapshot exists, pin the explicit ID **`gpt-5.6-sol`**.
3. **Never** pin the generic alias `gpt-5.6` (or `gpt-5.6-latest`). The script rejects
   these explicitly — a floating alias can re-point mid-experiment, which is exactly the
   drift the model-control rule exists to prevent.

### Why not Fable 5 for V3

Fable 5 is excluded as the adjudicator because its safeguard architecture can route some
requests to Opus 4.8. That would introduce a model-routing variable into adjudication for
no benefit. `claude-opus-4-8` is pinned directly.

### Identity capture and drift handling

Every treatment run records all returned identity fields: `requested_model`,
`returned_model`, `response_id`, `system_fingerprint`, `service_tier`, the provider
`x-request-id`, and usage. `harness/run_condition.py` writes these to
`<run>_<stage>_metadata.json` alongside the verbatim raw response.

**If an identity or fingerprint that should remain stable changes between treatment runs,
VOID the affected run.** Do not silently accept model drift: a mid-experiment model change
and a representation effect are indistinguishable after the fact. Re-run on the pinned
configuration and record the void.

### Preflight requirement

Before V0, run `harness/synthetic_preflight.py`. It generates its own 2×2 synthetic PNG
and a trivial synthetic sentence, and verifies authentication, image ingestion, JSON
output, model identity, reasoning configuration, `tools_registered == []`, and transport
restriction.

**It must not expose the selected model or session to any VRTV artifact** — no source, no
view, no prompt, no finding. The script reads nothing from the repository or the staging
tree by construction.

Selecting or changing the model **after** seeing any condition's output is a post-hoc
tuning route and is forbidden by the preregistration freeze.

## 5. Artifact manifest

| Artifact | Path | Hash file |
|---|---|---|
| Clean views A–D | `docs/vrtv01/views/` | `VIEW_HASHES.txt` |
| Seeded A, B | `docs/vrtv01/seeded/` | `SEEDED_HASHES.txt` |
| Clean render script | `docs/vrtv01/render_views.sh` | — |
| Seeded render script | `docs/vrtv01/render_seeded.sh` | — |
| Answer key | `docs/vrtv01/SEEDED_ANSWER_KEY.OPERATOR_ONLY.md` | **operator only — supply to no condition** |
| Packages | `docs/vrtv01/packages/` | — |

Render procedure is identical for clean and seeded: `@mermaid-js/mermaid-cli@11.12.0`,
`--theme neutral --backgroundColor white --width 1600 --scale 2`. The scripts are separate
so that rendering seeded controls can never re-render or rewrite a clean artifact.

Before the first condition: verify `sha256sum -c VIEW_HASHES.txt` and
`sha256sum -c SEEDED_HASHES.txt` both pass, and record that they did.

## 5b. Network boundary — two different things, do not conflate

Earlier wording said reviewer sessions run with "network access denied." Read literally
that would forbid a cloud-hosted treatment model, which is **not** the intent. The
isolation requirement governs what the *reviewer* can reach, not how inference is
transported.

### Class 1 — reviewer tool and data network access: **DENIED**

The reviewer must have no capability to reach anything beyond its staged inputs. Denied:

- browsing the web;
- accessing GitHub or any git remote;
- fetching repository files by any path or protocol;
- arbitrary HTTP/HTTPS, DNS, or socket tools;
- any retrieval, search, code-execution, or file-download affordance that could surface
  forbidden experiment material.

Concretely: no web-search tool, no URL-fetch tool, no repository or MCP connector, no
shell with outbound access, no package installation, no "read this link" affordance.
**If the reviewer can name a URL and receive its contents, the run is void.**

### Class 2 — model transport: **MAY be allowed, minimum path only**

The single network path required to reach the **preselected** model provider/API is
permitted. This is inference transport, not reviewer capability.

Permitted only as: outbound to the provider's API endpoint, for the pinned model,
carrying exactly the staged inputs and the prompt. Nothing else may traverse it.

### The invariant

> **The reviewer sees only the files in its staged input directory.**

Model transport does not widen that set. If transport is allowed, the reviewer's *inputs*
remain exactly the staging manifest — no more.

### If the harness cannot enforce the distinction

Some harnesses expose network to the model as a *tool* rather than as transport. There
Class 1 and Class 2 are not separable and the setup is unusable as written. Then either:

- **use a harness that can enforce the distinction** — provider transport open, reviewer
  tools closed. In practice this means a plain API client with **no tools registered**,
  rather than an agentic harness that has web/file tools available; or
- **use a sufficiently capable local multimodal model**, so no transport is needed and
  Class 1 and Class 2 collapse into a single denial.

Choosing a local model purely to satisfy this is legitimate, but it must still meet every
§3 requirement — multimodal understanding, context capacity for the full frozen source
set, pinnable identity, and availability for all five treatment sessions on identical
configuration. Do not trade experimental validity for isolation convenience: a model too
weak to review this material produces a null result that says nothing about
representation, which is a worse outcome than a harness change.

### Record either way

Whichever route is taken, record it in §4 and apply it **identically to all five treatment
sessions**. A transport difference between conditions is a configuration difference, and
under §3 that voids the affected run.

## 6. Required fail-closed staging and launch boundary

The repository is an operator workspace, not a reviewer sandbox. A reviewer must never
be launched from the repository, a repository worktree, or a directory whose mounted
filesystem includes the repository. Reviewer conditions must run from a separate,
permission-restricted staging root outside the repository, with no `.git`, remote,
symlink, parent traversal path to the repository, answer key, package, preregistration,
or Mermaid source. Mount only the run's input directory plus a separate output location,
and deny reviewer tool/data network access per §5b Class 1. Model-provider transport
(§5b Class 2) may remain open.

Use the committed `docs/vrtv01/stage_runs.py` helper. It copies the frozen source from
`SOURCE_BASELINE_SHA` using `git archive`, verifies image hashes before copying, rejects
non-empty destinations and symlinks, rejects normalized V3 findings that retain
reviewer/condition/view identity, and writes `STAGING_MANIFEST.json`. It never launches
a reviewer.

Initial staging, from a path outside the repository:

```text
python3 docs/vrtv01/stage_runs.py \
  --repo /path/to/sim-to-real-control-systems-public \
  --stage-root /path/outside/repo/vrtv01-runs \
  --run V0-CLEAN --run V1-CLEAN --run V1-SEEDED \
  --run V2-CLEAN --run V2-SEEDED
```

V1 stage 1 must be run from `V1-CLEAN/stage-1` or `V1-SEEDED/stage-1` only. Save and
close its output outside the staging tree, then reveal source only by running:

```text
python3 docs/vrtv01/stage_runs.py \
  --repo /path/to/sim-to-real-control-systems-public \
  --stage-root /path/outside/repo/vrtv01-runs \
  --advance-v1 V1-CLEAN --stage1-output /path/to/closed-stage1-output.json
```

The same command applies to `V1-SEEDED`. Do not reuse a stage-1 session after a
violation; record the run void and start a fresh session. Stage 2 receives only the
newly created `stage-2` source directory and its saved stage-1 output.

V3 must be staged only after normalization and its output must be a condition-neutral
JSON file:

```text
python3 docs/vrtv01/stage_runs.py \
  --repo /path/to/sim-to-real-control-systems-public \
  --stage-root /path/outside/repo/vrtv01-runs \
  --stage-v3 --normalized-findings /path/to/normalized_findings.json
```

The operator must inspect the manifest and launch each fresh session in a restricted
environment with repository access denied and reviewer tool/data network access denied
(§5b Class 1). Model-provider transport (§5b Class 2) may be open, so a cloud-hosted
pinned model is permitted. A working directory alone is not an isolation boundary, and
neither is an instruction telling the model not to browse — the capability must be absent.
