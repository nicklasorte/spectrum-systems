# Plan — TLS-EXEC-01 — 2026-04-27

## Prompt type
PLAN

## Roadmap item
TLS-EXEC-01 — Operationalize TLS (Review → Fix → Action → Control → Learn)

## Objective
Implement a deterministic five-phase TLS execution pipeline that produces governed artifacts for ranking review, score adjustments, execution action planning, control integration, and learning updates.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-TLS-EXEC-01-2026-04-27.md | CREATE | Required plan-first artifact for a multi-file build. |
| spectrum_systems/modules/tls_dependency_graph/tls_exec_01.py | CREATE | Implement deterministic TLS-05..TLS-09 logic with fail-closed behavior. |
| scripts/run_tls_exec_01.py | CREATE | Provide CLI entrypoint for artifact-first execution and CI use. |
| tests/test_tls_exec_01.py | CREATE | Validate misranking detection, ranking improvement, action plan correctness, control enforcement, and learning updates. |
| artifacts/tls/tls_ranking_review_report.json | CREATE | TLS-05 output artifact. |
| artifacts/tls/system_dependency_priority_report.json | MODIFY | TLS-06 adjusted deterministic priority report. |
| artifacts/system_dependency_priority_report.json | MODIFY | Publish TLS-06 adjusted report at top-level artifact path. |
| artifacts/tls/ranking_adjustment_log.json | CREATE | TLS-06 adjustment trace artifact. |
| artifacts/tls/tls_action_plan.json | CREATE | TLS-07 execution action plan artifact. |
| artifacts/tls/tls_control_input_artifact.json | CREATE | TLS-08 control-input artifact for CDE review. |
| artifacts/tls/tls_control_decision_artifact.json | CREATE | TLS-08 control decision artifact enforcing CDE+SEL gate. |
| artifacts/tls/tls_learning_record.json | CREATE | TLS-09 learning record artifact. |
| artifacts/tls/tls_weight_update_record.json | CREATE | TLS-09 deterministic weight update artifact. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_tls_exec_01.py`
2. `pytest tests/test_build_tls_dependency_priority.py`

## Scope exclusions
- Do not modify TLS phase 0..4 graph/evidence/classification/trust-gap generation logic.
- Do not introduce non-deterministic ranking adjustments.
- Do not add dashboard-side computation or execution authority transfer to TLS.

## Dependencies
- `artifacts/system_dependency_priority_report.json` must exist and remain the source input for TLS-EXEC-01.
