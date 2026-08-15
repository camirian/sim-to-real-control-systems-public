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

No condition may start until this table is filled in and committed.

| Field | Value |
|---|---|
| Reviewer provider | `TO BE RECORDED BEFORE V0-CLEAN` |
| Reviewer model + exact version string | `TO BE RECORDED BEFORE V0-CLEAN` |
| Reviewer configuration (temperature / effort / tools / limits) | `TO BE RECORDED BEFORE V0-CLEAN` |
| Multimodal image input confirmed | `TO BE RECORDED BEFORE V0-CLEAN` |
| Frozen-source context capacity confirmed | `TO BE RECORDED BEFORE V0-CLEAN` |
| Repository/filesystem access denied | `TO BE RECORDED BEFORE V0-CLEAN` |
| Reviewer tool/data network access denied (§5b Class 1) | `TO BE RECORDED BEFORE V0-CLEAN` |
| Reviewer tools registered (must be none that fetch/search/execute) | `TO BE RECORDED BEFORE V0-CLEAN` |
| Model transport route (§5b Class 2: provider API / local model) | `TO BE RECORDED BEFORE V0-CLEAN` |
| Transport identical across all five treatment sessions | `TO BE RECORDED BEFORE V0-CLEAN` |
| Five-session pin availability confirmed | `TO BE RECORDED BEFORE V0-CLEAN` |
| V3 provider | `TO BE RECORDED BEFORE V3` |
| V3 model + exact version string | `TO BE RECORDED BEFORE V3` |
| Selection rationale | `TO BE RECORDED BEFORE V0-CLEAN` |
| Selected by | `TO BE RECORDED BEFORE V0-CLEAN` |
| Date/time of selection | `TO BE RECORDED BEFORE V0-CLEAN` |

Selecting the model **after** seeing any condition's output is a post-hoc tuning route and
is forbidden by the preregistration freeze.

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
