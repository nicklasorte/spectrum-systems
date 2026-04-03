# Plan — MAP-003 + MAP-004 + MAP-DOC — 2026-04-03

## Prompt type
PLAN

## Roadmap item
MAP-003 — PQX Integration + Slice Gating; MAP-004 — Roadmap Generator Integration; MAP-DOC — Process Flow Document Generation

## Objective
Make repo review state control PQX slice progression, derive roadmap decisions from governed review artifacts, and emit a deterministic human-readable process-flow document from runtime artifacts.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-MAP-003-MAP-004-MAP-DOC-2026-04-03.md | CREATE | Required plan-first artifact before multi-file BUILD work. |
| PLANS.md | MODIFY | Register this active MAP plan in the plan ledger. |
| contracts/schemas/repo_review_snapshot.schema.json | MODIFY | Add governed structured roadmap handoff payload required by MAP-004 extraction. |
| contracts/examples/repo_review_snapshot.json | MODIFY | Keep golden-path snapshot example aligned with updated schema fields. |
| contracts/standards-manifest.json | MODIFY | Version-bump manifest entry for repo_review_snapshot schema change. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Enforce review-gated progression using repo review + eval/control artifacts with allow/warn/freeze/block behavior. |
| spectrum_systems/modules/runtime/review_roadmap_generator.py | CREATE | Deterministic review-artifact-driven roadmap extraction + sequencing enforcement module. |
| spectrum_systems/modules/runtime/repo_process_flow_doc.py | CREATE | Deterministic generator for docs/reviews/repo_process_flow.md from governed artifacts. |
| docs/reviews/repo_process_flow.md | CREATE | Generated MAP-DOC human-readable process flow output artifact. |
| scripts/run_map_review_orchestration.py | CREATE | Deterministic MAP runner that wires review->eval/control->roadmap->PQX gating->process-flow document emission. |
| tests/test_pqx_sequence_runner.py | MODIFY | Add MAP-003 gating coverage (valid review, missing review, freeze/block behavior, determinism). |
| tests/test_review_roadmap_generator.py | CREATE | Add MAP-004 extraction, sequencing, and unsafe-readiness behavior tests. |
| tests/test_repo_process_flow_doc.py | CREATE | Add MAP-DOC deterministic generation and weak-point derivation tests. |

## Contracts touched
- `contracts/schemas/repo_review_snapshot.schema.json` (additive structured handoff field)
- `contracts/standards-manifest.json` (repo_review_snapshot last_updated_in bump)

## Tests that must pass after execution
1. `pytest tests/test_repo_health_eval.py tests/test_pqx_sequence_runner.py tests/test_review_roadmap_generator.py tests/test_repo_process_flow_doc.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `PLAN_FILES='docs/review-actions/PLAN-MAP-003-MAP-004-MAP-DOC-2026-04-03.md PLANS.md contracts/schemas/repo_review_snapshot.schema.json contracts/examples/repo_review_snapshot.json contracts/standards-manifest.json spectrum_systems/modules/runtime/pqx_sequence_runner.py spectrum_systems/modules/runtime/review_roadmap_generator.py spectrum_systems/modules/runtime/repo_process_flow_doc.py docs/reviews/repo_process_flow.md scripts/run_map_review_orchestration.py tests/test_pqx_sequence_runner.py tests/test_review_roadmap_generator.py tests/test_repo_process_flow_doc.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign PQX architecture or create a parallel orchestration path.
- Do not add non-governed free-text decision logic.
- Do not modify unrelated roadmap, cycle-runner, or promotion modules.

## Dependencies
- MAP-001 + MAP-002 baseline (`repo_review_snapshot` + `repo_health_eval`) must be present and remain authoritative.
