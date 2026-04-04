# Plan — BATCH-TPA-02 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
TPA-006 through TPA-012

## Objective
Harden the existing PQX-integrated TPA Plan→Build→Simplify→Gate flow so selection, simplicity review, complexity metrics, regression gating, observability, and cleanup-only mode become governed deterministic artifacts.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-02-2026-04-04.md | CREATE | Required written plan before this multi-file BUILD slice. |
| PLANS.md | MODIFY | Register this active plan in the plan index. |
| contracts/schemas/tpa_slice_artifact.schema.json | MODIFY | Extend TPA contract for hardened selection, simplicity review, delete-pass accounting, complexity metrics, cleanup-only mode, and regression gating fields. |
| contracts/schemas/tpa_observability_summary.schema.json | CREATE | Add governed TPA observability/effectiveness summary artifact contract. |
| contracts/examples/tpa_slice_artifact.json | MODIFY | Keep TPA golden example aligned with updated schema requirements. |
| contracts/examples/tpa_observability_summary.json | CREATE | Add example for new TPA observability summary contract. |
| contracts/standards-manifest.json | MODIFY | Version and register updated/new TPA contracts. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Implement deterministic TPA complexity-signal accounting, selection artifact hardening, simplicity review gating, regression gate, observability summary, and cleanup-only mode enforcement. |
| tests/test_tpa_sequence_runner.py | MODIFY | Add deterministic tests covering TPA-006..012 behavior and fail-closed paths. |
| tests/test_contracts.py | MODIFY | Validate new TPA observability contract example. |
| docs/reviews/2026-04-04-tpa-completion-hardening.md | CREATE | Repo-native review record for TPA completion hardening behavior and outcomes. |

## Contracts touched
- `tpa_slice_artifact` (schema version bump)
- `tpa_observability_summary` (new schema)
- `standards_manifest` (new publication metadata)

## Tests that must pass after execution
1. `pytest tests/test_tpa_sequence_runner.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-BATCH-TPA-02-2026-04-04.md`

## Scope exclusions
- Do not redesign PQX sequencing architecture outside the TPA extensions.
- Do not modify unrelated control-loop, roadmap-selection, or queue modules.
- Do not introduce external dependencies for static analysis.

## Dependencies
- `docs/review-actions/PLAN-TPA-001-2026-04-03.md` baseline TPA flow must remain intact.
