# CLP-02 Review Actions

Companion to `docs/reviews/CLP-02_require_pre_pr_gate_redteam.md`.

## Summary

Red-team review produced **0 must_fix** findings. All 13 vectors are
either fully covered by CLP-02 surfaces (items 1–11, 13) or recorded as
documented hardening gaps owned by AEX/PQX (item 12).

This document still records every CLP-02 surface change so a reviewer can
trace the disposition of each red-team finding back to a concrete file
and test.

## Disposition table

| Finding | Category    | Disposition         | Files / tests                                                                                                                                                                                                                              |
|---------|-------------|---------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1       | observation | covered             | `agent_core_loop_proof.py`, `core_loop_pre_pr_gate_policy.py`; `tests/test_agent_core_loop_requires_clp.py::test_missing_clp_blocks_repo_mutating`                                                                                          |
| 2       | observation | covered             | `agent_core_loop_proof.py::_load_clp_evidence`; existing `tests/test_core_loop_pre_pr_gate.py::test_agl_treats_invalid_clp_artifact_as_missing`                                                                                              |
| 3       | observation | covered             | `core_loop_pre_pr_gate_policy.py::evaluate_pr_ready`; `tests/test_check_agent_pr_ready.py::test_clp_block_blocks_pr_ready`                                                                                                                  |
| 4       | observation | covered             | `core_loop_pre_pr_gate_policy.py::evaluate_pr_ready`; `tests/test_check_agent_pr_ready.py::test_warn_with_unallowed_reason_blocks` and `test_warn_with_policy_allowed_reason_passes`                                                         |
| 5       | observation | covered             | `scripts/run_core_loop_pre_pr_gate.py::_check_authority_shape`; existing `tests/test_core_loop_pre_pr_gate.py::test_authority_shape_failure_blocks` and `test_missing_required_check_output_blocks`                                          |
| 6       | observation | covered             | `scripts/run_core_loop_pre_pr_gate.py::_check_authority_leak`; existing `tests/test_core_loop_pre_pr_gate.py::test_authority_leak_failure_blocks`                                                                                            |
| 7       | observation | covered             | `scripts/run_core_loop_pre_pr_gate.py::_check_contract_preflight`; `spectrum_systems/modules/prl/clp_consumer.py::CLP_TO_PRL_FAILURE_CLASS`; `tests/test_check_agent_pr_ready.py::test_clp_block_normalizes_to_prl_classes`                  |
| 8       | observation | covered             | `scripts/run_core_loop_pre_pr_gate.py::_check_tls_freshness`; existing `tests/test_core_loop_pre_pr_gate.py::test_tls_freshness_drift_blocks` and `test_stale_tls_artifact_blocks`                                                            |
| 9       | observation | covered             | `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py::evaluate_gate`; existing `tests/test_core_loop_pre_pr_gate.py::test_tls_freshness_skip_blocks_repo_mutating`                                                                     |
| 10      | observation | covered             | `scripts/run_core_loop_pre_pr_gate.py::_check_selected_tests`; existing `tests/test_core_loop_pre_pr_gate.py::test_selected_tests_skip_in_repo_mutating_blocks`                                                                              |
| 11      | observation | covered             | Schemas pin `authority_scope` const; `docs/governance/core_loop_pre_pr_gate_policy.json` `must_not_do`; `tests/test_core_loop_pre_pr_gate_policy.py::test_policy_authority_scope_is_observation_only`                                       |
| 12      | observation | gap documented      | `docs/architecture/clp_02_pr_ready_admission.md` (Remaining hardening gap section); `docs/architecture/system_registry.md` (CLP-02 entry, "must_not_do" preserves AEX/PQX authority)                                                       |
| 13      | observation | covered             | `spectrum_systems/modules/prl/clp_consumer.py`; `scripts/run_pre_pr_reliability_gate.py` (`--clp-result`); `tests/test_check_agent_pr_ready.py::test_clp_block_normalizes_to_prl_classes`                                                   |

## must_fix actions

None — no must_fix findings.

## should_fix actions

None.

## Validation

The cleanup-section of `docs/reviews/CLP-02_require_pre_pr_gate_final_report.md`
records the exact validation commands run and their results
(authority-shape preflight pass, authority-leak guard pass, contract
compliance signal pass, full CLP-02 + CLP-01 + AGL test bundle pass).
