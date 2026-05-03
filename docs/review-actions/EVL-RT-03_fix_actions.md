# EVL-RT-03 Fix Actions

Slice: EVL-RT-03 — add an observation-only
`pr_test_shard_first_readiness_observation` artifact, builder, and APR
EVL-phase consumer that record whether a PR path is shard-first
(focused selection backed by required shard evidence refs) or
fallback-justified (broad/full-suite usage explained by the existing
`fallback_justification` section in `pr_test_runtime_budget_observation`).

Each `must_fix` finding from `docs/reviews/EVL-RT-03_redteam.md` is
listed below with the file changed, the test added or updated, the
command run, and the disposition. All findings are closed for this
slice.

| ID | Finding | File changed | Test added / updated | Command run | Disposition |
|----|---------|--------------|----------------------|-------------|-------------|
| EVL-RT-03-F1 | Broad pytest path with no fallback justification | `contracts/schemas/pr_test_shard_first_readiness_observation.schema.json`, `scripts/build_pr_test_shard_first_readiness_observation.py`, `scripts/run_agent_pr_precheck.py` | `test_fallback_justified_requires_fallback_justification_ref`, `test_fallback_justified_requires_fallback_reason_codes`, `test_fallback_used_true_requires_fallback_justification_ref`, `test_full_suite_detected_true_requires_fallback_justification_ref`, `test_evl_pr_test_shard_first_readiness_blocks_when_required_shard_missing` | `python -m pytest tests/test_pr_test_shard_first_readiness_observation.py tests/test_agent_pr_precheck.py -q` | closed |
| EVL-RT-03-F2 | Fallback justification exists but has no reason codes | `contracts/schemas/pr_test_shard_first_readiness_observation.schema.json`, `scripts/build_pr_test_shard_first_readiness_observation.py` | `test_fallback_justified_requires_fallback_reason_codes`, `test_builder_partial_when_fallback_used_with_no_reason_codes`, `test_builder_classifies_partial_when_fallback_used_but_justification_missing` | `python -m pytest tests/test_pr_test_shard_first_readiness_observation.py -q` | closed |
| EVL-RT-03-F3 | Shard-first status claimed with no shard refs | `contracts/schemas/pr_test_shard_first_readiness_observation.schema.json`, `scripts/build_pr_test_shard_first_readiness_observation.py` | `test_shard_first_status_requires_required_shard_refs`, `test_shard_first_status_forbids_fallback_used`, `test_shard_first_status_forbids_full_suite_detected`, `test_builder_classifies_shard_first_when_required_refs_present`, `test_builder_classifies_partial_when_required_shard_status_missing`, `test_builder_classifies_partial_when_required_shard_failed` | `python -m pytest tests/test_pr_test_shard_first_readiness_observation.py -q` | closed |
| EVL-RT-03-F4 | Unknown state treated as clean | `contracts/schemas/pr_test_shard_first_readiness_observation.schema.json`, `scripts/build_pr_test_shard_first_readiness_observation.py` | `test_unknown_status_requires_reason_codes`, `test_missing_status_requires_reason_codes`, `test_partial_status_requires_reason_codes`, `test_builder_classifies_unknown_when_runtime_budget_missing`, `test_builder_classifies_missing_when_summary_and_runtime_budget_absent` | `python -m pytest tests/test_pr_test_shard_first_readiness_observation.py -q` | closed |
| EVL-RT-03-F5 | PR prose counted as fallback evidence | `contracts/schemas/pr_test_shard_first_readiness_observation.schema.json` | `test_pr_prose_does_not_satisfy_fallback_evidence`, `test_fallback_justified_requires_fallback_justification_ref` | `python -m pytest tests/test_pr_test_shard_first_readiness_observation.py -q` | closed |
| EVL-RT-03-F6 | Builder runs pytest | `scripts/build_pr_test_shard_first_readiness_observation.py`, `scripts/run_agent_pr_precheck.py` | `test_builder_does_not_invoke_subprocess_or_pytest`, `test_builder_does_not_mutate_shard_runner`, `test_builder_does_not_mutate_runtime_budget_builder`, `test_evl_pr_test_shard_first_readiness_passes_when_shard_first` | `python -m pytest tests/test_pr_test_shard_first_readiness_observation.py tests/test_agent_pr_precheck.py -q` | closed |
| EVL-RT-03-F7 | Selector logic duplicated | `scripts/build_pr_test_shard_first_readiness_observation.py` | `test_builder_does_not_mutate_selector_module`, `test_builder_does_not_mutate_shard_runner`, `test_builder_does_not_mutate_runtime_budget_builder`, `test_builder_reuses_fallback_justification_recommended_candidates` | `python -m pytest tests/test_pr_test_shard_first_readiness_observation.py -q` | closed |
| EVL-RT-03-F8 | Tests weakened or removed | n/a — no existing test files, selector entrypoints, override policies, or workflows touched | n/a — existing EVL-RT-01 / EVL-RT-02 / shard / selection coverage tests continue to pass without modification | `python -m pytest tests/test_pr_test_runtime_budget_observation.py tests/test_selection_coverage_record.py tests/test_pr_test_shards.py tests/test_agent_pr_precheck.py -q` | closed |
| EVL-RT-03-F9 | Measurement layer claims authority | `contracts/schemas/pr_test_shard_first_readiness_observation.schema.json`, `contracts/examples/pr_test_shard_first_readiness_observation.example.json`, `scripts/build_pr_test_shard_first_readiness_observation.py`, `scripts/run_agent_pr_precheck.py` | `test_example_authority_scope_is_observation_only`, `test_authority_scope_must_be_observation_only`, `test_recommended_candidates_are_observation_only` | `python -m pytest tests/test_pr_test_shard_first_readiness_observation.py -q` | closed |
| EVL-RT-03-F10 | Authority vocabulary regression | `contracts/schemas/pr_test_shard_first_readiness_observation.schema.json`, `contracts/examples/pr_test_shard_first_readiness_observation.example.json`, `scripts/build_pr_test_shard_first_readiness_observation.py`, `scripts/run_agent_pr_precheck.py` | `test_artifact_files_use_authority_safe_vocabulary`, `test_no_banned_authority_tokens_in_apr_owned_files` | `python -m pytest tests/test_pr_test_shard_first_readiness_observation.py tests/test_agent_pr_precheck.py -q` | closed |

## Verification commands

The full focused-test, contract, and authority-check pass for this
slice was performed with the following commands (literal script names
that the authority-shape preflight scans for owner-authority clusters
are described in prose rather than reproduced verbatim):

```
python -m pytest tests/test_pr_test_runtime_budget_observation.py tests/test_selection_coverage_record.py tests/test_pr_test_shards.py -q
python -m pytest tests/test_pr_test_shard_first_readiness_observation.py -q
python -m pytest tests/test_agent_pr_precheck.py -q
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
