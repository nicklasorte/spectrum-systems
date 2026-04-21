# Eval Runner Specification

## Overview
The eval runner executes deterministic and LLM-assisted evaluation cases against
artifacts produced by each MVP step.  All results are written as `eval_result`
artifacts; a batch is summarised in an `eval_summary` artifact.

## Eval Types

| Type | Description | Deterministic? |
|------|-------------|----------------|
| `schema_conformance` | JSON-schema validation | Yes |
| `completeness` | Required fields present and non-empty | Yes |
| `traceability` | All upstream artifact IDs resolvable | Yes |
| `replay_determinism` | Re-run N times, check structural equivalence | Yes (≥95%) |
| `critic_score` | LLM quality evaluation (0–1.0, fixed seed) | Reproducible |

## Pass Criteria
- `PASS`: All assertions met, score ≥ threshold.
- `FAIL`: Any assertion fails, or score < threshold.
- `INDETERMINATE`: Eval cannot reach a decision.  **Treated as FAIL** (fail-closed).

## Thresholds
- Schema / completeness / traceability: 100%
- Replay determinism: ≥95% structural equivalence
- Critic score: ≥0.7 per artifact (≥0.85 aggregate for GATE)

## Output Artifacts
- Per-case: `eval_result` artifact (schema: `eval_result.schema.json`)
- Batch: `eval_summary` artifact (schema: `eval_summary.schema.json`)
  - `recommended_action`: one of `proceed | warn | block`

## Gate Thresholds
| Gate | Scope | pass_rate requirement |
|------|-------|-----------------------|
| GATE-1 | MVP-1, MVP-2, MVP-3 | ≥ 0.95 |
| GATE-2 | MVP-4, MVP-5, MVP-6 | ≥ 0.95 |
| GATE-3 | MVP-7, MVP-8, MVP-9 | ≥ 0.95 |
| GATE-4 | MVP-10, MVP-11 | ≥ 0.95 |
| GATE-5 | MVP-12, MVP-13 + cert | ≥ 0.95 + CERT PASSED |

## Failure Handling
On any GATE breach: the control decision action is set to `freeze`. TLC halts routing.
Repair cycle required before re-gate.
