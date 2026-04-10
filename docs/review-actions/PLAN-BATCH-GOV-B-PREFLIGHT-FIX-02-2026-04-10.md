# Plan — BATCH-GOV-B-PREFLIGHT-FIX-02 — 2026-04-10

## Prompt type
PLAN

## Objective
Diagnose repeated GOV-B contract preflight BLOCK in pqx_governed PR flow using generated preflight artifacts as source of truth, then apply minimum changes to clear BLOCK without weakening GOV-B authority boundaries.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| .github/workflows/artifact-boundary.yml | MODIFY | Make wrapper generation robust to invalid base/head revision ranges to prevent malformed wrapper BLOCK in pqx_governed flow. |
| tests/test_failure_learning_artifacts.py | MODIFY | Align test setup with GOV-B fail-closed requirement for real review artifacts in closure_decision_pending path. |
| tests/test_pre_pr_repair_loop.py | MODIFY | Align repair-loop tests with strict review artifact prerequisites introduced by GOV-B authority hardening. |
| tests/test_roadmap_signal_generation.py | MODIFY | Preserve roadmap signal assertions while satisfying non-fabricated review artifact inputs. |
| tests/test_system_handoff_integrity.py | MODIFY | Ensure malformed CDE-output test reaches intended `next_step_class` validation boundary under new GOV-B prerequisites. |
| docs/reviews/BATCH-GOV-B-PREFLIGHT-FIX-02-DELIVERY-2026-04-10.md | CREATE | Delivery report with blocker classification, minimum fix, and revalidation status. |

## Scope constraints
- No redesign of GOV-B authority model.
- No weakening of preflight rules.
- No unrelated refactors.
