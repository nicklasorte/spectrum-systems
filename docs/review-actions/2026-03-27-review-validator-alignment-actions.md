# 2026-03-27 Review Validator Alignment — Actions

## Decision
- **Authoritative validation model:** aligned dual-path model.
- `scripts/validate_review_artifact.py` is the canonical pairwise validator.
- `scripts/validate_review_artifacts.py` is the repo-level runner that applies canonical pairwise validation across discovered artifact pairs.

## Changes made
1. Refactored `scripts/validate_review_artifacts.py` to:
   - Discover canonical governed review JSON artifacts only.
   - Validate JSON with `validate_review_json` from `scripts/validate_review_artifact.py`.
   - Validate markdown companions with `validate_markdown_metadata`.
   - Fail closed when markdown companions are missing.
2. Updated `docs/reviews/README.md` to document canonical pairwise validation and repo-level aggregation behavior.
3. Added `tests/test_review_artifact_repo_validation.py` with coverage for:
   - current-artifact pass,
   - invalid artifact fail,
   - missing markdown pair fail.
4. Recorded governance decision in `docs/reviews/2026-03-27-review-validator-alignment.md`.

## Rationale
- Prevent contradictory outcomes between validators.
- Preserve strict schema enforcement via `contracts/schemas/review_artifact.schema.json`.
- Keep CI/tooling behavior deterministic and fail-closed.

## Deprecated paths
- Legacy schema-driven behavior in `scripts/validate_review_artifacts.py` is removed.
- The legacy schema file remains in repository for backward compatibility with unrelated historical tests/docs, but it is no longer authoritative for governed review artifacts.

## Verification checklist
- [x] `python scripts/validate_review_artifacts.py` exits 0 on current repository state.
- [x] `pytest -q` passes after alignment and added coverage.
