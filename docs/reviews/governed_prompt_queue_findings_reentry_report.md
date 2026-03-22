# Governed Prompt Queue Findings Reentry Report

## 1) Intent
This patch delivers the missing live-review loop segment that routes lineage-valid findings (emitted via the review parsing handoff path) back into the existing repair prompt generation path.

Delivered now:
- findings-to-repair reentry validation and lineage enforcement,
- deterministic repair prompt generation reuse,
- schema-backed findings reentry artifact emission,
- deterministic queue/work-item updates.

Deferred for later prompts:
- retries and blocked-item recovery,
- queue-wide scheduling/orchestration,
- provider abstraction expansion,
- downstream automation beyond existing repair prompt path.

## 2) Architecture
### Contracts
- Added `prompt_queue_findings_reentry` schema and example payload.
- Registered contract in standards manifest.
- Added nullable `findings_reentry_artifact_path` to queue work-item/state contracts.

### Modules
- `findings_reentry.py`: pure validation + lineage checks + adapter call into existing `generate_repair_prompt_artifact()`.
- `findings_reentry_artifact_io.py`: pure schema validation + write boundary for reentry artifacts.
- `findings_reentry_queue_integration.py`: pure deterministic queue/work-item mutation, duplicate prevention, and state progression.

### CLI
- `run_prompt_queue_findings_reentry.py`: thin orchestration shell that loads artifacts, executes reentry module, writes artifacts, mutates queue, and exits non-zero on failures.

### Minimal state model change
- Added only one new nullable field on work item/state (`findings_reentry_artifact_path`) to preserve lineage auditability without introducing new state-machine statuses.

## 3) Guarantees
- Only lineage-valid findings from successful invocation + parsing handoff can re-enter repair generation.
- Malformed or incomplete lineage fails closed with explicit errors.
- Reentry artifacts are schema-validated before write.
- Queue/work-item mutations are deterministic and schema-validated.
- No silent continuation occurs without a successfully generated repair prompt artifact.

## 4) Tests mapped to guarantees
- `test_valid_live_findings_reentry_completes_and_links_repair_prompt`:
  proves successful lineage-valid reentry, repair prompt generation, artifact writes, and queue linkage.
- `test_missing_findings_artifact_fails_closed`:
  proves fail-closed behavior for missing findings path.
- `test_missing_handoff_artifact_fails_closed`:
  proves fail-closed behavior when handoff artifact is invalid/missing.
- `test_lineage_mismatch_fails_closed`:
  proves cross-artifact lineage mismatch is rejected.
- `test_repair_prompt_generation_failure_fails_closed`:
  proves repair prompt generation failure halts reentry.
- `test_duplicate_reentry_attempt_is_prevented`:
  proves deterministic duplicate prevention.
- `test_findings_reentry_example_validates_against_schema`:
  proves contract/example conformance.
- `test_queue_update_is_deterministic_and_schema_valid`:
  proves deterministic queue mutation with schema-valid output.

## 5) Failure modes and remaining gaps
Still deferred by design:
- retry strategy and retry scheduling,
- blocked-item recovery policies,
- queue-wide scheduling and prioritization,
- expanded provider abstraction behavior,
- downstream automation and PR/merge orchestration beyond existing paths.

Current failure policy:
- hard fail-closed on missing artifacts, invalid lineage, duplicate reentry, malformed findings, repair-prompt generation failure, or write failures.
