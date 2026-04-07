# HNX Long-Running Execution (HR-B)

## Why HNX now owns time/continuity
HR-A established HNX as the canonical structure spine (`stage_contract` + runtime seam). HR-B extends that same canonical surface to continuity semantics so checkpoint/resume/async-wait/reset-handoff behavior is policy-bound, deterministic, and artifact-first.

This prevents subsystem-specific continuation semantics from drifting across PQX, prompt-queue, and sequence orchestration paths.

## Canonical artifact set
HR-B introduces four canonical continuity artifacts:

- `checkpoint_record`
- `resume_record`
- `async_wait_record`
- `handoff_artifact`

Each is schema-bound (JSON Schema Draft 2020-12), fail-closed by default, and trace-linked.

## Reset vs continuous execution
`stage_contract.execution_mode` is authoritative:

- `continuous`: stage may continue via governed checkpoint/resume/async semantics.
- `reset_with_handoff`: continuation requires governed `handoff_artifact` validation.

No hidden continuity state is permitted.

## Resume validation rules
`stage_contract.resume_policy` defines deterministic inputs:

- `allowed`
- `validation_required`
- `max_resume_age_minutes`
- optional `resume_requires_human_review`

Runtime evaluates age and validation evidence fail-closed. Invalid/expired resume attempts block continuation.

## Async wait model
`stage_contract.async_policy` controls intentional suspension:

- `allowed`
- `max_wait_minutes`
- `timeout_behavior` (`freeze` or `block`)

Timeout handling is policy-driven and deterministic.

## Handoff requirements
For `reset_with_handoff`, continuity requires a valid `handoff_artifact` bound to the active `stage_contract_id` and required state transfer semantics.

## Chosen integration seam
This slice wires continuity enforcement into the real sequence transition seam in `spectrum_systems/orchestration/sequence_transition_policy.py` via `_stage_contract_gate` + `_continuity_gate`.

Before continuation (`evaluate_sequence_transition`) proceeds on contracted stages, the seam now:

1. Loads stage contract.
2. Evaluates long-running continuity policy.
3. Validates checkpoint/resume/handoff semantics when requested/present.
4. Fails closed on invalid continuity state.

Existing promotion, trust-spine, control, and eval gates remain additive and unchanged in authority.

## Existing overlap aligned (not fully migrated)
HR-B aligns these existing surfaces conceptually without broad migration in this slice:

- `prompt_queue_resume_checkpoint`
- `pqx_slice_continuation_record`
- `prompt_queue_loop_continuation`

These remain valid subsystem artifacts, while HNX now defines canonical cross-system continuity semantics.

## Future HR follow-ons
- Progressive adoption of canonical continuity artifacts by each subsystem-specific continuation producer.
- Additional seam wiring beyond sequence transition where long-running execution is initiated.
- Migration path docs for replacing legacy continuation fields with canonical refs over time.
