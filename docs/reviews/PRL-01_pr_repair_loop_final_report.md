# PRL-01 Final Report

Built governed two-attempt PR repair loop artifacts, deterministic runtime helper, CLI runner, tests, and red-team/fix-action documentation.

## Max-attempt behavior
- Hard cap max_attempts=2 in schemas and code.
- Attempt 2 unresolved emits human_review_required.

## Allowed repair classes
- authority_shape_violation
- authority_leak_observation
- pytest_selection_missing
- schema_validation_failure (examples/fixtures scoped)

## Blocked repair classes
- unknown_failure and broad/high-risk classes route to human_review_required.

## Authority boundaries
PRL remains observation-only and records CDE/SEL inputs without claiming authority.

## Red-team findings and fixes
All must_fix findings in red-team document were implemented in this same PR and tracked in fix actions.

## Tests run
See command log in PR body.

## Remaining risks
Classifier coverage remains intentionally conservative.

## Next step
Add optional workflow_dispatch integration for artifact harvesting only.
