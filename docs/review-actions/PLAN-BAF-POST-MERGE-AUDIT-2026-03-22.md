# Plan — BAF Post-Merge Audit — 2026-03-22

## Prompt type
PLAN

## Roadmap item
BAF — Enforcement Wiring post-merge audit

## Objective
Audit BAF enforcement wiring for remaining fail-open seams and apply only minimal fail-closed fixes if concrete defects are confirmed.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAF-POST-MERGE-AUDIT-2026-03-22.md | CREATE | Required plan artifact for scoped multi-file audit and validation work. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Apply narrow boundary-parity fix only if replay path is less strict than runtime control boundary. |
| tests/test_replay_engine.py | MODIFY | Add focused regression test proving any confirmed replay boundary defect and fix. |
| docs/reviews/2026-03-22-baf-post-merge-audit.md | CREATE | Required audit review artifact with findings, test evidence, and commit hash. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_replay_engine.py`
2. `pytest tests/test_control_integration.py tests/test_enforcement_engine.py tests/test_evaluation_control.py`
3. `PLAN_FILES="docs/review-actions/PLAN-BAF-POST-MERGE-AUDIT-2026-03-22.md spectrum_systems/modules/runtime/replay_engine.py tests/test_replay_engine.py docs/reviews/2026-03-22-baf-post-merge-audit.md" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not refactor unrelated runtime modules.
- Do not change schemas, manifests, or architecture.
- Do not alter non-BAF control-chain surfaces.

## Dependencies
- Existing BAF hardening patch state on branch (replay/control/enforcement/evaluation_control updates) must be present.
