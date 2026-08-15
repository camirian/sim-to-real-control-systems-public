# VRTV-01 execution control plane

Downstream of the frozen preregistration. **Nothing here edits `0369dab`.** These are
execution artifacts and controls; the experimental design they serve is fixed.

## 1. Identity model — three distinct SHAs

These are routinely conflated. They are not interchangeable and must be recorded separately.

| Identity | SHA | What it is |
|---|---|---|
| `SOURCE_BASELINE_SHA` | `f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29` | `main` at the time VRTV-01 opened. The frozen source set every condition reasons from. |
| `PREREGISTRATION_SHA` | `0369dab5b83cedcc92847088ba939de092c295c0` | The commit that froze the experimental design in `docs/VISUAL_ROUND_TRIP_EXPERIMENT_01.md`. **This is the preregistration. It is not superseded by later commits on this branch.** |
| `CURRENT_EXECUTION_PACKAGE_HEAD` | see issue #17 | The PR head carrying execution artifacts (packages, seeded controls, this file). Advances as control-plane work lands. **Never cite this as the preregistration SHA.** |

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
  permissions).

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
- no need for repository access: each session can run from its staged input directory
  with repository and network access denied.

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
| Network access denied | `TO BE RECORDED BEFORE V0-CLEAN` |
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

## 6. Required fail-closed staging and launch boundary

The repository is an operator workspace, not a reviewer sandbox. A reviewer must never
be launched from the repository, a repository worktree, or a directory whose mounted
filesystem includes the repository. Reviewer conditions must run from a separate,
permission-restricted staging root outside the repository, with no `.git`, remote,
symlink, parent traversal path to the repository, answer key, package, preregistration,
or Mermaid source. Disable network and mount only the run's input directory plus a
separate output location.

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
environment with repository and network access denied. A working directory alone is
not an isolation boundary.
