# Action Tracker — Control Loop Enforcement Review (2026-03-22)

- **Source Review:** `docs/2026-03-22-control-loop-enforcement-review.md`
- **Owner:** Engineering / Codex execution agent
- **Last Updated:** 2026-03-22

## Critical Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| CL-1 | Harden `continuation_allowed` in `control_integration.py`: replace `exec_status not in _BLOCKED_STATUSES` with `exec_status == "success"` positive allowlist | Codex | Open | None | Fail-open on null/unknown status. Implement in downstream engine repo. |
| CL-2 | Make `decision_id` deterministic in `evaluation_control.py`: replace `uuid.uuid4()` with `uuid.uuid5` seeded from `eval_run_id + triggered_signals + schema_version` | Codex | Open | None | Breaks replay/regression ID linkage. Implement in downstream engine repo. |
| CL-3 | Update `replay_run()` in `replay_engine.py` to call `enforce_control_decision` instead of `enforce_budget_decision`; update output schema reference accordingly | Codex | Open | CL-2 (stable decision_id required first) | Dual enforcement path. Implement in downstream engine repo. |
| CL-4 | Resolve `_BYPASS_BLOCKED_RESULT` in `control_integration.py`: wire into bypass-detection path or delete | Codex | Open | None | Dead enforcement artifact creates governance ambiguity. |

## High-Priority Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| CL-5 | Gate or remove `thresholds` override parameter in `build_evaluation_control_decision`; require explicit governance token for non-default thresholds | Claude / Governance | Open | None | Unchecked threshold relaxation is a latent trust risk. |
| CL-6 | Change `_execute_steps()` open-span mapping: `status=None` → `'skipped'` (not `'ok'`) with determinism note | Codex | Open | None | Masks enforcement failures in replay output. |

## Medium-Priority Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| CL-7 | Add explicit warning log in `evaluate_trace_pass_fail()` when `decision_consistency` key is absent from analysis artifact | Codex | Open | None | Silent indeterminate default reduces regression harness observability. |

## Blocking Items

- **CL-1** blocks any production-grade use of the enforcement gate.
- **CL-2** must be resolved before **CL-3** (deterministic IDs are required for canonical replay comparison).
- **CL-3** must be resolved before the regression harness (BAI) can validate canonical control-loop decisions.

## Deferred Items

- Removal of `enforce_budget_decision` entirely: defer until all consumers (run-bundle, replay) have migrated to the canonical path. Track under CL-3 follow-up.
