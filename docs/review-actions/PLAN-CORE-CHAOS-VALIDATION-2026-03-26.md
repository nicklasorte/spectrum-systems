# Plan — CORE-CHAOS-VALIDATION — 2026-03-26

## Prompt type
PLAN

## Roadmap item
System roadmap active slice — governed core loop chaos/failure validation hardening

## Objective
Add a deterministic, fail-closed chaos validation slice that exercises governed runtime seams and emits schema-valid audit artifacts without changing control-loop behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CORE-CHAOS-VALIDATION-2026-03-26.md | CREATE | Required plan-first governance precondition for multi-file BUILD + contract addition. |
| contracts/schemas/governed_failure_injection_summary.schema.json | CREATE | New governed artifact contract for deterministic chaos/failure validation output. |
| contracts/examples/governed_failure_injection_summary.json | CREATE | Minimal schema-valid example payload for new contract. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump manifest version metadata. |
| spectrum_systems/modules/runtime/governed_failure_injection.py | CREATE | Deterministic runtime chaos case executor over existing validators/builders. |
| scripts/run_governed_failure_injection.py | CREATE | Thin operator CLI for running selected chaos cases and writing artifacts. |
| tests/test_governed_failure_injection.py | CREATE | Golden/fail path tests for deterministic IDs, schema validity, fail-closed checks, and CLI exit codes. |
| tests/fixtures/governed_failure_injection_cases.json | CREATE | Deterministic case selector fixture for CLI filtering tests. |

## Contracts touched
- New: `governed_failure_injection_summary` (`contracts/schemas/governed_failure_injection_summary.schema.json`)
- Modified: `contracts/standards-manifest.json` (version bump + contract registration entry)

## Tests that must pass after execution
1. `pytest tests/test_governed_failure_injection.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `pytest`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign control loop semantics or policy precedence.
- Do not add network calls, LLM logic, or permissive fallback behavior.
- Do not refactor unrelated runtime modules.
- Do not modify non-adjacent schemas/contracts outside this slice.

## Dependencies
- Existing runtime seam validators/builders must remain authoritative and reused in-place.
