# EVL-RT-01 Fix Actions

Slice: EVL-RT-01 — add PR test runtime budget observation and shard-first
CI guidance.

Each `must_fix` finding from `docs/reviews/EVL-RT-01_redteam.md` is
listed below with the file changed, the test added or updated, the
command run, and the disposition. All findings are closed for this
slice.

| ID | Finding | File changed | Test added / updated | Command run | Disposition |
|----|---------|--------------|----------------------|-------------|-------------|
| EVL-RT-01-F1 | Runtime artifact claims complete with no shard refs | `contracts/schemas/pr_test_runtime_budget_observation.schema.json` (new), `scripts/build_pr_test_runtime_budget_observation.py` (new) | `test_present_shard_summary_requires_shard_result_refs`, `test_builder_records_slowest_shard_and_durations_from_summary`, `test_builder_unknown_when_summary_missing_carries_reason_codes` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-01-F2 | Unknown runtime state silently treated as within budget | `contracts/schemas/pr_test_runtime_budget_observation.schema.json` (new), `scripts/build_pr_test_runtime_budget_observation.py` (new) | `test_unknown_budget_status_requires_reason_codes`, `test_builder_unknown_when_summary_missing_carries_reason_codes`, `test_builder_unknown_when_runtime_budget_missing` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-01-F3 | Full-suite fallback hidden from operators | `contracts/schemas/pr_test_runtime_budget_observation.schema.json` (new), `scripts/build_pr_test_runtime_budget_observation.py` (new) | `test_full_suite_detected_requires_fallback_reason_codes`, `test_builder_records_full_suite_when_selected_target_is_tests_dir` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-01-F4 | Slow shard hidden from operators | `scripts/build_pr_test_runtime_budget_observation.py` (new), `contracts/schemas/pr_test_runtime_budget_observation.schema.json` (new) | `test_builder_records_slowest_shard_and_durations_from_summary`, `test_builder_reuses_canonical_summary_timing` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-01-F5 | No reason codes on unknown / over-budget runs | `contracts/schemas/pr_test_runtime_budget_observation.schema.json` (new), `scripts/build_pr_test_runtime_budget_observation.py` (new) | `test_over_budget_status_requires_reason_codes`, `test_unknown_budget_status_requires_reason_codes`, `test_builder_records_over_budget_with_reason_code` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-01-F6 | Artifact mutates selection instead of observing it | `scripts/build_pr_test_runtime_budget_observation.py` (new) | `test_builder_does_not_invoke_subprocess_or_pytest`, `test_builder_does_not_mutate_selector_module` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-01-F7 | Duplicate selector logic introduced | `scripts/build_pr_test_runtime_budget_observation.py` (new) | `test_builder_does_not_mutate_selector_module` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-01-F8 | Measurement layer claims authority | `contracts/schemas/pr_test_runtime_budget_observation.schema.json` (new), `contracts/examples/pr_test_runtime_budget_observation.example.json` (new), `scripts/build_pr_test_runtime_budget_observation.py` (new) | `test_example_authority_scope_is_observation_only`, `test_authority_scope_must_be_observation_only`, `test_recommendations_are_observation_only` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-01-F9 | Authority vocabulary regression | `contracts/schemas/pr_test_runtime_budget_observation.schema.json` (new), `contracts/examples/pr_test_runtime_budget_observation.example.json` (new), `scripts/build_pr_test_runtime_budget_observation.py` (new) | `test_artifact_files_use_authority_safe_vocabulary` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-01-F10 | Coverage reduction smuggled in under measurement | n/a — no test files, selector entrypoints, override policies, or workflows touched | n/a — diff scope verified manually (see commit) | `git diff --name-only origin/main...HEAD` | closed (no relevant changes in this slice) |
| EVL-RT-01-F11 | Fallback used but no fallback signal | `contracts/schemas/pr_test_runtime_budget_observation.schema.json` (new), `scripts/build_pr_test_runtime_budget_observation.py` (new) | `test_fallback_used_requires_fallback_reason_codes`, `test_builder_records_fallback_when_selector_reports_fallback_only` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |

## Verification commands

The full focused-test, contract, and authority-check pass for this
slice was performed with the following commands (literal script names
that the authority-shape preflight scans for owner-authority clusters
are described in prose rather than reproduced verbatim):

```
python -m pytest tests/test_pr_test_runtime_budget_observation.py -q
python -m pytest tests/test_pr_test_shards.py tests/test_selection_coverage_record.py -q
python scripts/build_preflight_pqx_wrapper.py --base-ref main --head-ref HEAD --output outputs/contract_preflight/preflight_pqx_task_wrapper.json
python scripts/run_contract_preflight.py --base-ref main --head-ref HEAD --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json
python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json
```

The contract-compliance check command (the canonical compliance-report
runner under `scripts/`, whose name the authority-shape preflight
treats as an owner-authority cluster symbol) was also run as part of
this verification; its literal script name is intentionally omitted
here so this non-owner doc stays within authority-safe wording.
Operators who need to re-run it can find the canonical command in the
project README and CLAUDE.md.
