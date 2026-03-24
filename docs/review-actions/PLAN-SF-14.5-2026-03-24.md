# Plan — SF-14.5 — 2026-03-24

## Prompt type
PLAN

## Roadmap item
SF-14.5a–d — Release/Canary hardening standards layer

## Objective
Implement a surgical trust-hardening layer that standardizes deterministic IDs, decision precedence, indeterminate handling, and coverage parity enforcement across SF-14 release/canary and adjacent governance paths without architectural redesign.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SF-14.5-2026-03-24.md | CREATE | Required PLAN artifact before multi-file BUILD changes |
| PLANS.md | MODIFY | Register active SF-14.5 plan in active plans table |
| spectrum_systems/utils/__init__.py | CREATE | Repo-native shared utils package surface |
| spectrum_systems/utils/deterministic_id.py | CREATE | Canonical deterministic identity utility for governance artifacts |
| spectrum_systems/modules/runtime/decision_precedence.py | CREATE | Canonical precedence standard + helper mapping |
| spectrum_systems/modules/runtime/release_canary.py | MODIFY | Enforce precedence helper, indeterminate defaults, and coverage parity checks |
| scripts/run_release_canary.py | MODIFY | Replace uuid-based release identity with deterministic ID utility |
| scripts/run_eval_ci_gate.py | MODIFY | Use deterministic gate IDs and canonical indeterminate blocking semantics |
| scripts/run_eval_coverage_report.py | MODIFY | Use deterministic coverage run IDs and canonical indeterminate policy handling |
| data/policy/eval_release_policy.json | MODIFY | Align release policy knobs for indeterminate and coverage parity semantics |
| data/policy/eval_ci_gate_policy.json | MODIFY | Add explicit indeterminate default policy knob |
| data/policy/eval_coverage_policy.json | MODIFY | Align explicit indeterminate blocking/fail-closed semantics |
| tests/test_release_canary.py | MODIFY | Add coverage parity, precedence, and deterministic behavior assertions |
| tests/test_eval_ci_gate.py | MODIFY | Add policy override test for indeterminate handling and deterministic IDs |
| tests/test_eval_coverage_report.py | MODIFY | Add indeterminate policy alias behavior assertions |
| tests/test_control_loop_chaos.py | MODIFY | Add explicit precedence helper conformance checks |
| tests/test_deterministic_id.py | CREATE | Verify deterministic ID utility stability and canonicalization |
| docs/reliability/control-precedence.md | MODIFY | Document canonical precedence order and term mapping |
| docs/reliability/release-and-canary-policy.md | MODIFY | Document deterministic IDs, precedence, indeterminate defaults, and coverage parity |
| docs/reliability/eval-ci-gate.md | MODIFY | Document canonical indeterminate blocking semantics + override behavior |
| docs/reliability/eval-coverage-and-slices.md | MODIFY | Document canonical indeterminate and slice parity semantics |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_deterministic_id.py`
2. `pytest tests/test_release_canary.py tests/test_eval_ci_gate.py tests/test_eval_coverage_report.py tests/test_control_loop_chaos.py`
3. `PLAN_FILES="docs/review-actions/PLAN-SF-14.5-2026-03-24.md PLANS.md spectrum_systems/utils/__init__.py spectrum_systems/utils/deterministic_id.py spectrum_systems/modules/runtime/decision_precedence.py spectrum_systems/modules/runtime/release_canary.py scripts/run_release_canary.py scripts/run_eval_ci_gate.py scripts/run_eval_coverage_report.py data/policy/eval_release_policy.json data/policy/eval_ci_gate_policy.json data/policy/eval_coverage_policy.json tests/test_release_canary.py tests/test_eval_ci_gate.py tests/test_eval_coverage_report.py tests/test_control_loop_chaos.py tests/test_deterministic_id.py docs/reliability/control-precedence.md docs/reliability/release-and-canary-policy.md docs/reliability/eval-ci-gate.md docs/reliability/eval-coverage-and-slices.md" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign eval, control, release, or SBGE architecture.
- Do not add dashboards/UI, trust score systems, capacity/cost logic, or speculative scoring.
- Do not refactor unrelated modules or convert the entire repository to new ID helpers.
- Do not modify contracts/schemas in this slice.

## Dependencies
- SF-05 implementation remains the canonical eval execution path.
- SF-07 coverage/slice artifacts remain the canonical source for slice governance.
- SF-12 control-loop deterministic behavior remains unchanged except precedence explicitness.
- SF-14 release/canary flow remains the canonical release decision path.
