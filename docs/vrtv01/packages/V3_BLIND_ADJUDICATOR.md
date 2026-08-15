# Package V3 — BLIND ADJUDICATOR

Read `00_COMMON.md`. Run in a fresh session, by an operator who did **not** author the views and did **not** run V0/V1/V2.

## Allowed inputs
- The normalized, blinded finding set (`normalized_findings.json`, schema below).
- The frozen source set, in full.

## Forbidden information
- Which condition produced any finding.
- How many conditions exist, or their names.
- The seeded-defect answer key (`docs/vrtv01/SEEDED_ANSWER_KEY.OPERATOR_ONLY.md`) and the View C pre-disclosure list. **The human operator holds these and applies them after V3 returns.** V3 must not know that seeding exists at all, nor how many defects were planted.
- Note: §3.3 of the frozen preregistration says this list is held "by the adjudicator only." That means the *human operator performing adjudication*, not the V3 model session. See the superseding note in the answer key.
- Any reviewer's confidence score, rationale, or self-verdict from stage 2.

## Prompt — verbatim

```text
You are an independent adjudicator. Below is a randomized list of candidate findings about a completed simulation campaign, produced by reviewers whose identity and method you do not know.

For each finding, consult the committed source and decide:

verdict:
  SUPPORTED   - the committed source confirms it
  REFUTED     - the committed source contradicts it
  UNRESOLVED  - the committed evidence is insufficient to decide
  NOT_CHECKABLE_FROM_AVAILABLE_EVIDENCE - answering would require artifacts not in the repository

Then classify the failure mode:

  SOURCE_DEFECT         - the committed source really has this problem
  REPRESENTATION_DEFECT - the source is correct; a supplied view misstates it
  REVIEWER_ERROR        - neither source nor any view supports this
  NOT_APPLICABLE        - the finding is SUPPORTED

For REPRESENTATION_DEFECT, name the specific view and element that is wrong.

Prefer deterministic evidence over judgment. Cite the exact path and field for every verdict. Do not infer a stronger claim than the artifact supports. Do not rank, group, or comment on which findings seem to share an origin.
```

## Blinding and randomization procedure — operator steps

1. Pool every stage-1 candidate from **all five reviewer runs** — `V0-CLEAN`, `V1-CLEAN`, `V1-SEEDED`, `V2-CLEAN`, `V2-SEEDED`. **Do not use stage-2 self-verdicts.** Seeded-run findings enter the same blinded pool so that V3 cannot infer packet type from what it is asked to judge.
2. Replace each `local_id` with a fresh opaque `finding_id` (e.g. `f_001`…). Keep the mapping in a file V3 never sees.
3. Strip `reviewer_confidence`, `derived_from`, `rationale`, and every phrase naming a view ("as shown in the diagram", "View B indicates"). Rewrite such phrasing to a neutral assertion of the same claim. **Record every rewrite** — over-aggressive normalization can destroy a finding's meaning, and the rewrite log is auditable.
4. Deduplicate **only exact semantic duplicates**. Preserve disagreements and near-misses; near-duplicates across conditions are signal, not noise.
5. Shuffle with a recorded seed. Emit `normalized_findings.json`.
6. After V3 returns, rejoin verdicts to conditions via the mapping and apply the §3.2 pre-disclosure and §3.3 seeded exclusions.

## Normalized finding schema

```json
{
  "finding_id": "f_001",
  "claim": "neutral one-sentence assertion",
  "severity_if_true": "CRITICAL | MAJOR | MINOR | NOTE",
  "requested_source_check": "exact path/field"
}
```

## Result schema

```json
{
  "finding_id": "f_001",
  "verdict": "SUPPORTED | REFUTED | UNRESOLVED | NOT_CHECKABLE_FROM_AVAILABLE_EVIDENCE",
  "failure_mode": "SOURCE_DEFECT | REPRESENTATION_DEFECT | REVIEWER_ERROR | NOT_APPLICABLE",
  "offending_view": "VIEW_A | VIEW_B | VIEW_C | VIEW_D | null",
  "evidence_path": "exact file and field",
  "reasoning": "string"
}
```

## Experiment result record (assembled by the operator, after rejoin)

```json
{
  "preregistration_sha": "0369dab5b83cedcc92847088ba939de092c295c0",
  "current_execution_package_head": "string",
  "source_baseline_sha": "f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29",
  "clean_view_hashes_verified": true,
  "seeded_view_hashes_verified": true,
  "reviewer_provider": "string",
  "reviewer_model_version": "string",
  "reviewer_config": "string",
  "v3_provider": "string",
  "v3_model_version": "string",
  "model_control_rule_upheld": true,
  "randomization_seed": "string",
  "per_condition": {
    "<V0|V1|V2>": {
      "valid_findings": 0,
      "novel_valid_findings_vs_v0": 0,
      "pre_disclosed_excluded": 0,
      "false_positives": 0,
      "unresolved": 0,
      "not_checkable": 0,
      "representation_defects_attributed": 0,
      "reviewer_errors": 0,
      "seeded_defects_caught": 0,
      "seeded_defects_planted": 0,
      "traceability_rate": 0.0,
      "claim_boundary_errors": 0,
      "time_to_first_valid_finding_s": 0,
      "stage1_duration_s": 0,
      "stage2_duration_s": 0,
      "tokens_or_cost": null,
      "model_provider_version": "string",
      "packet": "clean | seeded",
      "counts_toward_primary_comparison": true
    }
  },
  "human_comprehension": {
    "status": "RUN | INDICATIVE_ONLY | NOT_RUN",
    "readers_per_arm": 0,
    "q5_claim_inflation_regression": false
  },
  "void_runs": [],
  "decision": "PROMOTE_FOR_SECOND_DOGFOOD | PUBLIC_COMMS_ONLY | REVISE_AND_REPEAT | STOP_NO_LIFT",
  "decision_rationale": "string"
}
```

## Decision rule
As specified in §7 of `docs/VISUAL_ROUND_TRIP_EXPERIMENT_01.md`. The operator applies it mechanically. If the outcome is ambiguous under the rule, record `REVISE_AND_REPEAT` and name the specific ambiguity — do not choose the more favorable reading.
