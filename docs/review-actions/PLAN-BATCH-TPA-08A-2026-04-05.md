# Plan — BATCH-TPA-08A Strategy Alignment Hardening — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-TPA-08A — Strategy Alignment Hardening (R3, R5, R1)

## Objective
Harden TPA governance integrity by wiring bypass drift into readiness observability, anchoring scope policy to source-authority refresh evidence, and making TPA policy precedence explicit through a contract-backed composition artifact consumed by runtime checks.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-08A-2026-04-05.md | CREATE | Required plan-first artifact for this multi-file schema/runtime/test hardening slice. |
| contracts/schemas/judgment_remediation_readiness_status.schema.json | MODIFY | Add deterministic readiness-plane fields for consumed TPA bypass drift signal references. |
| contracts/examples/judgment_remediation_readiness_status.json | MODIFY | Golden example for updated readiness contract with bypass signal observability fields. |
| spectrum_systems/orchestration/cycle_observability.py | MODIFY | Wire TPA bypass drift into remediation readiness observability and fail-closed behavior. |
| contracts/schemas/tpa_scope_policy.schema.json | MODIFY | Anchor scope policy to source-authority layer via required refresh-evidence object. |
| config/policy/tpa_scope_policy.json | MODIFY | Provide source-authority refresh evidence in the governed scope policy artifact. |
| spectrum_systems/modules/governance/tpa_scope_policy.py | MODIFY | Enforce scope-policy source-authority refresh evidence fail-closed checks. |
| contracts/schemas/tpa_policy_composition.schema.json | CREATE | New contract declaring deterministic precedence/merge rules for TPA-adjacent policies. |
| contracts/examples/tpa_policy_composition.json | CREATE | Golden-path example for policy composition contract. |
| config/policy/tpa_policy_composition.json | CREATE | Runtime-governed instance of the composition contract consumed by policy resolution logic. |
| spectrum_systems/modules/governance/tpa_policy_composition.py | CREATE | Load/validate/apply composition contract for deterministic policy resolution. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Consume contract-backed policy composition precedence instead of implicit precedence only in code. |
| tests/test_cycle_observability.py | MODIFY | Coverage for bypass drift readiness wiring and fail-closed evidence behavior. |
| tests/test_tpa_scope_policy.py | MODIFY | Coverage for source-authority anchoring and refresh-evidence fail-closed behavior. |
| tests/test_tpa_policy_composition.py | CREATE | Deterministic precedence and conflict-resolution tests for composition contract. |
| tests/test_tpa_sequence_runner.py | MODIFY | Integration coverage that runtime precedence is contract-backed and deterministic. |
| tests/test_contracts.py | MODIFY | Validate new/updated schema examples (tpa_policy_composition and updated contracts). |
| contracts/standards-manifest.json | MODIFY | Register new contract and version bumps for modified contracts. |

## Contracts touched
- `judgment_remediation_readiness_status` (version bump)
- `tpa_scope_policy` (version bump)
- `tpa_policy_composition` (new)

## Tests that must pass after execution
1. `pytest tests/test_cycle_observability.py tests/test_tpa_scope_policy.py tests/test_tpa_policy_composition.py tests/test_tpa_sequence_runner.py tests/test_contracts.py`
2. `pytest tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign TPA phase artifacts (`plan/build/simplify/gate`) beyond required policy-resolution/readiness wiring.
- Do not implement the deferred unified TPA certification envelope (R4).
- Do not widen repo taxonomy or introduce new artifact classes beyond existing governed contract families.

## Dependencies
- Existing TPA hardening slices from `docs/review-actions/PLAN-BATCH-TPA-02-2026-04-04.md`, `PLAN-BATCH-TPA-03-2026-04-04.md`, and `PLAN-BATCH-TPA-04-2026-04-04.md`.
- Source authority layer from `docs/review-actions/PLAN-SOURCE-AUTHORITY-LAYER-2026-03-28.md`.
