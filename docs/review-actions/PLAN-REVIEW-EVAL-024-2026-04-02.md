# Plan — REVIEW-EVAL-024 — 2026-04-02

## Prompt type
PLAN

## Roadmap item
[REVIEW-EVAL-024] Review Signal → Eval Integration + Failure-Derived Eval Auto-Generation

## Objective
Route review-derived control signals through governed eval artifacts and deterministic failure-derived eval-case generation so control consumes review outcomes through existing eval surfaces without weakening fail-closed behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-REVIEW-EVAL-024-2026-04-02.md | CREATE | Required plan-first artifact for this multi-file foundation-hardening slice. |
| spectrum_systems/modules/runtime/review_eval_bridge.py | CREATE | Deterministic review_control_signal → eval_result/eval_summary adapter and replay-safe canonicalization/hashing. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Wire review-derived eval artifacts into existing control decision path with fail-closed required-signal behavior and precedence safeguards. |
| spectrum_systems/modules/runtime/evaluation_auto_generation.py | MODIFY | Add governed deterministic review-finding → failure-derived eval_case generation with provenance and dedupe. |
| tests/test_review_eval_bridge.py | CREATE | Coverage for deterministic review→eval conversion, fail-closed malformed signal handling, replay determinism, and trace linkage. |
| tests/test_evaluation_control.py | MODIFY | Verify review-derived eval artifacts influence control via normal eval surfaces and that stronger blocking signals are not overridden. |
| tests/test_evaluation_auto_generation.py | MODIFY | Verify critical review findings generate deterministic deduped failure-derived eval cases with provenance. |
| tests/test_review_signal_extractor.py | MODIFY | Add deterministic replay assertion from review markdown to derived review eval_result artifact. |

## Seams impacted
- review signal extraction/consumption seam (`review_control_signal`)
- eval artifact seam (`eval_result` / review-derived summary)
- evaluation control decision seam (`evaluation_control_decision`)
- failure-derived learning seam (`eval_case` generation from review findings)
- replay determinism seam (canonical identity and digest generation)

## Contracts touched
None (existing contracts reused: `review_control_signal`, `eval_result`, `eval_case`, `evaluation_control_decision`).

## Replay/eval/control surfaces affected
- Replay-safe deterministic identity for review-derived eval artifacts.
- Review outcomes represented as governed eval_result artifacts.
- Control consumes review-derived eval status via eval-backed input path while preserving existing direct safeguards.
- Failure-derived review findings emit deterministic eval_case artifacts with explicit provenance and dedupe.

## Validation steps
1. `pytest tests/test_review_eval_bridge.py tests/test_evaluation_control.py tests/test_evaluation_auto_generation.py tests/test_review_signal_extractor.py tests/test_review_control_integration.py`
2. `python scripts/run_contract_enforcement.py`
3. `python scripts/run_contract_preflight.py`
4. `PLAN_FILES="docs/review-actions/PLAN-REVIEW-EVAL-024-2026-04-02.md spectrum_systems/modules/runtime/review_eval_bridge.py spectrum_systems/modules/runtime/evaluation_control.py spectrum_systems/modules/runtime/evaluation_auto_generation.py tests/test_review_eval_bridge.py tests/test_evaluation_control.py tests/test_evaluation_auto_generation.py tests/test_review_signal_extractor.py" .codex/skills/verify-changed-scope/run.sh`
5. `pytest`

## Expected fail-closed behaviors
- Missing required review-derived eval signal keeps decision non-allow (`deny`/`block`).
- Malformed review signal or malformed review-derived eval artifacts raise explicit errors and do not degrade to allow.
- Ambiguous review-finding mapping fails closed (explicit error) rather than guessed eval family assignment.
- Review-derived PASS cannot override stronger pre-existing block/freeze/deny outcomes.

## Expected learning loop additions
- Critical review findings produce deterministic, deduped failure-derived eval_case artifacts.
- Eval cases contain provenance linking review ID, review control signal ID, and finding identity.
- Repeated identical findings stabilize to identical eval_case IDs for recurrence tracking and regression reuse.

## Scope exclusions
- No redesign of control authority or policy precedence model.
- No UI/front-end changes.
- No taxonomy expansion beyond explicit bounded finding→eval-family mappings required for this slice.
- No unrelated runtime refactors outside listed files.

## Dependencies
- Existing `review_control_signal`, `eval_result`, `eval_case`, and `evaluation_control_decision` contracts and loaders.
- Existing deterministic ID utilities and current control fail-closed semantics.
