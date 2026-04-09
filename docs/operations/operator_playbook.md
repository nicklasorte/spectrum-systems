# Operator Playbook — Governed System Usage (OPS-001)

Date: 2026-04-06  
Scope: Governed system operation only (no policy/authority changes)

## 1) System Overview

This playbook describes the existing governed path for PR/review-driven operation:

```text
PR / Review Event
→ RIL
→ CDE
→ TLC
→ PQX / TPA / FRE / PRG (as needed)
→ SEL enforced boundaries
→ system stops
→ operator merges
```

Role boundaries are fixed by the system registry:
- **RIL** interprets review outputs into deterministic integration artifacts.
- **CDE** decides closure state from governed evidence.
- **TLC** orchestrates subsystem routing only.
- **PQX / TPA / FRE / PRG** run only when TLC routes to them.
- **SEL** enforces hard fail-closed boundaries across the path.

The loop is bounded and stop-based. The system always ends in a terminal state; the operator then decides whether to merge.

Governed build/review/fix clarifications:
- Review is mandatory after every PQX execution record (`pqx_slice_execution_record` / `pqx_bundle_execution_record`).
- Fix execution is permitted only on `tpa_slice_artifact` inputs issued by TPA.
- RQX performs review artifact production only and does not execute fixes.
- Unresolved review outcomes are terminal for execution and route to TLC handoff disposition classification (no automatic PQX recursion).

## 2) How to Trigger the Governed Loop

Use only the existing trigger paths.

### Trigger A — Review event (automatic)
- `pull_request_review` with `submitted` type starts `review-trigger-pipeline`.
- `issue_comment` with `created` type can also start `review-trigger-pipeline`.

### Trigger B — Manual dispatch (operator initiated)
- Run `review-trigger-pipeline` via `workflow_dispatch` with required inputs:
  - `pr_number`
  - `review_source`
  - `run_mode`

### Trigger C — Continuation step
- `closure-continuation-pipeline` runs automatically on successful `review-trigger-pipeline` completion (`workflow_run`).
- Or run it manually with `workflow_dispatch` and `review_run_id` plus optional bounded closure flags.

## 3) What the System Will Do

In deterministic order:

1. **Ingestion + RIL** (`review-trigger-pipeline`)
   - Normalizes the incoming GitHub event.
   - Emits governed review artifacts, including `review_integration_packet_artifact`.

2. **Closure decision (CDE)** (`closure-continuation-pipeline`)
   - Consumes governed review evidence.
   - Emits `closure_decision_artifact` with one bounded decision type:
     - `lock`
     - `hardening_required`
     - `final_verification_required`
     - `continue_bounded`
     - `blocked`
     - `escalate`

3. **Orchestration (TLC), conditional**
   - TLC runs only for continuation-eligible CDE decisions.
   - If TLC runs, it emits `top_level_conductor_run_artifact` and applies SEL enforcement at governed boundaries.

4. **Terminal stop**
   - System emits final terminal state and stops.
   - No silent continuation outside governed rules.

## 4) Outputs to Expect

### From `review-trigger-pipeline`
- `ingestion_result.json`
- Governed review artifacts in the emitted artifact directory, including:
  - `review_integration_packet_artifact.json`
  - `review_projection_bundle_artifact.json`

### From `closure-continuation-pipeline`
- `continuation_result.json`
- Continuation directory containing:
  - `closure_decision_artifact.json` (always)
  - `next_step_prompt_artifact.json` (only when applicable)
  - `top_level_conductor_run_artifact.json` (only when TLC ran)
  - `continuation_summary.json`
- PR feedback comment payload is generated from these governed artifacts.

## 5) Terminal States and Exact Meaning

Use `continuation_result.final_terminal_state` as authoritative operator state:

- **`ready_for_merge`**
  - Closure path is complete for this bounded run.
  - Produced when CDE decision is `lock`, or when TLC reaches `ready_for_merge`.

- **`blocked`**
  - Fail-closed stop.
  - Missing/invalid/governance-blocking conditions remain unresolved.

- **`exhausted`**
  - Bounded retries or allowed progression were consumed.
  - Additional governed evidence/work is required before merge.

- **`escalated`**
  - Human/governance escalation is required.
  - Produced directly from escalation path (for example CDE `escalate` or TLC escalated state).

## 6) When a Human Should Intervene

Intervene immediately when any condition is true:

1. Final terminal state is `blocked`, `exhausted`, or `escalated`.
2. CDE decision is not `lock`.
3. `closure_decision_artifact` evidence refs indicate unresolved blockers/action items.
4. Any flow shows fail-closed stop reason requiring additional evidence.
5. Promotion/policy signals indicate freeze/block or inconsistent promotion gates.

Operator action in intervention cases:
- collect missing governed artifacts,
- resolve blocking review/policy items,
- rerun through the same governed trigger path.

Do not bypass RIL/CDE/TLC/SEL boundaries.

## 7) When It Is Safe to Merge

Merge is safe only when all checks below are true:

1. `continuation_result.final_terminal_state == "ready_for_merge"`.
2. `closure_decision_artifact` exists and is valid for the run.
3. If TLC ran, `top_level_conductor_run_artifact.ready_for_merge == true`.
4. No unresolved blocker/action-item evidence remains in closure artifacts.
5. No active SEL fail-closed condition exists on this run.

If any check fails, do not merge.

## 8) Deterministic Operator Checklist

1. Open `continuation_result.json`.
2. Record `cde_decision`, `tlc_ran`, `final_terminal_state`.
3. Open `closure_decision_artifact.json`; confirm decision/evidence refs.
4. If `tlc_ran=true`, open `top_level_conductor_run_artifact.json`; confirm `current_state`, `stop_reason`, `ready_for_merge`.
5. Apply Section 7 merge gate exactly.
6. Merge only on `ready_for_merge`; otherwise remediate and rerun.

This checklist is execution-only guidance for the current governed system. It does not grant new authority or alter subsystem roles.
