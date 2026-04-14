# Preflight Ref Normalization (Canonical)

Preflight ref normalization is deterministic and fail-closed.

## Event-specific rules

1. `pull_request`
   - prefer explicit `--base-ref` + `--head-ref` when both are non-empty
   - otherwise use `GITHUB_BASE_SHA` + `GITHUB_HEAD_SHA`

2. `push`
   - prefer explicit `--base-ref` + `--head-ref` when both are non-empty
   - otherwise use `GITHUB_BEFORE_SHA` + `GITHUB_SHA`
   - push normalization must not depend on PR-only env vars

3. `workflow_dispatch` / local execution
   - explicit `--base-ref` + `--head-ref` are required
   - missing explicit refs block with structured reason

4. Unknown events
   - block with `unsupported_event_context`

## Structured observability fields

Preflight report and changed-path resolution artifacts include `ref_context`:
- `event_name`
- `raw_inputs` (CLI refs and relevant GitHub env vars)
- `base_ref` and `head_ref` after normalization
- `normalization_strategy`
- `fallback_used`
- `valid`
- `reason_code` / `invalid_reason` when blocked
- `root_cause_classification` and `repair_eligibility_rationale` in `contract_preflight_report.json` for deterministic repair/escalation decisions

## Failure reason-code distinctions

- `missing_refs`
- `unsupported_event_context`
- `malformed_ref_context`
- `contract_mismatch_from_bad_ref_resolution`

These reason codes are consumed by the preflight diagnosis/repair flow for deterministic classification and bounded auto-repair behavior.

## PRF-06 repair terminal-state semantics

Root cause of vague `BLOCK + exit 2` handling: first-pass preflight classification emitted `contract_mismatch` with `auto_repair_allowed`, but the CI flow could stop after first-pass preflight without executing the governed repair+rereun path.

Current governed state machine:
1. run first-pass `scripts/run_contract_preflight.py`
2. if first pass blocks and `preflight_repair_plan_record.eligibility_decision == auto_repair_allowed`, run `scripts/run_github_pr_autofix_contract_preflight.py`
3. auto-repair emits deterministic terminal state and post-repair artifact truth:
   - `passed_after_auto_repair`
   - `blocked_repair_failed`
   - `blocked_repair_not_applicable`
   - `blocked_escalation_required`

Guardrails:
- if `eligibility_decision == auto_repair_allowed`, flow must either mark `repair_attempted == true` or set deterministic `repair_inapplicable_reason`.
- generic terminal `BLOCK` is not accepted when a post-repair terminal state is available.
