# Core-Loop Checkpoint Fix Plan (FPO)

- review_artifact: `docs/reviews/2026-03-26-core-loop-checkpoint-review.json`
- review_id: `REV-CORE-LOOP-2026-03-26`
- schema: `contracts/schemas/review_artifact.schema.json`
- schema_validation: `pass`
- planning_source_rule: `JSON artifact only`

## Extracted findings

### critical_findings
- `F-001` (`critical`) — `spectrum_systems/modules/runtime/agent_golden_path.py::run_agent_golden_path`

### required_fixes
- `FIX-001` (`P0`) — AG-01 enforcement-authority continuation/status correction (addresses `F-001`)
- `FIX-002` (`P1`) — replay_result-only boundary in `evaluation_control`
- `FIX-003` (`P1`) — replay-boundary lineage assertion in `evaluation_monitor`
- `FIX-004` (`P2`) — trace-context binding in `control_loop`

### watch_items
- Keep replay-related helper builders aligned with replay-authoritative lineage assumptions.
- Retain isolated trace_store injection discipline in chaos cases.

## Prioritization method (rack-and-stack)
1. trust-boundary severity
2. blast radius
3. dependency order
4. hidden regression risk

## Ordered execution bundles

### Bundle 1 — AG-01 enforcement-authority fix
- **bundle_id:** `BUNDLE-01-AG01-ENFORCEMENT-AUTHORITY`
- **priority:** `P0`
- **blocking:** `true`
- **findings included:** `F-001`, `FIX-001`
- **rationale:** Critical trust-boundary defect at final enforcement seam; can record success despite enforcement requiring review.
- **files to modify:**
  - `spectrum_systems/modules/runtime/agent_golden_path.py`
  - `tests/modules/runtime/test_agent_golden_path.py` (targeted enforcement-authority assertions)
- **tests to run:**
  - `pytest tests/modules/runtime/test_agent_golden_path.py -k "enforcement or final_status or fail_closed"`
  - `pytest tests/modules/runtime/test_agent_golden_path.py`

#### Codex prompt
```text
Type: BUILD

Apply a surgical fix for AG-01 enforcement authority in spectrum_systems/modules/runtime/agent_golden_path.py (run_agent_golden_path).

Requirements:
1) Derive continuation and execution status strictly from enforcement.final_status.
2) Preserve replay_result-only enforcement authority and fail-closed behavior whenever final_status is not "allow".
3) Remove/avoid any success path derived from decision.system_response when it conflicts with enforcement authority.
4) Keep the patch minimal; no redesign, refactor, or surface expansion.
5) Add/update targeted tests in tests/modules/runtime/test_agent_golden_path.py that prove:
   - allow -> continuation permitted
   - non-allow -> blocked/fail-closed execution record
   - contradictory decision.system_response cannot override enforcement.final_status

Run:
- pytest tests/modules/runtime/test_agent_golden_path.py -k "enforcement or final_status or fail_closed"
- pytest tests/modules/runtime/test_agent_golden_path.py
```

### Bundle 2 — Replay-boundary hardening
- **bundle_id:** `BUNDLE-02-REPLAY-BOUNDARY-HARDENING`
- **priority:** `P1`
- **blocking:** `true`
- **findings included:** `FIX-002`, `FIX-003`
- **rationale:** Shared runtime seam and contract surface (replay-boundary lineage). Both fixes are tightly coupled and reduce hidden regression from mixed eval_summary/replay_result paths.
- **files to modify:**
  - `spectrum_systems/modules/runtime/evaluation_control.py`
  - `spectrum_systems/modules/runtime/evaluation_monitor.py`
  - `tests/modules/runtime/test_evaluation_control.py`
  - `tests/modules/runtime/test_evaluation_monitor.py`
- **tests to run:**
  - `pytest tests/modules/runtime/test_evaluation_control.py -k "replay_result or fail_closed"`
  - `pytest tests/modules/runtime/test_evaluation_monitor.py -k "lineage or observability_metrics_id"`
  - `pytest tests/modules/runtime/test_evaluation_control.py tests/modules/runtime/test_evaluation_monitor.py`

#### Codex prompt
```text
Type: BUILD

Implement replay-boundary hardening with a minimal patch across:
- spectrum_systems/modules/runtime/evaluation_control.py
- spectrum_systems/modules/runtime/evaluation_monitor.py

Scope:
A) Constrain evaluation_control runtime path to replay_result-only inputs; if eval_summary mode appears in runtime seams, fail closed.
B) In evaluation_monitor, assert lineage consistency so error_budget_status.observability_metrics_id references embedded observability_metrics.artifact_id.

Guardrails:
1) Preserve replay_result-only enforcement invariant.
2) Preserve fail-closed behavior.
3) Keep change surgical; no redesign or unrelated refactors.
4) Add/update targeted tests only for these seams.

Run:
- pytest tests/modules/runtime/test_evaluation_control.py -k "replay_result or fail_closed"
- pytest tests/modules/runtime/test_evaluation_monitor.py -k "lineage or observability_metrics_id"
- pytest tests/modules/runtime/test_evaluation_control.py tests/modules/runtime/test_evaluation_monitor.py
```

### Bundle 3 — Control-loop trace-context validation
- **bundle_id:** `BUNDLE-03-CONTROL-LOOP-TRACE-CONTEXT`
- **priority:** `P2`
- **blocking:** `false`
- **findings included:** `FIX-004`
- **rationale:** Important replay/control context integrity hardening, but lower severity and narrower blast radius than B1/B2.
- **files to modify:**
  - `spectrum_systems/modules/runtime/control_loop.py`
  - `tests/modules/runtime/test_control_loop.py`
- **tests to run:**
  - `pytest tests/modules/runtime/test_control_loop.py -k "trace_context or replay artifact identity"`
  - `pytest tests/modules/runtime/test_control_loop.py`

#### Codex prompt
```text
Type: BUILD

Apply a surgical trace-context validation fix in spectrum_systems/modules/runtime/control_loop.py.

Requirements:
1) Validate and bind control_loop.trace_context to replay artifact identity.
2) Eliminate replay/control split-brain continuation paths.
3) Preserve replay_result-only and fail-closed invariants.
4) Do not redesign loop architecture; minimal targeted edits only.
5) Add/update focused tests in tests/modules/runtime/test_control_loop.py for mismatched vs aligned trace_context/replay identity behavior.

Run:
- pytest tests/modules/runtime/test_control_loop.py -k "trace_context or replay artifact identity"
- pytest tests/modules/runtime/test_control_loop.py
```

## Deferred watch items
- Keep replay-related helper builders aligned with replay-authoritative lineage assumptions to avoid normalizing weaker fixture patterns.
- Retain isolated trace_store injection discipline in chaos cases to avoid accidental fallback to process-global trace state.
