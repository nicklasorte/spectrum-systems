# RAX eval surface authority chain (RAX-EVAL-01)

RAX execution now uses a governed eval surface so test success alone cannot advance readiness.

## Authority chain
1. **tests** are developer execution signals only.
2. **eval artifacts** (`eval_result`, `eval_summary`) are governed quality signals for RAX semantics and control integrity.
3. **readiness artifact** (`rax_control_readiness_record`) is a bounded local artifact for downstream control consumption.
4. **downstream control** remains the authority; RAX does not hold promotion authority.

## Minimum flow
`tests -> eval artifacts -> readiness artifact -> downstream control`

## Why this was required
RAX previously allowed test-authoritative progression risks (valid-looking but semantically wrong output, incomplete trace evidence, or missing required eval coverage). The new eval surface enforces fail-closed handling on missing required eval artifacts, semantic contradictions, trace incompleteness, version authority drift, and baseline regression.

Design note: `docs/review-actions/RAX-EVAL-01-design-note.md`.
