# Closure Decision Engine (CDE)

## Purpose
The Closure Decision Engine (CDE) deterministically consumes governed review/closure evidence and emits a `closure_decision_artifact` that decides one bounded closure outcome:

- `lock`
- `hardening_required`
- `final_verification_required`
- `continue_bounded`
- `blocked`
- `escalate`

CDE may also emit `next_step_prompt_artifact` when a deterministic next governed step is available.

## Explicit role boundary
CDE is strictly a closure-state decision layer.

CDE **does**:
- determine closure-state and lock-state
- determine bounded next-step class
- produce evidence-traceable closure decisions

CDE **does not**:
- execute work (PQX boundary)
- repair artifacts or code
- run review parsing/classification (RIL boundary)
- mutate policy or authorize bypasses (SEL/TPA boundary)
- generate broad roadmap strategy (PRG boundary)

## Deterministic contract surface
Inputs are governed artifacts (for example `review_projection_bundle_artifact`, `review_consumer_output_bundle_artifact`, `review_control_signal_artifact`, `review_signal_artifact`) passed into the CDE request payload.

Primary output:
- `closure_decision_artifact`

Optional deterministic output:
- `next_step_prompt_artifact`

## TLC consumption boundary
CDE output is structured for later TLC orchestration consumption.
CDE itself remains non-executing and non-authoritative beyond closure decisioning.
