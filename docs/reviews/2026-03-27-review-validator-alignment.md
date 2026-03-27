---
module: review_validator_governance
review_type: validator_alignment_decision
review_date: 2026-03-27
reviewer: Codex
decision: PASS
trust_assessment: high
status: final
related_plan: docs/review-actions/PLAN-PQX-FIX-REVIEW-VALIDATOR-ALIGNMENT-2026-03-27.md
---

## Scope
- Determine authoritative review-artifact validator path across scripts, tests, and docs.
- Resolve mismatch between repo-level and pairwise validator behavior.
- Keep fail-closed semantics and canonical contract enforcement.

## Decision
**Decision: C) Both must be aligned** (preferred path).

`validate_review_artifact.py` is the canonical validator implementation and `validate_review_artifacts.py` is now an authoritative repo-level orchestrator that reuses the same canonical checks per JSON/Markdown pair.

## Trust Assessment
- High confidence.
- Evidence reviewed:
  - `scripts/validate_review_artifact.py`
  - `scripts/validate_review_artifacts.py`
  - `docs/reviews/README.md`
  - `tests/test_control_loop_hardening.py`
  - `tests/test_review_artifact_repo_validation.py`

## Critical Findings
- Prior state had dual-validator drift:
  - pairwise validator used `contracts/schemas/review_artifact.schema.json`
  - repo-level validator used legacy `schemas/review-artifact.schema.json`
- This allowed contradictory pass/fail outcomes for the same artifacts.

## Required Fixes
- Refactor repo-level validator to call canonical pairwise validation logic.
- Enforce markdown companion presence at repo-level.
- Add deterministic test coverage for pass/fail/missing-pair outcomes.

## Optional Improvements
- Future follow-up: remove or formally deprecate legacy `schemas/review-artifact.schema.json` once no remaining consumers reference it.

## Failure Mode Summary
Validator drift created governance ambiguity. Alignment removes conflicting validation paths and restores single-source-of-truth behavior.
