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

**Decision recorded 2026-08-15. Model resolved and synthetic preflight PASSED against
the live authenticated endpoint on 2026-08-15T23:03Z.**

| Field | Value | Established how |
|---|---|---|
| Treatment provider | **OpenAI** | decision |
| Treatment family | **GPT-5.6 Sol** | decision |
| **Exact treatment model ID** | **`gpt-5.6-sol`** | authenticated Models endpoint, re-derived twice |
| Pin basis | **`explicit-id-no-snapshot-published`** | authenticated — no `gpt-5.6-sol-<snapshot>` published |
| `gpt-5.6*` visible | `gpt-5.6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra` | authenticated |
| API | **OpenAI Responses API**, plain client | harness contract |
| Reasoning effort | **high** | request parameter, accepted |
| `store` | **false** | request parameter |
| Registered tools | **NONE** | harness contract |
| Tools key sent | **false** | asserted in preflight and by guard G7 |
| Reviewer web / GitHub / arbitrary network | **DENIED** | §5b Class 1 |
| Model transport | **OpenAI API only** | §5b Class 2 |
| **Multimodal image input** | **CONFIRMED** — model read a 1600×600 synthetic image and returned the printed word, printed number and block colour correctly | preflight ground-truth checks, 4/4 pass |
| **Returned model identity** | **`gpt-5.6-sol`** — matches requested | preflight |
| Context window | 1,050,000; **max input 922,000**; max output 128,000 | provider docs |
| Long-context tier | >272,000 input tokens → 2× input, 1.5× output on the full request | provider docs |
| **Frozen-source context capacity** | **FAILS — see "Context capacity blocker"** | measured |
| Five-session pin availability | **NOT GUARANTEED BY THE API** — unversioned ID; detected, not prevented | honest limitation |
| Selected by | pre-execution operator under frozen VRTV-01 control | — |
| Selection timing | 2026-08-15, before any reviewer condition executed | — |
| V3 provider / model | Anthropic / `claude-opus-4-8` | decision |
| V3 API visibility | **UNVERIFIED — confirm before V3** (no Anthropic credential) | honest limitation |

### Pre-V0 identity baseline

The preflight **does** establish the first provider-observed identity baseline, before V0.
This closes the previously recorded gap where V0 would have had to establish its own.

Baseline observed 2026-08-15T23:03Z:

```
returned_model        gpt-5.6-sol
service_tier          default
response_id           resp_0e074e97f389d947016a80f03bf330819a9b7382ca8edbf998
provider_request_id   req_8d38ab63343d41e9a4875a3ac3ef44bb
```

**Identity fields AVAILABLE and stable-checkable across runs:** `returned_model`,
`service_tier`. These must match the baseline on every treatment run.

**Identity fields AVAILABLE but NOT stable-checkable** (unique per request, recorded for
provenance only, never compared): `response_id`, `provider_request_id`.

**Identity fields UNAVAILABLE:** **`system_fingerprint` is `null`** on this endpoint. Do
not treat its absence as drift, and do not write a drift check against it. The available
drift signal is narrower than originally assumed: `returned_model` plus `service_tier`.

Observed usage on the preflight: 1,242 input tokens, 30 output tokens, 0 reasoning tokens
for the trivial task. Note reasoning-token count varies sharply with task difficulty — an
earlier trivial call returned 743 — so output-token budgets for real review must not be
extrapolated from the preflight.

### Context capacity blocker — BLOCKS EXECUTION

Measured with `tiktoken` `o200k_base` against the actual staged inputs:

| Category | Files | Tokens | Share |
|---|---:|---:|---:|
| `telemetry.csv` (raw 200 Hz) | 40 | 2,079,029 | 57.4% |
| `truth.csv` (raw) | 40 | 1,433,605 | 39.6% |
| `raw_evidence.json` | 40 | 58,988 | 1.6% |
| `evidence/*.json` | 40 | 18,932 | 0.5% |
| other JSON | 4 | 16,834 | 0.5% |
| markdown docs | 5 | 13,134 | 0.4% |
| `run_meta.json` | 40 | 1,300 | 0.0% |
| **TOTAL frozen source** | **209** | **3,621,822** | |
| *excluding raw telemetry/truth CSV* | 169 | *109,188* | |

**The frozen source set is 3,621,822 tokens against a 922,000 max input — 3.93× over.
V0-CLEAN, V2-CLEAN and V2-SEEDED stage-1, and stage-2 of every condition, cannot be
submitted as staged.** 97.0% of the load is per-sample raw telemetry: 40 runs × 2,002 rows
× two CSVs.

This is **not** a staging defect. `stage_runs.py` faithfully implements §2 of the frozen
preregistration, which names *"committed M4 evidence under
`campaign/results/m4-franka-filtered-vs-unfiltered-v1/`"* — and that directory contains the
raw per-sample CSVs.

**Resolving it requires an owner decision, because every option touches the frozen
preregistration and none may be taken unilaterally:**

1. **Narrow the frozen source set** to documents, manifests, run metadata and evidence
   JSON, excluding raw per-sample CSVs (109,188 tokens — fits comfortably, standard
   pricing). This is a preregistration change and therefore **VRTV-02**, not a VRTV-01 edit.
2. **Summarise or downsample** the telemetry before staging. This inserts a derived
   representation into what is supposed to be the authoritative source — which would
   quietly make the baseline condition a *representation* condition and defeat the
   experiment's purpose.
3. **Keep the source set and change the protocol** to allow source-on-demand retrieval.
   That is a different experiment; it also reintroduces a reviewer tool, violating §5b
   Class 1.

Option 1 is the least damaging and the most honest, but it is still a design change and it
belongs to VRTV-02 under the freeze rule. **No option is taken here.**

### Cost estimate — measured tokens, official pricing

Pricing (developers.openai.com/api/docs/pricing): input **$5.00**/M, cached input
**$0.50**/M, output **$30.00**/M. Long context (>272K input): input **$10.00**/M, output
**$45.00**/M applied to the full request.

Image tokens estimated at ~10,000 for the four-view packet, scaled from the measured
preflight anchor (1600×600 ≈ 1,190 tokens). Estimate only — the views were deliberately
**not** sent to the model for measurement.

Under Option 1 (source = 109,188 tokens, all requests below the long-context threshold):

| Run | stage-1 in | stage-2 in | cost @8k out | cost @25k out |
|---|---:|---:|---:|---:|
| V0-CLEAN | 109,588 | 113,588 | $1.60 | $2.62 |
| V1-CLEAN | 10,400 | 113,588 | $1.10 | $2.12 |
| V1-SEEDED | 10,400 | 113,588 | $1.10 | $2.12 |
| V2-CLEAN | 119,588 | 113,588 | $1.65 | $2.67 |
| V2-SEEDED | 119,588 | 113,588 | $1.65 | $2.67 |
| **TOTAL** | | | **$7.09** | **$12.19** |

**Conservative upper bound: ~$15**, allowing for reasoning-token variance at effort `high`,
one voided run requiring a rerun, and image-token estimation error.

As staged (Option 0), a single V0 request would carry 3,621,822 input tokens — impossible
against the 922,000 cap, and ~$36.22 of input alone per request if it were possible.

**A $5 balance is not sufficient** even under the cheapest viable option. V3 is billed
separately by Anthropic and is not included above.

**Current API balance: NOT AVAILABLE.** The project key lacks the `api.usage.read` scope,
and `/dashboard/billing/*` requires a browser session key. Not inferred.

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
