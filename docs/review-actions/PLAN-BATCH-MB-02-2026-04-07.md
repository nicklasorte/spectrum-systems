# Plan — BATCH-MB-02 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-MB-02 (GHA-11, GHA-12)

## Objective
Harden PR promotion gating so merge-ready surfacing requires certified governed evidence, and provide deterministic end-to-end scenario proof for clean/repair/escalated/exhausted/roadmap command paths.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-MB-02-2026-04-07.md | CREATE | Required plan-first artifact for this multi-file + contract change. |
| contracts/schemas/promotion_gate_decision_artifact.schema.json | CREATE | Canonical schema for deterministic promotion gate decision artifact. |
| contracts/examples/promotion_gate_decision_artifact.json | CREATE | Golden-path example for promotion gate decision artifact contract. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump manifest publication metadata version. |
| spectrum_systems/modules/runtime/github_closure_continuation.py | MODIFY | Emit promotion gate decision artifact; enforce certified governed evidence before branch-update eligibility. |
| spectrum_systems/modules/runtime/github_pr_feedback.py | MODIFY | Consume promotion gate decision artifact and render unambiguous promotion visibility states. |
| tests/test_github_closure_continuation.py | MODIFY | Add hardening coverage for promotion decision artifact, evidence requirements, and non-ready branch policy. |
| tests/test_github_pr_feedback.py | MODIFY | Add feedback rendering coverage for promotion-ready vs status-only visibility. |
| tests/test_promotion_gate_decision.py | CREATE | Focused deterministic unit tests for promotion gate decisioning rules. |
| tests/test_end_to_end_governed_scenarios.py | CREATE | Canonical scenario pack proving governed loop paths and deterministic replay. |
| tests/test_pr_promotion_hardening.py | CREATE | Focused hardening coverage for PR promotion gating invariants. |

## Contracts touched
- Create `promotion_gate_decision_artifact` schema (`contracts/schemas/promotion_gate_decision_artifact.schema.json`).
- Register `promotion_gate_decision_artifact` in `contracts/standards-manifest.json`.

## Tests that must pass after execution
1. `pytest tests/test_promotion_gate_decision.py`
2. `pytest tests/test_pr_promotion_hardening.py`
3. `pytest tests/test_end_to_end_governed_scenarios.py`
4. `pytest tests/test_github_closure_continuation.py tests/test_github_pr_feedback.py tests/test_top_level_conductor.py`
5. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not introduce any new subsystem/acronym beyond existing runtime boundaries.
- Do not move business logic into GitHub workflow YAML.
- Do not alter CDE/TLC/PQX/SEL ownership boundaries.
- Do not perform unrelated refactors outside declared files.

## Dependencies
- Existing governed continuation path from prior GHA batches must remain intact and is consumed as-is.
- Existing certification artifacts (`top_level_conductor_run_artifact`, `closure_decision_artifact`, `repair_attempt_record_artifact`) are reused as promotion evidence inputs.
