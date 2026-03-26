---
module: core_runtime
review_type: architecture_checkpoint
review_date: 2026-03-26
reviewer: codex
decision: FAIL
trust_assessment: medium
status: final
related_plan: PLAN-SRE-03-REPLAY-ENFORCEMENT
---

# Core Loop Checkpoint Review — replay_result-only enforcement

## Scope reviewed
- `spectrum_systems/modules/runtime/trace_engine.py`
- `spectrum_systems/modules/runtime/governed_failure_injection.py`
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/control_loop.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/evaluation_monitor.py`
- `spectrum_systems/modules/runtime/alert_triggers.py`
- `spectrum_systems/modules/runtime/agent_golden_path.py`
- `tests/helpers/replay_result_builder.py`
- `tests/helpers/replay_adjacent_builders.py`

## Decision
- **FAIL**
- Replay-authoritative seams are materially strengthened, but high-impact split-brain and bypass-adjacent paths remain.

## Findings (high signal)

### F-001
- **severity:** critical
- **file:** `spectrum_systems/modules/runtime/agent_golden_path.py`
- **function:** `run_agent_golden_path`
- **failure_mode:** final continuation is derived from `decision.system_response in {"allow", "warn"}` rather than `enforcement.final_status`; this can mark execution `success` even when enforcement emits `require_review`.
- **impact:** split-brain between control decisioning and enforcement artifact; fail-closed guarantee can be bypassed inside AG-01 after a review override path.
- **minimal_fix:** compute continuation strictly from `enforcement["final_status"] == "allow"` and align final execution record status with enforcement.

### F-002
- **severity:** high
- **file:** `spectrum_systems/modules/runtime/evaluation_control.py`
- **function:** `build_evaluation_control_decision`
- **failure_mode:** API still accepts `eval_summary` directly, preserving a non-replay entry path alongside replay-result enforcement.
- **impact:** downstream callers can bypass replay-authoritative lineage checks (embedded observability/error-budget linkage) by invoking eval-summary mode.
- **minimal_fix:** enforce replay-only input mode at this seam (or hard-block eval_summary in runtime-call contexts).

### F-003
- **severity:** medium
- **file:** `spectrum_systems/modules/runtime/evaluation_monitor.py`
- **function:** `validate_replay_result_boundary_or_raise`
- **failure_mode:** replay boundary check validates schemas and trace IDs but omits `error_budget_status.observability_metrics_id == observability_metrics.artifact_id` lineage assertion.
- **impact:** split validation behavior across seams; artifact chain can pass monitor boundary but fail later in control/alert seams.
- **minimal_fix:** add explicit observability-to-error-budget artifact ID linkage enforcement matching replay/alert/evaluation control checks.

### F-004
- **severity:** medium
- **file:** `spectrum_systems/modules/runtime/control_loop.py`
- **function:** `run_control_loop`
- **failure_mode:** `trace_context` is accepted but not validated or cross-checked with replay artifact linkage.
- **impact:** replay/control split-brain risk for callers assuming injected trace context is authoritative; weakens seam determinism/audit expectations.
- **minimal_fix:** validate `trace_context` and require consistency with replay artifact (`trace_id`, execution/run identity) before decision evaluation.

## Classification

### critical_findings (must fix before next roadmap step)
- F-001

### required_fixes
- Fix F-002 replay bypass-adjacent input path at evaluation-control seam.
- Fix F-003 monitor lineage parity drift.
- Fix F-004 trace-context consistency enforcement in control loop.

### watch_items (non-blocking)
- Keep helper builders constrained to replay-authoritative defaults to avoid test fixtures normalizing weaker lineage assumptions.
- Preserve isolated trace-store injection in chaos paths; avoid introducing default-global fallback in injected runs.

## Primary review questions — result
1. **Bypass replay_result?** Partial: core integration loop enforces replay_result, but evaluation-control still exposes eval_summary mode (F-002).
2. **Global trace state mutation in isolated/chaos execution?** No direct defect found in scoped chaos path; isolated store use is preserved.
3. **Schema-valid but runtime-rejected drift?** Yes, seam-policy drift observed via missing lineage parity check in monitor boundary (F-003) and stricter runtime-only assumptions at other seams.
4. **Split-brain risks?** Yes, enforcement-vs-execution split in AG-01 (F-001), plus unbound trace_context in control loop (F-004).
5. **Determinism/fail-closed preserved?** Improved overall, but not fully preserved across all seams due to F-001/F-004.
6. **Agent/control/HITL aligned with replay-only enforcement?** Mostly, but not fully due to enforcement/continuation misalignment (F-001) and retained eval_summary branch (F-002).
