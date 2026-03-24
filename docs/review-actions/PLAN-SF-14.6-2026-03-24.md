# Plan — SF-14.6 — 2026-03-24

## Prompt type
PLAN

## Roadmap item
SF-14.6 — Script/module boundary cleanup, dependency/bootstrap lock, and artifact envelope consistency

## Objective
Eliminate script-to-script imports, enforce one dependency bootstrap path across local+CI, and align core governance artifact envelope fields without changing governance decision semantics.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SF-14.6-2026-03-24.md | CREATE | Required PLAN artifact before multi-file BUILD changes |
| PLANS.md | MODIFY | Register SF-14.6 active plan |
| spectrum_systems/modules/evaluation/eval_coverage_reporting.py | CREATE | Move shared eval coverage builder logic from script into module |
| scripts/run_eval_coverage_report.py | MODIFY | Convert to thin CLI wrapper importing module |
| scripts/run_release_canary.py | MODIFY | Import coverage builder from module, remove script-to-script import |
| scripts/run_eval_ci_gate.py | MODIFY | Align envelope field usage for gate artifact |
| spectrum_systems/modules/runtime/release_canary.py | MODIFY | Align release artifact envelope fields |
| spectrum_systems/modules/runtime/control_loop_chaos.py | MODIFY | Align chaos summary envelope fields |
| contracts/schemas/evaluation_release_record.schema.json | MODIFY | Add envelope-consistent id/trace reference fields |
| contracts/schemas/evaluation_ci_gate_result.schema.json | MODIFY | Add envelope-consistent id/trace reference fields |
| contracts/schemas/eval_coverage_summary.schema.json | MODIFY | Add envelope-consistent id/trace reference fields |
| contracts/examples/evaluation_release_record.json | MODIFY | Keep example aligned with schema envelope |
| contracts/examples/evaluation_ci_gate_result.json | MODIFY | Keep example aligned with schema envelope |
| contracts/examples/eval_coverage_summary.json | MODIFY | Keep example aligned with schema envelope |
| scripts/verify_environment.py | MODIFY | Add explicit critical-package bootstrap verification |
| .github/workflows/release-canary.yml | MODIFY | Use canonical dependency bootstrap + verification |
| .github/workflows/lifecycle-enforcement.yml | MODIFY | Ensure all jobs use canonical dependency bootstrap + verification |
| tests/test_eval_coverage_report.py | MODIFY | Update imports and envelope assertions |
| tests/test_release_canary.py | MODIFY | Envelope assertions for evaluation_release_record |
| tests/test_eval_ci_gate.py | MODIFY | Envelope assertions for evaluation_ci_gate_result |
| tests/test_control_loop_chaos.py | MODIFY | Envelope assertions for chaos summary |
| tests/test_script_module_boundaries.py | CREATE | Enforce no script importing from scripts package |
| tests/test_verify_environment.py | MODIFY | Validate expanded dependency verification behavior |
| docs/reliability/release-and-canary-policy.md | MODIFY | Document module boundary + envelope expectations |
| docs/reliability/eval-ci-gate.md | MODIFY | Document bootstrap contract + envelope expectations |
| docs/reliability/eval-coverage-and-slices.md | MODIFY | Document module boundary + envelope expectations |

## Contracts touched
- `contracts/schemas/evaluation_release_record.schema.json` (non-breaking additive fields)
- `contracts/schemas/evaluation_ci_gate_result.schema.json` (non-breaking additive fields)
- `contracts/schemas/eval_coverage_summary.schema.json` (non-breaking additive fields)

## Tests that must pass after execution
1. `pytest tests/test_script_module_boundaries.py`
2. `pytest tests/test_verify_environment.py tests/test_eval_coverage_report.py tests/test_eval_ci_gate.py tests/test_release_canary.py tests/test_control_loop_chaos.py`
3. `python scripts/verify_environment.py`
4. `python scripts/run_eval_coverage_report.py --output-dir outputs/eval_coverage_plan_check`
5. `python scripts/run_eval_ci_gate.py --output-dir outputs/eval_ci_gate_plan_check`
6. `python scripts/run_release_canary.py --baseline-version baseline --candidate-version candidate --baseline-prompt-version-id prompt-a --candidate-prompt-version-id prompt-b --baseline-schema-version schema-a --candidate-schema-version schema-b --baseline-policy-version-id policy-a --candidate-policy-version-id policy-b --output-dir outputs/release_canary_plan_check`

## Scope exclusions
- Do not change release/canary/eval/control decision semantics or policy thresholds.
- Do not redesign architecture beyond script→module extraction and wiring.
- Do not add UI/dashboard/performance work.
- Do not modify unrelated modules, contracts, or workflows.

## Dependencies
- docs/review-actions/PLAN-SF-14-2026-03-24.md
- docs/review-actions/PLAN-SF-14.5-2026-03-24.md
