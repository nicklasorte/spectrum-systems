# Governed Prompt Queue Loop Control Report

## Intent
This slice enforces bounded, deterministic repair loop control so prompt queue work items cannot silently re-enter forever. The policy computes a contract-backed decision from generation depth and parent lineage, then queue integration applies a single canonical action (`allow_reentry`, `require_review`, `block_reentry`) that always terminates or escalates within configured bounds.

## Architecture
### Modules created
- `spectrum_systems/modules/prompt_queue/loop_control_policy.py`
- `spectrum_systems/modules/prompt_queue/loop_control_artifact_io.py`
- `spectrum_systems/modules/prompt_queue/loop_control_queue_integration.py`
- `scripts/run_prompt_queue_loop_control.py`

### Generation tracking design
- `generation_count` is added to prompt queue work item schema/model.
- Root work items require `generation_count = 0` and no parent.
- Repair children require strict monotonic lineage: `child.generation_count = parent.generation_count + 1`.
- Missing or invalid lineage fails closed.

### Enforcement mapping
Canonical tuple is now governed by schema and integration guard:
- `within_budget` → `allow_reentry` → `within_budget_allow_reentry`
- `limit_reached` → `require_review` → `limit_reached_require_review`
- `limit_exceeded` → `block_reentry` → `limit_exceeded_block_reentry`

## Guarantees
1. **No infinite loops**: generation budget is enforced; `limit_exceeded` hard-blocks re-entry.
2. **Bounded generation**: every repair child must increment exactly one generation from parent.
3. **Fail-closed lineage safety**: missing generation count, missing parent linkage for non-root, and lineage mismatch all fail closed.
4. **Contract safety**: every loop-control decision artifact validates against `prompt_queue_loop_control_decision` before write.

## Tests mapped to guarantees
- Bounded budget status/action mapping (`within_budget`, `limit_reached`, `limit_exceeded`) validates deterministic enforcement.
- Lineage/generation failures validate fail-closed behavior.
- Schema tuple mismatch and invalid artifact tests validate contract hardening and integration guard.
- Blocked-state child spawn test validates no additional repair child creation after budget exceedance.

## Failure modes not handled in this slice
- Retry scheduling or delayed re-processing.
- Multi-item/global queue fairness strategies.
- External provider execution and runtime backoff behavior.

## Delivery artifact
- File path: `docs/reviews/governed_prompt_queue_loop_control_report.md`
- Commit hash: `RECORDED-IN-GIT-COMMIT-METADATA`
- Blockers: `none`
