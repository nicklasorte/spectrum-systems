# Plan — BATCH-DN — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-DN

## Objective
Integrate governed context_bundle_v2, review/eval signals, and failure history into TPA Plan→Build→Simplify→Gate enforcement while preserving deterministic fail-closed control.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-DN-2026-04-03.md | CREATE | Required PLAN-first artifact for this multi-file BUILD scope. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Add context-aware TPA validations for PLAN/BUILD/SIMPLIFY/GATE phases and deterministic context risk gating behavior. |
| contracts/schemas/tpa_slice_artifact.schema.json | MODIFY | Extend TPA artifact contract to carry governed context refs, risk/failure metadata, and gate mitigation signals. |
| contracts/examples/tpa_slice_artifact.json | MODIFY | Keep golden-path contract example aligned with updated TPA plan artifact schema. |
| contracts/standards-manifest.json | MODIFY | Version-bump tpa_slice_artifact contract metadata per contract authority rules. |
| tests/test_tpa_sequence_runner.py | MODIFY | Add deterministic tests for context-aware PLAN/BUILD/SIMPLIFY/GATE behavior and blocking semantics. |

## Contracts touched
- `tpa_slice_artifact` (schema update + standards manifest version bump + example update).

## Tests that must pass after execution
1. `pytest tests/test_tpa_sequence_runner.py`
2. `pytest tests/test_context_selector.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not modify `context_bundle_v2` schema structure in this slice.
- Do not modify non-TPA execution ordering, admission policy, or bundle-state lifecycle behavior.
- Do not add new modules or refactor unrelated runtime codepaths.

## Dependencies
- `docs/review-actions/PLAN-TPA-001-2026-04-03.md` must remain satisfied as the baseline TPA governance layer.
- `docs/review-actions/PLAN-HS-06-2026-03-24.md` context bundle contract remains authoritative input source.

## Context signals (authoritative inputs)
- Context bundle: `context_bundle_v2` refs from slice request and emitted TPA artifacts.
- Review/eval signals: `review_signal_refs` and `eval_signal_refs` surfaced via context bundle and gate payload.
- Failure history: failure pattern refs and recurrence counters supplied in context metadata.
- Risk posture: active risk refs and risk severity flags supplied in context metadata.

## Changed-scope verification plan
- Run `.codex/skills/verify-changed-scope/run.sh` after BUILD and confirm only declared files changed.
