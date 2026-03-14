# CODEX.md — spectrum-program-advisor

Execution guidance for Codex-style agents working in the `spectrum-program-advisor` repo.

## Principles
- Treat `spectrum-systems` contracts as law; do not fork schemas.
- Keep outputs deterministic; structured JSON is authoritative before prose.
- Preserve traceability links between risks, decisions, milestones, assumptions, and source artifacts.
- Avoid automation code until workflows and tests exist; start with fixtures and validation.

## Tasks to perform
- Maintain repository structure (`docs/`, `contracts/`, `src/`, `examples/`, `tests/`).
- Update fixtures and CLI behavior when contracts change.
- Ensure CLI outputs stay in sync with canonical examples.
- Expand evaluation tests for readiness scoring, dependency handling, and missing-evidence reporting.

## Tasks to avoid
- Inventing new schemas locally.
- Removing human review gates or determinism checks.
- Introducing non-deterministic AI behavior without guarded evaluation.

## Dependencies
- Contracts resolved from `spectrum-systems/contracts/schemas`.
- Tests should use standard library tooling; pin to fixtures for determinism.
