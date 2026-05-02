# EVL-RT-02 Fix Actions

Slice: EVL-RT-02 — extend the observation-only
`pr_test_runtime_budget_observation` artifact with a
`fallback_justification` section that records why broad / full-suite /
shard fallback was used and what mapping/sharding improvements should
be considered.

Each `must_fix` finding from `docs/reviews/EVL-RT-02_redteam.md` is
listed below with the file changed, the test added or updated, the
command run, and the disposition. All findings are closed for this
slice.

| ID | Finding | File changed | Test added / updated | Command run | Disposition |
|----|---------|--------------|----------------------|-------------|-------------|
| EVL-RT-02-F1 | Fallback used with no reason codes | `contracts/schemas/pr_test_runtime_budget_observation.schema.json`, `scripts/build_pr_test_runtime_budget_observation.py` | `test_fallback_justification_fallback_used_true_requires_reason_codes`, `test_builder_classifies_full_suite_scope_with_evidence_refs`, `test_builder_classifies_broad_pytest_scope_for_select_all_tests` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-02-F2 | Full-suite detected but hidden | `contracts/schemas/pr_test_runtime_budget_observation.schema.json`, `scripts/build_pr_test_runtime_budget_observation.py` | `test_fallback_justification_full_suite_detected_requires_reason_codes`, `test_fallback_justification_full_suite_present_requires_evidence_ref`, `test_builder_emits_recommended_shard_candidates_for_full_suite_scope` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-02-F3 | Unknown fallback state treated as clean | `contracts/schemas/pr_test_runtime_budget_observation.schema.json`, `scripts/build_pr_test_runtime_budget_observation.py` | `test_fallback_justification_unknown_scope_requires_reason_codes`, `test_builder_classifies_unknown_scope_when_inputs_missing` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-02-F4 | Missing selection refs counted present | `contracts/schemas/pr_test_runtime_budget_observation.schema.json`, `scripts/build_pr_test_runtime_budget_observation.py` | `test_fallback_justification_present_fallback_requires_evidence_ref`, `test_fallback_justification_full_suite_present_requires_evidence_ref` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-02-F5 | Fallback justification mutates test selection | `scripts/build_pr_test_runtime_budget_observation.py` | `test_fallback_justification_does_not_mutate_selection_or_run_pytest`, `test_builder_surfaces_recommended_mapping_candidates_observation_only`, `test_fallback_justification_authority_scope_preserved` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-02-F6 | Builder runs pytest | `scripts/build_pr_test_runtime_budget_observation.py` | `test_builder_does_not_invoke_subprocess_or_pytest`, `test_fallback_justification_does_not_mutate_selection_or_run_pytest` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-02-F7 | Duplicate selector logic introduced | `scripts/build_pr_test_runtime_budget_observation.py` | `test_builder_does_not_mutate_selector_module`, `test_fallback_justification_does_not_mutate_selection_or_run_pytest` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-02-F8 | Measurement layer claims authority | `contracts/schemas/pr_test_runtime_budget_observation.schema.json`, `contracts/examples/pr_test_runtime_budget_observation.example.json`, `scripts/build_pr_test_runtime_budget_observation.py` | `test_fallback_justification_authority_scope_preserved`, `test_fallback_justification_section_required_in_schema`, `test_authority_scope_must_be_observation_only` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-02-F9 | Authority vocabulary regression | `contracts/schemas/pr_test_runtime_budget_observation.schema.json`, `contracts/examples/pr_test_runtime_budget_observation.example.json`, `scripts/build_pr_test_runtime_budget_observation.py` | `test_artifact_files_use_authority_safe_vocabulary` | `python -m pytest tests/test_pr_test_runtime_budget_observation.py -q` | closed |
| EVL-RT-02-F10 | Coverage reduction smuggled in under fallback justification | n/a — no test files, selector entrypoints, override policies (other than additive doc->test mappings), or workflows touched | n/a — diff scope verified manually (see commit) | `git diff --name-only origin/main...HEAD` | closed (no relevant changes in this slice) |

## Verification commands

The full focused-test, contract, and authority-check pass for this
slice was performed with the following commands (literal script names
that the authority-shape preflight scans for owner-authority clusters
are described in prose rather than reproduced verbatim):

```
python -m pytest tests/test_pr_test_runtime_budget_observation.py tests/test_selection_coverage_record.py tests/test_pr_test_shards.py -q
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
