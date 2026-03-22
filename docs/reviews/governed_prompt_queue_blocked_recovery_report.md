# Governed Prompt Queue Blocked Recovery — Implementation Report

## Intent
This patch delivers the blocked-item recovery policy slice for governed prompt queue operability. It adds deterministic blocked-item classification, schema-backed recovery decision artifacts, bounded queue mutation for explicitly recoverable cases, and a thin CLI for operational execution.

Delivered now:
- Blocked item recovery classification policy (recoverable/manual-review/non-recoverable)
- Recovery decision contract + example + manifest registration
- Recovery decision artifact validation and IO boundary
- Deterministic queue integration that only unblocks explicit recoverable decisions
- Focused fail-closed tests

Deferred for later prompts:
- Retry behavior and retry scheduling
- Queue-wide scheduling/orchestration
- Operator UI/tooling and dashboards
- Provider abstraction expansion for recovery automation

## Architecture
### Contracts and examples
- Added `contracts/schemas/prompt_queue_blocked_recovery_decision.schema.json`.
- Added `contracts/examples/prompt_queue_blocked_recovery_decision.json`.
- Updated `contracts/standards-manifest.json` with contract registry entry and version bump.
- Added `blocked_recovery_decision_artifact_path` to queue work-item/state contracts and examples.

### Modules
- `spectrum_systems/modules/prompt_queue/blocked_recovery_policy.py`
  - Pure policy classification using deterministic reason-code mapping.
  - Builds lineage-preserving decision artifact.
- `spectrum_systems/modules/prompt_queue/blocked_recovery_artifact_io.py`
  - Validates against contract before write.
  - Writes only to explicit output path.
- `spectrum_systems/modules/prompt_queue/blocked_recovery_queue_integration.py`
  - Applies queue/work-item mutation only when recoverable.
  - Fail-closed on invalid lineage, state, action, or duplicate attempts.

### State model changes
- Minimal additive model extension only:
  - `blocked_recovery_decision_artifact_path` added as nullable field to work item model/schema.
- No new broad recovery workflow state machine added.

## Guarantees
- Only explicitly classified `recoverable` blocked items can transition out of `blocked`.
- `manual_review_required` and `non_recoverable` decisions remain blocked with `no_action`.
- Recovery decision artifacts are schema-validated before write.
- Queue/work-item updates are deterministic and fail closed on invalid input.
- No silent unblock and no forward jump occurs without explicit policy support.

## Tests
- Added focused test suite: `tests/test_prompt_queue_blocked_recovery.py`.
- Covers:
  - recoverable path returns to explicit prior state,
  - manual-review path remains blocked,
  - non-recoverable path remains blocked,
  - missing lineage evidence fails closed,
  - unsupported recovery action fails closed,
  - malformed work item fails closed,
  - schema validation for recovery decision contract,
  - deterministic queue and item updates,
  - deterministic duplicate recovery-attempt prevention.

## Failure modes and gaps
Still intentionally out of scope:
- Retries and retry scheduling
- Blocked-item operator tooling
- Queue scheduling and fleet orchestration
- Provider abstraction expansion for recovery operations
- Deferred autonomy enhancements

## Changed-scope verification
- Verification command executed with declared file set and passed after reverting undeclared generated report/graph outputs.
