# Plan — Prompt BPB Boundary Fix — 2026-03-21

## Prompt type
PLAN

## Roadmap item
Prompt BPB — Strategic Knowledge Validation Gate (Boundary Compliance Fix)

## Objective
Refactor the Strategic Knowledge Validation Gate to restore clean architecture boundaries by separating deterministic decision logic from filesystem loading/CLI adapters, while preserving fail-closed behavior and decision outputs.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BPB-BOUNDARY-FIX-2026-03-21.md | CREATE | Required plan artifact before multi-file BUILD fix. |
| PLANS.md | MODIFY | Register active boundary-fix plan. |
| spectrum_systems/modules/strategic_knowledge/validator.py | MODIFY | Keep policy/decision logic pure and deterministic. |
| spectrum_systems/modules/strategic_knowledge/validation_loader.py | CREATE | Isolate controlled filesystem loading/path resolution adapter. |
| spectrum_systems/modules/strategic_knowledge/__init__.py | MODIFY | Export refactored validation APIs. |
| scripts/validate_strategic_knowledge_artifact.py | MODIFY | Keep CLI thin by delegating loading + policy to module APIs. |
| tests/test_strategic_knowledge_validator.py | MODIFY | Align tests to pure validator interface and boundary shape. |
| tests/test_validate_strategic_knowledge_artifact_cli.py | MODIFY | Validate CLI remains thin and deterministic with adapter flow. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_strategic_knowledge_validator.py tests/test_validate_strategic_knowledge_artifact_cli.py`
2. `python scripts/check_artifact_boundary.py`
3. `python scripts/run_contract_enforcement.py`
4. `PLAN_FILES="docs/review-actions/PLAN-BPB-BOUNDARY-FIX-2026-03-21.md PLANS.md spectrum_systems/modules/strategic_knowledge/validator.py spectrum_systems/modules/strategic_knowledge/validation_loader.py spectrum_systems/modules/strategic_knowledge/__init__.py scripts/validate_strategic_knowledge_artifact.py tests/test_strategic_knowledge_validator.py tests/test_validate_strategic_knowledge_artifact_cli.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not weaken contract schema strictness.
- Do not remove fail-closed responses.
- Do not disable boundary checks.
- Do not add extraction/ingestion logic.

## Dependencies
- Prompt BPB implementation commit must be present.
