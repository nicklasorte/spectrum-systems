# Plan — BATCH-TPA-04 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
TPA-014, TPA-017, TPA-018

## Objective
Make PQX fail-closed on required-scope executions unless TPA lineage artifacts are present, add explicit TPA bypass drift signaling, and support governed lightweight TPA mode with traceability preserved.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-04-2026-04-04.md | CREATE | Required plan artifact for this multi-file BUILD slice. |
| PLANS.md | MODIFY | Register this plan in active plan index. |
| contracts/schemas/tpa_slice_artifact.schema.json | MODIFY | Add `tpa_mode` contract field and lightweight-mode compatibility. |
| contracts/schemas/tpa_observability_summary.schema.json | MODIFY | Add bypass observability metrics/hotspots/offender fields. |
| contracts/schemas/tpa_bypass_drift_signal.schema.json | CREATE | Define deterministic artifact for TPA bypass drift detection output. |
| contracts/examples/tpa_slice_artifact.json | MODIFY | Align example with new required `tpa_mode` field. |
| contracts/examples/tpa_observability_summary.json | MODIFY | Align example with bypass observability additions. |
| contracts/examples/tpa_bypass_drift_signal.json | CREATE | Add example for new bypass drift signal contract. |
| contracts/standards-manifest.json | MODIFY | Register schema updates/new artifact publication metadata. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Enforce required-scope TPA routing, bypass detection drift artifacts, and lightweight-mode fail-closed behavior. |
| tests/test_tpa_sequence_runner.py | MODIFY | Add routing/bypass/lightweight/fail-closed tests. |
| tests/test_contracts.py | MODIFY | Validate new/updated TPA contracts and examples. |

## Contracts touched
- `tpa_slice_artifact` (schema version bump)
- `tpa_observability_summary` (schema version bump)
- `tpa_bypass_drift_signal` (new schema)
- `standards_manifest` (publication metadata update)

## Tests that must pass after execution
1. `pytest tests/test_tpa_sequence_runner.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-BATCH-TPA-04-2026-04-04.md`

## Scope exclusions
- Do not redesign broader PQX orchestration architecture outside TPA routing/enforcement seams.
- Do not modify unrelated roadmap, operator, or non-TPA governance contracts.
- Do not relax existing TPA-03 enforcement semantics.

## Dependencies
- Existing TPA Plan→Build→Simplify→Gate enforcement from prior slices must remain intact.
