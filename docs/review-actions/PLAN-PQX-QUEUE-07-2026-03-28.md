# Plan — PQX-QUEUE-07 — 2026-03-28

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-07] Queue Observability and Health Classification

## Objective
Implement deterministic prompt-queue observability snapshot hardening with bounded health classification and fail-closed handling for missing or ambiguous queue health signals.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-07-2026-03-28.md | CREATE | Required PLAN artifact for multi-file BUILD execution. |
| PLANS.md | MODIFY | Register newly created QUEUE-07 plan in active plans table. |
| spectrum_systems/modules/prompt_queue/queue_observability.py | MODIFY | Add deterministic health metrics derivation and bounded queue health classification logic. |
| contracts/schemas/prompt_queue_observability_snapshot.schema.json | MODIFY | Expand governed observability snapshot contract with required health fields and bounded vocabularies. |
| contracts/examples/prompt_queue_observability_snapshot.json | MODIFY | Update canonical golden-path example to remain schema-valid with new fields. |
| contracts/standards-manifest.json | MODIFY | Register additive observability snapshot schema version update in canonical standards registry. |
| scripts/run_prompt_queue_observability.py | MODIFY | Keep thin wrapper while enforcing explicit non-zero fail-closed behavior on malformed input/artifact validation failures. |
| tests/test_prompt_queue_observability.py | MODIFY | Add deterministic coverage for stable/degraded/unstable classification and fail-closed malformed/ambiguous inputs. |

## Contracts touched
- `contracts/schemas/prompt_queue_observability_snapshot.schema.json` (additive schema update)
- `contracts/standards-manifest.json` (version and snapshot contract metadata update)

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_observability.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add replay/resume queue behavior.
- Do not add certification, backtesting, or multi-queue scheduling logic.
- Do not modify queue transition execution policy behavior beyond read-only observability derivation.

## Dependencies
- QUEUE-05 execution loop seam and queue state progression semantics must remain authoritative.
- QUEUE-06 retry and blocked-recovery artifacts must remain authoritative signal sources for derived metrics.
