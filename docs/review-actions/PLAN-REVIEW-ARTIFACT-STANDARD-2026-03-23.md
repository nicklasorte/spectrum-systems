# Plan — REVIEW-ARTIFACT-STANDARD — 2026-03-23

## Prompt type
PLAN

## Roadmap item
Foundation slice for governed review artifacts supporting future review-and-fix orchestration.

## Objective
Establish a canonical, machine-validated review artifact contract and repository review-storage standard so reviews can be deterministically retrieved and validated.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-REVIEW-ARTIFACT-STANDARD-2026-03-23.md | CREATE | Required plan-first artifact for this multi-file contract/governance change. |
| contracts/schemas/review_artifact.schema.json | CREATE | Canonical governed schema for review artifacts. |
| contracts/examples/review_artifact.json | CREATE | Golden-path example review artifact payload. |
| contracts/examples/review_artifact.example.json | CREATE | Golden-path fixture for contract validation skill compatibility. |
| contracts/standards-manifest.json | MODIFY | Register `review_artifact` contract and bump manifest version metadata. |
| docs/reviews/README.md | MODIFY | Define canonical storage, naming, metadata, and section requirements for markdown reviews. |
| scripts/validate_review_artifact.py | CREATE | Thin deterministic validator for review artifact JSON and markdown metadata block checks. |
| tests/test_review_artifact_contract.py | CREATE | Contract and helper validation tests for review artifact standard. |

## Contracts touched
- `contracts/schemas/review_artifact.schema.json` (new)
- `contracts/standards-manifest.json` (version bump + registration for `review_artifact`)

## Tests that must pass after execution
1. `pytest tests/test_review_artifact_contract.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/golden-path-check/run.sh review_artifact`

## Scope exclusions
- Do not implement review orchestration runners.
- Do not implement full markdown review parsing.
- Do not implement fix prompt generation.
- Do not bulk-migrate historical review documents.
- Do not change unrelated contracts or module internals.

## Dependencies
- Active contract and governance baseline on `main` for `contracts/standards-manifest.json`.
