# SMALL-BATCH-RISK-01 Fix Actions

This file records the disposition of every red-team finding from
`docs/reviews/SMALL-BATCH-RISK-01_redteam.md`. SMALL-BATCH-RISK-01 is
observation-only; canonical authority for admission, execution
closure, eval evidence, policy/scope, continuation/closure, and
final-gate signal remains with the systems declared in
`docs/architecture/system_registry.md`.

| Finding | Disposition | File(s) changed | Test added/updated | Command run |
|---|---|---|---|---|
| MF-01 risk artifact treated as a gate | resolved | `contracts/schemas/small_batch_risk_record.schema.json` (`authority_scope` const, no block fields); `scripts/run_agent_pr_precheck.py` (AEX adds artifact ref but does not flip status) | `test_artifact_does_not_carry_block_or_gate_fields`, `test_apr_does_not_block_on_risk_level`, `test_schema_authority_scope_is_const_observation_only` | `pytest tests/test_small_batch_risk_record.py -q` |
| MF-02 generated artifacts inflate risk without separation | resolved | `contracts/schemas/small_batch_risk_record.schema.json` (`generated_artifact_touch_count`, `generated_surface_touched`); `scripts/build_small_batch_risk_record.py` (`recommended_batches` separates generated_artifacts) | `test_generated_artifacts_touched_records_count`, `test_high_risk_emits_recommended_batches`, `test_very_high_risk_emits_recommended_batches` | `pytest tests/test_small_batch_risk_record.py -q` |
| MF-03 schema/runtime/workflow/docs/test mix not flagged | resolved | `scripts/build_small_batch_risk_record.py` (`_compute_risk_level` flags `>=5` classes and the schema+runtime+generated+workflow combination) | `test_five_or_more_surface_classes_yields_very_high`, `test_schema_runtime_generated_workflow_combination_is_very_high` | `pytest tests/test_small_batch_risk_record.py -q` |
| MF-04 unknown path treated as low | resolved | `scripts/build_small_batch_risk_record.py` (`_classify_all` records `classification_failed`; `_compute_risk_level` forces `unknown` and emits `path_classification_failed`); schema requires reason_codes for `risk_level=unknown` via `allOf` | `test_unknown_path_classification_yields_unknown_with_reason_codes` | `pytest tests/test_small_batch_risk_record.py -q` |
| MF-05 recommended split lacks evidence | resolved | `contracts/schemas/small_batch_risk_record.schema.json` (`recommended_batches` requires `paths`, `split_findings` requires `evidence_paths`, both carry `observation_only=true` const) | `test_high_risk_emits_recommended_batches`, `test_very_high_risk_emits_recommended_batches` | `pytest tests/test_small_batch_risk_record.py -q` |
| MF-06 dashboard surface ignored | resolved | `scripts/build_small_batch_risk_record.py` (`classify_surface` checks dashboard prefixes before generated artifacts); schema requires `dashboard_surface_touched`, `dashboard_touch_count` | `test_dashboard_touched_sets_flag`, `test_classify_surface_dashboard_priority_over_generated` | `pytest tests/test_small_batch_risk_record.py -q` |
| MF-07 PR body prose substitutes for artifact | resolved | `scripts/build_small_batch_risk_record.py` writes the canonical artifact file; `scripts/run_agent_pr_precheck.py` adds the artifact ref only when the on-disk file is present | `test_apr_aex_emits_small_batch_risk_record_on_disk`, `test_builder_script_writes_validated_record` | `pytest tests/test_small_batch_risk_record.py -q` |
| MF-08 authority vocabulary leak | resolved | schema/example/builder/test all lint-clean for the reserved authority verb cluster | `test_schema_does_not_contain_reserved_authority_tokens`, `test_example_does_not_contain_reserved_authority_tokens`, `test_builder_does_not_contain_reserved_authority_tokens`, `test_test_file_does_not_contain_reserved_authority_tokens_outside_lint_list` | `pytest tests/test_small_batch_risk_record.py -q` |
| MF-09 schema/example mismatch | resolved | example validated against schema under test | `test_example_validates_against_schema`, `test_example_required_fields_present` | `pytest tests/test_small_batch_risk_record.py -q` |
| MF-10 APR integration writes outside outputs/ | resolved | `scripts/run_agent_pr_precheck.py` (`_write_small_batch_risk_record` writes only to `outputs/small_batch_risk/`; `try/except` so a builder failure simply omits the artifact ref) | exercised by `test_apr_aex_emits_small_batch_risk_record_on_disk` | `pytest tests/test_small_batch_risk_record.py -q` |

No `must_fix` finding is left unresolved. The `should_fix` SF-01
follow-up (pin risk-level thresholds to a governance policy file) is
recorded as an explicit next slice and does not block
SMALL-BATCH-RISK-01.

The `OBS-*` items are intentional design choices for this slice and
are documented in the red-team doc rather than as fix actions.
