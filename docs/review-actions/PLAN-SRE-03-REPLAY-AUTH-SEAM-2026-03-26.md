# Plan — SRE-03 Replay Authoritative Seam Hardening — 2026-03-26

## Prompt type
PLAN

## Roadmap item
SRE-03 — Replay correctness and governed seam enforcement

## Objective
Harden runtime replay so downstream monitor/decision logic only consumes schema-validated, replay-attached governed artifacts with deterministic identities and fail-closed enforcement.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SRE-03-REPLAY-AUTH-SEAM-2026-03-26.md | CREATE | Record required PLAN before multi-file schema + runtime enforcement updates. |
| PLANS.md | MODIFY | Register this active plan in repository plan index. |
| contracts/schemas/replay_result.schema.json | MODIFY | Tighten replay_result contract for authoritative embedded artifacts and deterministic identity fields. |
| contracts/examples/replay_result.json | MODIFY | Keep golden example aligned with tightened replay_result schema contract. |
| contracts/standards-manifest.json | MODIFY | Bump manifest and replay_result contract publication metadata for schema change. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Enforce fail-closed authoritative replay seam, deterministic replay identity/timestamp behavior, and bypass blocking. |
| spectrum_systems/modules/runtime/alert_triggers.py | MODIFY | Remove best-effort missing-source behavior and fail closed when replay-attached governed sources are incomplete. |
| tests/test_replay_engine.py | MODIFY | Add regression coverage for required replay attachments, deterministic replay output identity, and bypass prevention. |
| tests/test_alert_triggers.py | MODIFY | Assert fail-closed behavior when required replay-attached artifacts are missing. |

## Contracts touched
- `contracts/schemas/replay_result.schema.json` (schema_version increment; stricter required fields and linkage constraints)
- `contracts/standards-manifest.json` (artifact/manifest version update)

## Tests that must pass after execution
1. `pytest tests/test_replay_engine.py tests/test_alert_triggers.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add new runtime subsystems or external integrations.
- Do not change AI/LLM logic or prompt orchestration behavior.
- Do not refactor unrelated modules outside replay/alert/schema enforcement seam.
- Do not weaken fail-closed behaviors.

## Dependencies
- Existing SRE-03 canonical replay path in `run_replay(...)` remains the execution base.
- Existing SRE-08/SRE-10 governed observability and error-budget contracts remain the source schema vocabulary.
