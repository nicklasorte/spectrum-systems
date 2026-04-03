# Plan — BATCH-RA — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-RA — Narrow Fix: Review Artifact Class Alignment

## Objective
Repair the BATCH-R artifact-classification regression by reclassifying new review observability artifacts into an existing allowed class without widening global taxonomy.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RA-2026-04-03.md | CREATE | Required plan-first artifact for this narrow fix. |
| PLANS.md | MODIFY | Register active BATCH-RA plan entry. |
| contracts/standards-manifest.json | MODIFY | Reclassify review artifacts to allowed manifest artifact_class values. |

## Contracts touched
- `review_eval_generation_report` (classification-only manifest alignment)
- `review_failure_summary` (classification-only manifest alignment)
- `review_hotspot_report` (classification-only manifest alignment)

## Invariants to preserve
- No new global artifact_class vocabulary.
- No redesign of review trigger/eval/gating logic.
- No schema discipline weakening.
- Dependency graph and artifact classification validations remain fail-closed.

## Risks
- Missing one affected manifest entry would keep classification tests failing.
- Accidental edits beyond manifest scope would violate narrow-fix intent.

## Acceptance criteria
- `tests/test_artifact_classification.py` passes.
- `tests/test_dependency_graph.py` passes.
- Required BATCH-R review/eval tests still pass.
- Contract enforcement passes.

## Test plan
1. `pytest tests/test_artifact_classification.py`
2. `pytest tests/test_dependency_graph.py`
3. `pytest tests/test_review_signal_extractor.py`
4. `pytest tests/test_review_eval_bridge.py`
5. `pytest tests/test_evaluation_control.py`
6. `pytest tests/test_evaluation_auto_generation.py`
7. `pytest tests/test_review_trigger_policy.py`
8. `pytest tests/test_review_required_gating.py`
9. `pytest tests/test_contracts.py`
10. `pytest tests/test_contract_enforcement.py`
11. `python scripts/run_contract_enforcement.py`

## Non-goals
- No changes to review trigger logic.
- No changes to review/eval schema shapes.
- No changes to dependency graph schema enums.
