# HOP BATCH-3 Red-Team Review (A25) + Fix Pass (A26)

## Prompt type
REVIEW

## Scope
HOP-BATCH-3 (A20–A26) for transcript → FAQ golden workflow only.

## Finding 1 — Sandbox escape via unsafe runtime operations
- **Severity:** Critical
- **Reproduction:** Candidate harness attempts network socket connection, `subprocess.Popen`, env read, or file write outside temp scope.
- **Required fix:** Force evaluator execution through subprocess sandbox and treat any guard hit as `sandbox_violation` failure artifact.
- **Fix status:** Implemented in `sandbox.py` + evaluator wiring; covered by sandbox unit/adversarial tests.

## Finding 2 — Pattern misuse can degrade quality silently
- **Severity:** High
- **Reproduction:** Draft output accepted without contradictory evidence check.
- **Required fix:** Draft-verify pattern must always include supporting and contradicting evidence surfaces and explicit confirm/revise verification signal.
- **Fix status:** Implemented in `patterns/draft_verify.py`; schema-bound with deterministic structure.

## Finding 3 — Overfitting to search set only
- **Severity:** Medium
- **Reproduction:** Optimization loop reports gain without baseline/best trail visibility.
- **Required fix:** Controlled trial report must include baseline score, best score, and frontier evolution over fixed iteration window.
- **Fix status:** Implemented in `trial_runner.py` with immutable report artifact and reproducible iteration bounds (5–10).

## Finding 4 — Context explosion from optional bootstrap
- **Severity:** Medium
- **Reproduction:** Full repository dump inserted into harness context.
- **Required fix:** Bootstrap snapshot capped with deterministic entry limits and explicit context budget field.
- **Fix status:** Implemented in `bootstrap.py` with bounded `max_entries` and `context_budget_tokens`.

## Finding 5 — Routing errors from non-deterministic free-text policy
- **Severity:** High
- **Reproduction:** Router uses unconstrained natural-language choice.
- **Required fix:** Deterministic routing on content signals and fixed task enums (`faq_extract`, `classify_statement`, `ignore`).
- **Fix status:** Implemented in `patterns/domain_router.py`; schema-bound routing artifact.

## Finding 6 — Bootstrap misuse introduces noise
- **Severity:** Medium
- **Reproduction:** Bootstrap always injected, even when not requested.
- **Required fix:** Bootstrap remains optional pattern-level artifact; not default in evaluator.
- **Fix status:** `bootstrap.py` is standalone and never auto-invoked by evaluator/optimization loop.

## A26 Fix Validation Summary
- All identified findings have code-level mitigations and deterministic tests.
- Trial rerun path is advisory-only (`advisory_only=true`).
