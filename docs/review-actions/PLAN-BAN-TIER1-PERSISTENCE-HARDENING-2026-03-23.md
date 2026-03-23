# Plan — BAN Tier-1 Persistence Hardening — 2026-03-23

## Prompt type
PLAN

## Roadmap item
BAN Tier-1 trust-boundary persistence hardening

## Objective
Enforce append-only, identity-safe, fail-closed persistence semantics across runtime trace storage and replay artifacts with hardened contracts and deterministic tests.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAN-TIER1-PERSISTENCE-HARDENING-2026-03-23.md | CREATE | Required PLAN artifact before multi-file BUILD |
| spectrum_systems/modules/runtime/trace_store.py | MODIFY | Remove mutability paths, enforce immutable writes and identity validation |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Remove placeholder linkage, enforce replay linkage integrity, and align persistence guarantees |
| contracts/schemas/persisted_trace.schema.json | MODIFY | Harden persisted-trace identity/storage constraints |
| contracts/schemas/replay_result.schema.json | MODIFY | Harden replay linkage/identity constraints and disallow placeholder linkage |
| contracts/standards-manifest.json | MODIFY | Version bump metadata due to schema changes |
| tests/test_trace_store.py | MODIFY | Migrate tests to append-only + identity-integrity semantics |
| tests/test_replay_engine.py | MODIFY | Add fail-closed linkage/persistence parity tests |

## Contracts touched
- `contracts/schemas/persisted_trace.schema.json` (constraint hardening)
- `contracts/schemas/replay_result.schema.json` (constraint hardening)
- `contracts/standards-manifest.json` (version metadata update)

## Tests that must pass after execution
1. `pytest tests/test_trace_store.py tests/test_replay_engine.py tests/test_contracts.py`
2. `pytest tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not refactor unrelated runtime modules.
- Do not alter non-storage replay/control-loop semantics beyond fail-closed linkage and persistence parity.
- Do not modify unrelated contracts/examples outside the listed schema and standards manifest updates.

## Dependencies
- None.
