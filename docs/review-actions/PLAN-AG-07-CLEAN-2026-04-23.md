# PLAN

## Prompt Type
BUILD

## Work Item
AG-07-CLEAN

## Scope
Implement a narrow generated eval registry-change path limited to request, review, execution, and reversal artifacts plus minimal runtime and test coverage.

## Files
- contracts/examples/generated_eval_registry_change_request_record.json
- contracts/examples/generated_eval_registry_change_review_record.json
- contracts/examples/generated_eval_registry_change_execution_record.json
- contracts/examples/generated_eval_registry_change_reversal_record.json
- contracts/schemas/generated_eval_registry_change_request_record.schema.json
- contracts/schemas/generated_eval_registry_change_review_record.schema.json
- contracts/schemas/generated_eval_registry_change_execution_record.schema.json
- contracts/schemas/generated_eval_registry_change_reversal_record.schema.json
- contracts/standards-manifest.json
- spectrum_systems/modules/runtime/failure_eval_generation.py
- tests/test_failure_eval_generation.py
- tests/test_generated_eval_registry_change_surface_vocabulary.py
- docs/runtime/ag-07-generated-eval-registry-change.md

## Steps
1. Add four contract schemas and examples with fail-closed constraints and deterministic artifact identifiers.
2. Register all four artifacts in the standards manifest with a single version increment.
3. Add one runtime execution path and one reversal path that always emit records and block on missing conditions.
4. Add narrow tests for contract validation, block conditions, success path, deterministic reversal, and vocabulary guard.
5. Run targeted tests and required contract checks.
