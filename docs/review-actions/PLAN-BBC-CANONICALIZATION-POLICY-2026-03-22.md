# Plan — BBC Canonicalization Policy Governance Hardening — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt BBC — Eval Registry + Dataset Governance

## Objective
Externalize eval dataset member canonicalization behavior into a governed versioned policy artifact and enforce it fail-closed across dataset build and registry snapshot integrity.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BBC-CANONICALIZATION-POLICY-2026-03-22.md | CREATE | Record approved scope for this multi-file governance hardening change |
| PLANS.md | MODIFY | Register this plan in active plans table |
| contracts/schemas/eval_canonicalization_policy.schema.json | CREATE | Define governed canonicalization policy artifact contract |
| contracts/schemas/eval_dataset.schema.json | MODIFY | Require canonicalization_policy_id on eval datasets |
| contracts/schemas/eval_registry_snapshot.schema.json | MODIFY | Require active and per-dataset canonicalization policy identity |
| contracts/examples/eval_canonicalization_policy.json | CREATE | Provide canonical governed example for policy artifact |
| contracts/examples/eval_dataset.json | MODIFY | Align example dataset with canonicalization policy linkage |
| contracts/examples/eval_registry_snapshot.json | MODIFY | Align snapshot example with canonicalization policy linkage |
| contracts/standards-manifest.json | MODIFY | Publish canonicalization policy contract and version bumps |
| spectrum_systems/modules/evaluation/eval_dataset_loader.py | MODIFY | Add thin loader for canonicalization policy artifact |
| spectrum_systems/modules/evaluation/eval_dataset_registry.py | MODIFY | Enforce policy-governed canonicalization and snapshot integrity checks |
| scripts/build_eval_registry_snapshot.py | MODIFY | Require canonicalization policy input for snapshot construction |
| tests/test_contracts.py | MODIFY | Validate canonicalization policy example in BBC governance contract checks |
| tests/test_eval_dataset_registry.py | MODIFY | Add fail-closed + deterministic policy-governed canonicalization coverage |
| tests/test_build_eval_registry_snapshot_cli.py | MODIFY | Add CLI coverage for canonicalization policy wiring and mismatch rejection |

## Contracts touched
- New contract: `eval_canonicalization_policy` schema `1.0.0`
- Updated contracts: `eval_dataset` schema `1.0.0` (required field expansion), `eval_registry_snapshot` schema `1.0.0` (required field expansion)
- Manifest updates: `contracts/standards-manifest.json` entries + contract `last_updated_in` alignment

## Tests that must pass after execution
1. `pytest -q tests/test_eval_dataset_registry.py tests/test_build_eval_registry_snapshot_cli.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not refactor unrelated evaluation modules or runtime control-loop logic.
- Do not introduce multi-version canonicalization engines beyond explicit v1 policy support.
- Do not change artifact envelope/provenance shared contracts.
- Do not weaken existing admission policy fail-closed checks.

## Dependencies
- docs/review-actions/PLAN-BBC-2026-03-22.md (BBC baseline scope)
- docs/review-actions/PLAN-BBC-REVIEW-2-ADMISSION-FIX-2026-03-22.md (deterministic admission hardening)
