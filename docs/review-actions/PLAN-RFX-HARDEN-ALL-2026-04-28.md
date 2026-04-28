# Plan — RFX-HARDEN-ALL — 2026-04-28

## Prompt type
BUILD

## Roadmap item
RFX-HARDEN-ALL (RFX-H01 through RFX-H19)

## Objective
Implement deterministic, non-owning RFX hardening modules H01-H19 with focused tests, guarded script wiring, red-team/fix/revalidation artifacts, and roadmap/report updates.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/rfx_health_contract.py | CREATE | H01 health contract generation/validation. |
| spectrum_systems/modules/runtime/rfx_reason_code_registry.py | CREATE | H02 reason-code registry + validation. |
| spectrum_systems/modules/runtime/rfx_debug_bundle.py | CREATE | H03 deterministic debug bundle generation. |
| spectrum_systems/modules/runtime/rfx_output_envelope.py | CREATE | H04 normalized envelope + validator. |
| spectrum_systems/modules/runtime/rfx_golden_loop.py | CREATE | H05 advisory golden loop record checks. |
| spectrum_systems/modules/runtime/rfx_dependency_map.py | CREATE | H06 dependency map + hidden/cycle/orphan checks. |
| spectrum_systems/modules/runtime/rfx_bloat_budget.py | CREATE | H07 runtime/size/depth budget checks. |
| spectrum_systems/modules/runtime/rfx_trend_clustering_hardening.py | CREATE | H08 variant clustering and ambiguity records. |
| spectrum_systems/modules/runtime/rfx_calibration_policy_handoff.py | CREATE | H09 calibration policy handoff checks. |
| spectrum_systems/modules/runtime/rfx_memory_persistence_handoff.py | CREATE | H10 persistence handoff and traced-write validation. |
| spectrum_systems/modules/runtime/rfx_authority_pattern_corpus.py | CREATE | H11 bad/neutral pattern corpus validation. |
| spectrum_systems/modules/runtime/rfx_module_elimination.py | CREATE | H12 remove-one-module elimination analysis. |
| spectrum_systems/modules/runtime/rfx_operator_runbook.py | CREATE | H13 runbook generation from registry + debug bundles. |
| spectrum_systems/modules/runtime/rfx_golden_failure_corpus.py | CREATE | H14 stable golden failure corpus + drift checks. |
| spectrum_systems/modules/runtime/rfx_architecture_drift_audit.py | CREATE | H16 drift audit for hidden authority and mutation attempts. |
| spectrum_systems/modules/runtime/rfx_contract_snapshot.py | CREATE | H17 output-contract manifest snapshot checks. |
| spectrum_systems/modules/runtime/rfx_unknown_state_campaign.py | CREATE | H18 unknown-state fail-closed campaign. |
| spectrum_systems/modules/runtime/rfx_authority_vocabulary_sweep.py | CREATE | H19 vocabulary/fixture sweep over changed files. |
| scripts/run_rfx_super_check.py | CREATE | H15 fast decisive preflight check runner. |
| tests/test_rfx_health_contract.py | CREATE | H01 coverage and red-team validation. |
| tests/test_rfx_reason_code_registry.py | CREATE | H02 coverage and red-team validation. |
| tests/test_rfx_debug_bundle.py | CREATE | H03 coverage and red-team validation. |
| tests/test_rfx_output_envelope.py | CREATE | H04 coverage and red-team validation. |
| tests/test_rfx_golden_loop.py | CREATE | H05 coverage and red-team validation. |
| tests/test_rfx_dependency_map.py | CREATE | H06 coverage and red-team validation. |
| tests/test_rfx_bloat_budget.py | CREATE | H07 coverage and red-team validation. |
| tests/test_rfx_trend_clustering_hardening.py | CREATE | H08 coverage and red-team validation. |
| tests/test_rfx_calibration_policy_handoff.py | CREATE | H09 coverage and red-team validation. |
| tests/test_rfx_memory_persistence_handoff.py | CREATE | H10 coverage and red-team validation. |
| tests/test_rfx_authority_pattern_corpus.py | CREATE | H11 coverage and red-team validation. |
| tests/test_rfx_module_elimination.py | CREATE | H12 coverage and red-team validation. |
| tests/test_rfx_operator_runbook.py | CREATE | H13 coverage and red-team validation. |
| tests/test_rfx_golden_failure_corpus.py | CREATE | H14 coverage and red-team validation. |
| tests/test_run_rfx_super_check.py | CREATE | H15 script integrity and output validation. |
| tests/test_rfx_architecture_drift_audit.py | CREATE | H16 coverage and red-team validation. |
| tests/test_rfx_contract_snapshot.py | CREATE | H17 coverage and red-team validation. |
| tests/test_rfx_unknown_state_campaign.py | CREATE | H18 coverage and red-team validation. |
| tests/test_rfx_authority_vocabulary_sweep.py | CREATE | H19 coverage and red-team validation. |
| docs/roadmaps/rfx_cross_system_roadmap.md | MODIFY | Add H01-H19 implemented entries after code/tests land. |
| artifacts/rfx_harden_all_delivery_report.json | CREATE | Delivery report with implementation, signals, RT/fix/revalidation. |
| docs/reviews/RFX-HARDEN-ALL-red-team-review.md | CREATE | Red-team review RT-H01..RT-H19. |
| docs/review-actions/RFX-HARDEN-ALL-fix-actions.md | CREATE | Fix-action matrix RT-H01..RT-H19. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_rfx_*.py -q`
2. `pytest tests/test_run_rfx_super_check.py -q`
3. `pytest tests/test_authority_shape_preflight.py -q`
4. `pytest tests/test_system_registry_guard.py -q`
5. `python scripts/run_rfx_super_check.py`
6. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
7. `python scripts/run_authority_drift_guard.py --base-ref main --head-ref HEAD --output outputs/authority_drift_guard/authority_drift_guard_result.json`
8. `python scripts/run_system_registry_guard.py --base-ref main --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`
9. `python scripts/run_authority_leak_guard.py --base-ref origin/main --head-ref HEAD`
10. `python scripts/check_roadmap_authority.py`
11. `python scripts/check_strategy_compliance.py --roadmap docs/roadmaps/rfx_cross_system_roadmap.md`
12. `python scripts/validate_forbidden_authority_vocabulary.py`
13. `pytest`

## Scope exclusions
- Do not alter canonical authority ownership in `docs/architecture/system_registry.md`.
- Do not introduce a new active system for RFX.
- Do not add non-deterministic behavior or hidden state.
- Do not weaken existing RFX-01 through RFX-16 behavior or guard scripts.

## Dependencies
- Existing RFX-01 through RFX-16 modules and tests remain baseline inputs.
