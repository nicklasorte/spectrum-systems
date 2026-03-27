---
module: control_loop_budget
review_type: fpo_targeted_correctness
review_date: 2026-03-27
reviewer: Claude
decision: FAIL
trust_assessment: medium
status: final
related_plan: docs/review-actions/PLAN-PQX-CLT-002-2026-03-27.md
source_review_output: docs/reviews/2026-03-27-budget-control-loop-review.md
normalized_decision: pass_with_fixes
---

## Scope
Target files reviewed:
- `spectrum_systems/modules/runtime/control_loop.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/agent_golden_path.py`
- `tests/test_control_loop_chaos.py`
- `tests/test_eval_ci_gate.py`
- `tests/helpers/replay_result_builder.py`
- `contracts/schemas/evaluation_control_decision.schema.json`

## Decision
- Normalized decision: `pass_with_fixes`
- Schema decision: `FAIL`

## Trust Assessment
- Trust assessment: `medium`

## Critical Findings
- **F-001** (critical, S1): [S1] Budget warning path may downgrade deny outcomes in reviewed slice output.
- **F-002** (high, S2): [S2] Builder updates objective observed_value without recomputing aggregate budget status fields.
- **F-003** (high, S2): [S2] CI gate lacks direct tests for warning/exhausted/invalid budget states.

## Required Fixes
- **FIX-001** (P0): Prevent warning-state override from weakening deny decisions in evaluation control.
- **FIX-002** (P1): Recompute aggregate budget fields in replay builder after objective edits.
- **FIX-003** (P1): Add CI gate tests covering warning/exhausted/invalid budget paths.

## Optional Improvements
- Track schema constraints linking decision and system_response to prevent drift.

## Failure Mode Summary
Targeted budget-control review passed core architecture but identified fail-open and coverage defects requiring remediation.
