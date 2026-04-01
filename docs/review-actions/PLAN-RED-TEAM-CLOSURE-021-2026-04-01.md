# Plan — RED-TEAM-CLOSURE-021 — 2026-04-01

## Prompt type
PLAN

## Roadmap item
RED-TEAM-CLOSURE-021 — Post-ALIGNMENT_020 trust-spine hardening bundle

## Objective
Close the highest-signal ALIGNMENT_020 trust-spine gaps by making enforcement non-bypassable on active replay/control surfaces, unifying decision authority precedence, requiring replay evidence for promotion-relevant progression, and adding deterministic proof that enforcement decisions are consumed downstream.

## Findings being closed
- A. Enforcement action recording present but bypassable (legacy/alternate path exposure)
- B. Dual / parallel decision authority across control surfaces
- C. Replay governance defaults allow execution without replay
- D. No proof that emitted enforcement decisions are obeyed
- E. Critical eval coverage gaps remain report-only where trust-spine promotion is concerned (narrow closure if repo-native)

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RED-TEAM-CLOSURE-021-2026-04-01.md | CREATE | Required plan-first artifact for this multi-file hardening bundle. |
| PLANS.md | MODIFY | Register this plan in active plans table per repo convention. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Remove/lock threshold override seam on active control decision builder. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Ensure replay_run path cannot route through legacy enforcement semantics. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Enforce deterministic authority precedence and promotion-time replay/eval/enforcement consumption gates. |
| tests/test_replay_engine.py | MODIFY | Validate replay path uses canonical enforcement chain and blocks bypass behavior. |
| tests/test_sequence_transition_policy.py | MODIFY | Validate promotion blocks on missing replay evidence / enforcement-obedience failures / coverage gaps and deterministic precedence. |
| tests/test_cycle_runner.py | MODIFY | Validate cycle runner trust-spine behavior when tightened sequence transition policy is consumed. |
| tests/fixtures/autonomous_cycle/evaluation_control_decision_allow.json | CREATE | Deterministic allow-path fixture proving promotion proceeds only when authority allows. |
| tests/fixtures/autonomous_cycle/enforcement_result_allow.json | CREATE | Deterministic enforcement allow fixture for obedience proof tests. |

## Contracts touched
None expected (contract fields already available through existing refs and governed artifacts).

## Tests that must pass after execution
1. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight`
2. `pytest tests/test_replay_engine.py`
3. `pytest tests/test_sequence_transition_policy.py`
4. `pytest tests/test_cycle_runner.py`
5. `pytest tests/test_control_loop.py`

## Execution notes
- Preflight will be run early (immediately after initial implementation pass) per preflight-first requirement.
- If touched seams include cycle runner / promotion / replay surfaces, those surfaces will be explicitly revalidated in targeted tests.
- Changed-scope verification will be run after implementation before commit.

## Scope exclusions
- No redesign of architecture or expansion beyond active trust spine hardening.
- No broad vocabulary refactor across all historical control surfaces.
- No new subsystem for eval coverage; only narrow trust-spine promotion gating if already adjacent.
- No schema/version bump unless an unavoidable compatibility break is discovered.

## Dependencies
- ALIGNMENT_020 red-team review artifact (docs/reviews/ALIGNMENT_020_RED_TEAM_REVIEW.md)
- Existing trust-spine modules: evaluation_control, replay_engine, sequence_transition_policy, cycle_runner
