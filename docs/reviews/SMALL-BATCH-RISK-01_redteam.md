# SMALL-BATCH-RISK-01 Red-Team Review — Governed PR Surface Risk Measurement

Categories: `must_fix` (blocks the PR), `should_fix` (open follow-up before
the next dependent slice), `observation` (informational).

SMALL-BATCH-RISK-01 is observation-only. It surfaces a measurement of
governed PR surface breadth and a recommended-batch observation only.
Canonical authority for admission, execution closure, eval evidence,
policy/scope, continuation/closure, and final-gate signal remains with
the systems declared in `docs/architecture/system_registry.md`. Each
finding below names the risk that the artifact pretends to claim
authority it does not have, and the mitigation that keeps the artifact
inside its observation envelope.

## Findings

### MF-01 — risk artifact treated as a gate
- **Risk:** APR or a downstream consumer could read `risk_level=high`
  / `risk_level=very_high` and flip a PR-ready signal to `not_ready`.
- **Mitigation:** the schema's `authority_scope` is fixed to
  `const = "observation_only"` and the artifact carries no
  `block` / `gate_status` / `pr_ready_status` /
  `pr_update_ready_status` fields. APR's AEX phase only adds the
  artifact ref to `output_artifact_refs`; the AEX `status` is still
  determined by the canonical required-surface mapping check.
- **Test:** `test_artifact_does_not_carry_block_or_gate_fields`,
  `test_apr_does_not_block_on_risk_level`,
  `test_schema_authority_scope_is_const_observation_only`.
- **Disposition:** resolved.

### MF-02 — generated artifacts inflate risk without being separated in findings
- **Risk:** a PR that touches a single generated artifact (e.g.,
  `artifacts/tls/...`) plus one runtime change could mask the
  generated touch in the high-level risk count.
- **Mitigation:** the schema requires
  `generated_artifact_touch_count` and `generated_surface_touched` as
  top-level fields; the builder emits both deterministically. The
  `recommended_batches` block separates `generated_artifacts` into its
  own batch when risk is `high` or `very_high`.
- **Test:** `test_generated_artifacts_touched_records_count`,
  `test_high_risk_emits_recommended_batches`,
  `test_very_high_risk_emits_recommended_batches`.
- **Disposition:** resolved.

### MF-03 — schema/runtime/workflow/docs/test mix not flagged
- **Risk:** the canonical recurring failure case from PR 1319 (broad,
  multi-surface PRs) is not captured by a simple distinct-class count.
- **Mitigation:** the builder applies two thresholds: distinct surface
  classes >=5 OR the schema + runtime + generated + workflow
  combination, both of which produce `risk_level=very_high` and a
  named `reason_code`
  (`many_governed_surface_classes`,
  `schema_runtime_generated_workflow_combination`).
- **Test:**
  `test_five_or_more_surface_classes_yields_very_high`,
  `test_schema_runtime_generated_workflow_combination_is_very_high`.
- **Disposition:** resolved.

### MF-04 — unknown path treated as low
- **Risk:** if the classifier ever returns a class outside the schema
  enum, the builder could fall back to "low" silently.
- **Mitigation:** `_classify_all` records a
  `classification_failed=True` flag whenever the classifier returns a
  class name that is not in `SURFACE_CLASSES`. `_compute_risk_level`
  then forces `risk_level="unknown"` and emits
  `path_classification_failed`. The schema requires reason_codes for
  `risk_level=unknown` via `allOf`. `split_recommendation` is
  forced to `human_review_required`.
- **Test:**
  `test_unknown_path_classification_yields_unknown_with_reason_codes`.
- **Disposition:** resolved.

### MF-05 — recommended split lacks evidence
- **Risk:** `recommended_batches` could be emitted without listing the
  changed paths that drove the recommendation.
- **Mitigation:** every `recommended_batches` entry has
  `paths` (non-empty array) and the schema requires it. Every
  `split_findings` entry has `evidence_paths`. Both carry
  `observation_only=true` (`const`). Tests verify both for high and
  very_high risk levels.
- **Test:** `test_high_risk_emits_recommended_batches`,
  `test_very_high_risk_emits_recommended_batches`.
- **Disposition:** resolved.

### MF-06 — dashboard surface ignored
- **Risk:** dashboard changes (apps/dashboard-3ls/, artifacts/dashboard_*)
  could be silently classified as generated artifacts because of the
  `artifacts/` prefix.
- **Mitigation:** `classify_surface` checks dashboard prefixes
  (`apps/dashboard-3ls/`, `artifacts/dashboard_metrics/`,
  `artifacts/dashboard_cases/`, `dashboard/`) before the generated
  artifact prefixes. The schema requires
  `dashboard_surface_touched` and `dashboard_touch_count`.
- **Test:** `test_dashboard_touched_sets_flag`,
  `test_classify_surface_dashboard_priority_over_generated`.
- **Disposition:** resolved.

### MF-07 — PR body prose substitutes for artifact
- **Risk:** an agent could include a "split recommendation" string in
  the PR body and skip generating the artifact.
- **Mitigation:** the schema requires the artifact JSON file with the
  full set of required fields; APR adds the artifact ref to
  `output_artifact_refs` only when the file is present on disk. The
  builder writes `outputs/small_batch_risk/small_batch_risk_record.json`
  via the canonical builder; PR bodies can reference the artifact ref
  but cannot stand in for it.
- **Test:** `test_apr_aex_emits_small_batch_risk_record_on_disk`,
  `test_builder_script_writes_validated_record`.
- **Disposition:** resolved.

### MF-08 — authority vocabulary leak
- **Risk:** the schema, example, builder, or test could carry the
  reserved authority verb cluster forbidden by the contract
  vocabulary policy (the cluster terms listed in the test's lint
  constant). Risk record must remain measurement-only; readiness
  observations and canonical authority remain with the current owner
  systems.
- **Mitigation:** lint tests assert that none of those tokens appear
  in the schema, example, builder, or test (outside of the lint
  constant itself).
- **Test:** `test_schema_does_not_contain_reserved_authority_tokens`,
  `test_example_does_not_contain_reserved_authority_tokens`,
  `test_builder_does_not_contain_reserved_authority_tokens`,
  `test_test_file_does_not_contain_reserved_authority_tokens_outside_lint_list`.
- **Disposition:** resolved.

### MF-09 — schema/example mismatch
- **Risk:** the canonical example could drift from the schema and pass
  CI because no test validates it.
- **Mitigation:** `test_example_validates_against_schema` calls
  `validate_artifact` against the canonical example on every test run.
- **Test:** `test_example_validates_against_schema`,
  `test_example_required_fields_present`.
- **Disposition:** resolved.

### MF-10 — APR integration writes outside outputs/
- **Risk:** the APR-side helper could be tempted to mutate
  contracts/, scripts/, spectrum_systems/, or docs/ when writing the
  artifact.
- **Mitigation:** `_write_small_batch_risk_record` writes only to
  `outputs/small_batch_risk/small_batch_risk_record.json`. The helper
  does not touch any other path. The artifact is observation-only and
  never blocks AEX (the helper is wrapped in a `try/except` so a
  builder failure simply omits the artifact ref).
- **Test:** the AEX wrapper is exercised by
  `test_apr_aex_emits_small_batch_risk_record_on_disk` and the
  builder is fully under `scripts/`. APR-owned files are unchanged
  outside the AEX integration block.
- **Disposition:** resolved.

### SF-01 — `should_fix`: pin risk-level thresholds to a policy file
- **Risk:** the thresholds (`distinct_count >= 5`, schema+runtime+
  generated+workflow combination) are baked into the builder. A
  future tuning step would need a code change rather than a policy
  update.
- **Suggested next slice:** add a governance policy file that
  declares the threshold table and have the builder read it. Out of
  scope for this slice (policy mapping and policy-test coverage are a
  separate change).

### OBS-01 — risk artifact is not yet referenced from APR's
top-level result
- **Observation:** the AEX phase adds the artifact ref to
  `output_artifact_refs` but the APR top-level result does not
  surface a dedicated `small_batch_risk_artifact_ref` field. This is
  intentional for the small-batch slice — APR continues to operate on
  observation-only inputs and the artifact ref is discoverable via
  the AEX phase output. A follow-up slice can add a top-level field.

### OBS-02 — risk artifact does not yet feed M3L / APU
- **Observation:** M3L and APU do not currently consume the
  small_batch_risk_record. This is intentional: the artifact is
  measurement-only, and M3L / APU continue to consume their canonical
  inputs unchanged.
