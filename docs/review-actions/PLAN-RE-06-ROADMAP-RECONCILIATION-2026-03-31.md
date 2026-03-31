# Plan — RE-06 Roadmap Reconciliation — 2026-03-31

## Prompt type
PLAN

## Roadmap item
RE-06 — Roadmap authority reconciliation to approved RE-05 corrections

## Objective
Apply the approved RE-05 corrections to the active roadmap authority and compatibility mirror using minimal, compatibility-safe edits that enforce one dominant trust spine and proof-before-scale gating.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RE-06-ROADMAP-RECONCILIATION-2026-03-31.md | CREATE | Required plan-first artifact for multi-file governance update. |
| PLANS.md | MODIFY | Register this active plan in the plan inventory. |
| docs/roadmaps/system_roadmap.md | MODIFY | Reconcile active authority sequencing and hard-gate language to approved RE-05 corrections. |
| docs/roadmap/system_roadmap.md | MODIFY | Mirror strategic sequencing notes in a runtime-safe, compatibility-preserving way. |
| docs/roadmaps/execution_state_inventory.md | MODIFY | Align execution/gap state narrative with revised phase-gated trust spine. |
| docs/roadmaps/2026-03-31-roadmap-transition-note.md | MODIFY | Record transition semantics for proof-before-scale and certification gating. |
| docs/review-actions/2026-03-31-roadmap-generation-delivery-actions.md | MODIFY | Add concise next-checkpoint action aligned with RE-05 sequencing. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_roadmap_authority.py tests/test_roadmap_step_contract.py tests/test_roadmap_tracker.py`
2. `pytest tests/test_pqx_backbone.py tests/test_pqx_bundle_orchestrator.py tests/test_pqx_sequence_runner.py tests/test_pqx_slice_runner.py`
3. `pytest tests/test_prompt_queue_sequence_cli.py tests/test_run_pqx_bundle_cli.py`
4. `python scripts/check_roadmap_authority.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify runtime/module implementation code.
- Do not remove or rename legacy executable IDs/rows in `docs/roadmap/system_roadmap.md`.
- Do not broaden roadmap scope beyond RE-05-approved sequencing corrections.
- Do not weaken tests/checkers to fit documentation changes.

## Dependencies
- RE-05 strategic review artifact (`docs/reviews/2026-03-31-RE-05-strategic-review.md`) remains the correction source of truth.
- Authority bridge semantics in `docs/roadmaps/roadmap_authority.md` remain unchanged and binding.
