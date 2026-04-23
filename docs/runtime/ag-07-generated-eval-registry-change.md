# AG-07 generated eval registry-change path

## Purpose

This path gives an admitted generated eval candidate one narrow way to request a required eval registry change, receive review, produce an execution result, and support reversal.

## Sequence

1. Emit `generated_eval_registry_change_request_record`.
2. Emit `generated_eval_registry_change_review_record` with `review_outcome` set to `ready` or `not_ready`.
3. Run one execution function that emits `generated_eval_registry_change_execution_record` in all outcomes.
4. If needed, emit `generated_eval_registry_change_reversal_record` with `reversal_reason=manual_registry_revert`.

## One-path rule

Only one execution function performs registry-change evaluation. The function is deterministic and keeps lineage across failure, generated eval case, request, review, and execution records.

## Replay validation requirement

Replay validation is explicit. Replay mismatch blocks registry update and records `replay_validation_passed=false` with a blocking reason.

## Fail-closed behavior

The execution record blocks updates when any required input is missing, admission did not succeed, linkage is mismatched, threshold is not met, review is not `ready`, or replay validation fails.

No silent registry update is allowed.
