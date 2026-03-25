# Alert Triggers (SRE-11)

## What this artifact means in this repo
`alert_trigger` is a governed **decision artifact** answering whether current replay-authoritative governed signals require operator attention.

This slice computes alert decisions only. It does **not** dispatch notifications.

## Source signals consumed
The evaluator consumes `replay_result` and its embedded governed measurement/control artifacts:
- `observability_metrics`
- `error_budget_status`
- `baseline_gate_decision` (optional)
- `drift_detection_result` (optional)
- `grounding_control_decision` (optional)

Required presence is policy-bound (`required_source_artifacts`), with default policy requiring replay + observability + error budget.

## Contracts
- `contracts/schemas/alert_trigger.schema.json`
- `contracts/examples/alert_trigger.json`
- `contracts/schemas/alert_trigger_policy.schema.json`
- `contracts/examples/alert_trigger_policy.json`

## Status and severity semantics
Bounded status vocabulary:
- `no_alert`
- `warning`
- `critical`
- `invalid`

Bounded severity vocabulary:
- `none`
- `low`
- `medium`
- `high`
- `critical`

Signal mappings are explicit and deterministic in `alert_trigger_policy` (no inferred free-text logic).

## Authoritative integration seam and rationale
Alert triggers are attached in `run_replay` (BAG replay seam), after observability and error-budget artifacts are attached.

Why this seam is authoritative:
1. Replay already centralizes deterministic measurement attachments.
2. Replay is trace-linked and schema-validated.
3. Alert decisions are therefore pinned to the exact governed evidence used by operators.

## Fail-closed behavior
- Schema-invalid replay input fails closed.
- Schema-invalid policy fails closed.
- Unknown status vocabulary in source signals fails closed.
- Missing policy-required source artifacts emit deterministic `invalid` alert decisions.
- Output is schema-validated before return.

## Determinism guarantees
- `artifact_id` is SHA-256 of canonical preimage fields.
- `timestamp` is sourced from replay artifact timestamp (no runtime clock in alert module).
- Condition evaluation order follows policy signal order.
- Triggered condition and reason arrays are deduplicated + sorted.

## Explicit non-goals
- No email/Slack/webhook/pager delivery.
- No escalation workflow implementation.
- No routing/channel selection logic.
- No enforcement redesign; this emits decision artifacts only.

## Handoff point for future delivery systems
Future notification/delivery slices should consume `alert_trigger` artifacts directly and must preserve:
- `replay_result_id`
- `source_artifact_ids`
- `policy_id`
- `trace_refs`

That separation keeps delivery concerns outside deterministic evaluation logic.
