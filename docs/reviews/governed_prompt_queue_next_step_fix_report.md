# Governed Prompt Queue Next-Step Semantic Integrity Fix Report

## 1) Intent
This patch closes the semantic-integrity gap for next-step orchestration by enforcing one canonical tuple per decision path:

- `decision_status`
- `action_status`
- `action_reason_code`

The integration layer now fails closed before any queue mutation or child-spawn operation when an incoming next-step action artifact is schema-valid at the enum level but semantically inconsistent with the canonical tuple mapping.

## 2) Architecture
### Changed files
- `spectrum_systems/modules/prompt_queue/next_step_queue_integration.py`
- `contracts/schemas/prompt_queue_next_step_action.schema.json`
- `contracts/standards-manifest.json`
- `tests/test_prompt_queue_next_step.py`

### Canonical tuple enforcement in integration
`apply_next_step_action_to_queue()` now validates the full decision/action/reason tuple using deterministic canonical mapping prior to transition logic, queue mutation, or child spawning. It fails closed on mismatch.

### Schema-level tuple constraints
The next-step action schema now includes explicit `allOf` + `if`/`then` branches binding each `decision_status` to exactly one allowed `action_status` and `action_reason_code`.

### Focused negative tests
Focused fail-closed tests cover semantically inconsistent but enum-valid tuple mismatches and assert that no queue mutation occurs and no child is spawned when rejected.

## 3) Guarantees
- Semantically inconsistent next-step artifacts fail closed.
- Child spawning cannot occur from a mismatched terminal decision tuple.
- Audit reason codes are deterministically bound to canonical decision/action paths.

## 4) Tests
### New mismatch-blocking tests
- `test_integration_rejects_complete_with_spawn_review_tuple_mismatch`
  - Blocks `complete` + `spawn_review`.
- `test_integration_rejects_review_required_with_marked_complete_tuple_mismatch`
  - Blocks `review_required` + `marked_complete`.
- `test_integration_rejects_reentry_blocked_with_non_blocked_reason_code`
  - Blocks `reentry_blocked` with non-blocked reason code.
- `test_integration_rejects_mismatched_reason_code_for_valid_decision_action_pair`
  - Blocks mismatched reason code on otherwise valid decision/action pair.

Each test verifies fail-closed behavior before queue mutation and before child spawn.

## 5) Failure modes and gaps
- This fix intentionally does not change retry/scheduling policies or broader queue architecture.
- The semantic tuple mapping is duplicated across orchestrator, integration, and schema by design for layered enforcement; future mapping additions require synchronized updates across all three surfaces.
- This patch hardens canonical tuple integrity for this next-step slice only.

## 6) Delivery artifact
- Report path: `docs/reviews/governed_prompt_queue_next_step_fix_report.md`
- Commit target: `docs(review): add next-step orchestration fix report`
- Blockers: None
