# AG-06 — Generated Eval Staging and Review (Governed Thin Layer)

## Purpose
AG-06 provides a deterministic bridge between admitted `generated_eval_case` artifacts and human-governed review for possible future registry inclusion.

This slice is explicitly **artifact-first**, **fail-closed**, and **non-authoritative**.

## Flow

`generated_eval_case` → `generated_eval_admission_record` → `generated_eval_staging_record` → `generated_eval_review_queue` → `promotion_recommendation_record`

## Candidate vs required eval coverage

- **Generated eval candidate** (`generated_eval_case`): deterministic output from runtime failure signals.
- **Required eval coverage**: durable, authority-scoped coverage expectations used by enforcement and certification.

AG-06 does **not** write to required eval registries and does **not** convert candidates into required evals automatically.

## Staging semantics

`generated_eval_staging_record` groups admitted generated eval candidates by stable recurrence keys (`reason_code` + `scenario_name`) and tracks:

- recurrence (`occurrence_count`)
- first/last occurrence timestamps (`first_seen_at`, `last_seen_at`)
- default status (`pending_review`)

Staging status values are intentionally bounded:
- `pending_review`
- `accepted_for_registry`
- `rejected`
- `deferred`

## Review queue semantics

`generated_eval_review_queue` is a deterministic bundle that surfaces:
- all generated eval IDs currently staged
- total candidate count
- high-priority candidate IDs based on recurrence threshold

The queue only informs review ordering. It does not grant promotion authority.

## Promotion recommendation semantics (non-authoritative)

`promotion_recommendation_record` emits a bounded recommendation:
- `promote` when recurrence threshold is met
- `monitor` otherwise

This artifact is advisory only and intentionally excludes policy execution, registry mutation, or automatic promotion.

## Why auto-promotion is intentionally excluded

Auto-promotion would violate authority boundaries and weaken fail-closed governance guarantees.

AG-06 is intentionally thin so repeated failures remain visible and reviewable without bypassing:
- admission checks,
- certification requirements,
- or explicit authority actions.
