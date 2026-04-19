# EVAL-AUTO-01 — Deterministic failure → eval generation

## Purpose
EVAL-AUTO-01 adds a thin learning-loop extension that converts runtime `failure_record` artifacts into governed, replayable eval candidates.

This slice moves failures from passive observation into durable prevention candidates while preserving:
- artifact-first execution
- fail-closed behavior
- clean authority boundaries (generation/admission only; no promotion decisioning)

## Generated artifact: `generated_eval_case`
`generated_eval_case` is a deterministic transformation output from one `failure_record`.

Required shape:
- `artifact_type` (`generated_eval_case`)
- `artifact_id` (canonical hash id)
- `source_failure_artifact_id`
- `trace_id`
- `run_id`
- `reason_code`
- `scenario_name`
- `scenario_description`
- `input_conditions`
- `expected_outcome`
- `expected_reason_code`
- `replay_required`
- `determinism_requirements`
- `created_at`

Key semantics:
- `expected_outcome` is bounded (`halt_with_reason_code:*`, `pause_with_reason_code:*`, or `fail_closed_with_reason_code:*`).
- `expected_reason_code` must stay linked to the source failure `reason_code` unless explicit normalization metadata is present.
- `replay_required` defaults to `true`.

## Deterministic generation logic
Generator: `spectrum_systems/modules/runtime/failure_eval_generation.py`

Rules:
1. Derive `scenario_name` from normalized `failure_state + reason_code`.
2. Derive `expected_outcome` from observed failure state (`halted`, `paused`, `failed_closed`).
3. Carry source linkage (`source_failure_artifact_id`, trace/run IDs, reason code).
4. Include replay-relevant context (`stage`, `missing_artifacts`, `failed_evals`).
5. Produce deterministic IDs using canonical JSON hashing.

No model inference is required.

## Admission: fail-closed eval candidate check
Admission output artifact: `generated_eval_admission_record`.

Admission rejects generated eval cases when any of the following is true:
- required fields are missing
- determinism requirements are absent
- expected outcome is missing
- reason-code linkage is broken without normalization proof
- source failure lineage is missing or mismatched
- replay-required case lacks sufficient replay material
- reason-code normalization mapping is incomplete or inconsistent when reason codes differ
- `expected_outcome` is outside the bounded pattern set:
  - `halt_with_reason_code:<reason_code>`
  - `pause_with_reason_code:<reason_code>`
  - `fail_closed_with_reason_code:<reason_code>`

This yields explicit denial reasons and `admitted=false`.

## Integration point (thin)
`generate_and_admit_failure_eval()` returns both artifacts in one deterministic bundle:
- `generated_eval_case`
- `generated_eval_admission_record`

This is an additive surfacing point for future prevention and promotion workflows.

## Out of scope
This slice does **not**:
- auto-promote generated evals into required eval coverage
- auto-edit canonical registries beyond contract registration
- alter policy/promotion authority logic

## Future path
A later governed slice can consume admitted `generated_eval_case` artifacts to support recurrence prevention and promotion discipline once certification policy explicitly authorizes that path.
