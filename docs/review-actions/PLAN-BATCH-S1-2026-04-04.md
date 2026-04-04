# Plan — BATCH-S1 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-S1 — Trust Boundary Hardening (REPORT-003 + ST-01)

## Objective
Harden the Review → Eval → Control trust boundary and persist the canonical self-testing architecture without expanding runtime capability.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-S1-2026-04-04.md | CREATE | Required plan-first artifact for this multi-file hardening batch |
| PLANS.md | MODIFY | Register the active BATCH-S1 plan |
| spectrum_systems/modules/runtime/review_signal_extractor.py | MODIFY | Determinism/fail-closed hardening for review-derived signal extraction |
| spectrum_systems/modules/runtime/review_eval_bridge.py | MODIFY | Determinism and review eval bridge hardening |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Precedence and fail-closed hardening for Review → Eval → Control gating |
| spectrum_systems/modules/runtime/evaluation_auto_generation.py | MODIFY | Fail-closed review eval-family mapping and deterministic dedupe hardening |
| tests/test_review_eval_bridge.py | MODIFY | Add coverage for deterministic ordering/fail-closed review bridge behavior |
| tests/test_evaluation_control.py | MODIFY | Add precedence integrity and fail-closed trust-boundary tests |
| tests/test_evaluation_auto_generation.py | MODIFY | Add eval-family token and dedupe-order hardening tests |
| docs/reviews/review_eval_hardening_report.md | CREATE | REPORT-003 audit evidence and minimal-fix record |
| docs/architecture/self_testing_system.md | CREATE | ST-01 canonical self-testing architecture definition |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_review_eval_bridge.py`
2. `pytest tests/test_evaluation_control.py`
3. `pytest tests/test_evaluation_auto_generation.py`
4. `pytest tests/test_contracts.py`
5. `pytest tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `pytest`
8. `python scripts/run_contract_preflight.py --base-ref HEAD~1 --head-ref HEAD --output-dir outputs/contract_preflight`
9. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-BATCH-S1-2026-04-04.md`

## Scope exclusions
- Do not modify control decision ordering outside trust-boundary hardening requirements.
- Do not modify PQX execution logic or cycle runner behavior.
- Do not modify roadmap authority logic.
- Do not add new runtime capability beyond hardening, determinism, and audit artifacts.

## Dependencies
- Existing replay/evaluation control contracts and examples must remain valid.
