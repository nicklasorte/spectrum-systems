# Plan — CON-033-FIX-2 ARTIFACT_CLASS GOVERNANCE ENUM RECONCILIATION — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-033-FIX-2 — Reconcile artifact_class enum drift for governance artifacts

## Objective
Resolve the exact artifact_class enum mismatch for the CON-033 trust-spine cohesion artifact in the smallest repo-native way so classification and dependency graph validations pass.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-033-FIX-ARTIFACT-CLASS-GOVERNANCE-2026-04-02.md | CREATE | Plan-first requirement for this reconciliation slice. |
| PLANS.md | MODIFY | Register this fix plan. |
| contracts/standards-manifest.json | MODIFY (if needed) | Reclassify affected artifact entry if required by canonical taxonomy evidence. |
| tests/test_artifact_classification.py | MODIFY (if needed) | Align allowed-class assertions with canonical decision. |
| contracts/schemas/dependency-graph.schema.json | MODIFY (if needed) | Align dependency graph artifact class enum with canonical decision. |
| scripts/build_dependency_graph.py | MODIFY (if needed) | Align generator classification validation with canonical decision. |
| tests/test_dependency_graph.py | MODIFY (if needed) | Narrow assertion updates for canonical class decision. |

## Contracts touched
Expected: no new contracts. Only reconcile existing class taxonomy usage if proven necessary.

## Tests that must pass after execution
1. `pytest -q tests/test_artifact_classification.py tests/test_dependency_graph.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py` (if schema/manifest/generator changed)
4. Dependency-graph builder path used by tests (if applicable)
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign artifact taxonomy.
- Do not touch unrelated runtime/control-loop logic.
- Do not add new feature behavior beyond enum/classification reconciliation.

## Dependencies
- CON-033 branch artifact registration is already present and must remain intact.
