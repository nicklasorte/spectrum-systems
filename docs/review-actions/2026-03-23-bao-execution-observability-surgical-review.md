# BAO Execution Observability Layer — Surgical Implementation Review

Date: 2026-03-23
Prompt type: REVIEW

## Decision
FAIL

## Critical Findings (max 5)

### 1) Observability emission is best-effort in governed runtime paths (silent-drop risk)
- **What is wrong**
  Multiple governed runtime paths swallow trace emission failures (`TraceNotFoundError`/`SpanNotFoundError`) and continue processing (`pass`).
- **Why it is dangerous**
  Governed execution can proceed with partial or missing trace spans/events while appearing successful, breaking audit reconstruction guarantees.
- **Location**
  `control_chain.py` and `control_executor.py` (and similarly `validator_engine.py`) around span/event close + attach blocks.
- **Realistic failure scenario**
  A transient in-memory trace index inconsistency causes `record_event`/`end_span` to fail; control decision still returns success/allow, but final trace lacks enforcement/gating terminal events and artifact attachment.

### 2) Cross-artifact correlation is incomplete for control execution artifacts
- **What is wrong**
  `control_execution_result` schema does not require or even define `trace_id`, `run_id`, `artifact_id`, or policy linkage fields.
- **Why it is dangerous**
  Execution artifacts can be valid yet not joinable to governed artifact chains (run, policy decision, provenance), making deterministic forensic joins impossible.
- **Location**
  `contracts/schemas/control_execution_result.schema.json`.
- **Realistic failure scenario**
  Two executions produce identical `actions_taken` shapes in the same interval; without mandatory correlation keys, downstream observability cannot unambiguously connect each execution result to its source decision artifact.

### 3) Replay/runtime observability parity drift (dual replay_result surfaces)
- **What is wrong**
  Replay engine validates replay results against both a BAG schema and a permissive legacy BP schema fallback. This allows two different shapes for the same concept.
- **Why it is dangerous**
  Consumers may receive semantically divergent replay artifacts depending on producer path, creating fragile joins and inconsistent governance semantics.
- **Location**
  `replay_engine.py` (`validate_replay_result` dual-schema logic) and replay result contract usage.
- **Realistic failure scenario**
  A downstream correlator expects BAG fields (`original_run_id`, `replay_run_id`, provenance shape), but a legacy-valid payload passes validation and omits those assumptions, causing correlation/report gaps.

### 4) Declared replay persistence control is a no-op
- **What is wrong**
  `execute_replay(..., persist_result=True)` documents persistence behavior but never performs persistence.
- **Why it is dangerous**
  Operators can believe replay observability is durable while results remain ephemeral, undermining replay audit trails.
- **Location**
  `replay_engine.py` (`persist_result` parameter documented but unused).
- **Realistic failure scenario**
  Incident response expects replay outputs persisted for later reconstruction; process restarts and replay evidence is gone because persistence was never executed.

### 5) Event semantics are insufficiently governed for deterministic observability
- **What is wrong**
  Trace event vocabulary is open-ended (`event_type` any non-empty string, payload arbitrary object). Replay governance emits uppercase logger events (`REPLAY_*`) while trace spans use lowercase domain events.
- **Why it is dangerous**
  Vocabulary drift and semantically weak-but-schema-valid records can fragment dashboards/alerts and hinder deterministic joins across runtime and replay.
- **Location**
  `contracts/schemas/trace.schema.json` and `replay_governance.py` event emission helpers.
- **Realistic failure scenario**
  Two teams emit equivalent semantics under different event names/casing; one pipeline misses alerts because it filters on only one vocabulary.

## Required Fixes (minimal, surgical)
1. **Fail-closed trace emission for governed paths**
   - Replace `except (TraceNotFoundError, SpanNotFoundError): pass` in governed terminal emission paths with explicit blocking/error propagation (or append mandatory `observability_emission_failed` blocking action).
2. **Add mandatory correlation keys to control execution artifact contract**
   - Require `trace_id` and at least one governed join key (`artifact_id` and/or `run_id`) in `control_execution_result` schema and emitted payloads.
3. **Remove or gate legacy replay-result acceptance in governed flows**
   - For governed execution/replay paths, require BAG canonical schema only (or explicit `schema_mode=legacy` with blocked status in governed mode).
4. **Implement or remove `persist_result` contract promise**
   - If retained, persist replay result deterministically when `persist_result=True`; otherwise remove parameter/docs to avoid false guarantees.
5. **Govern event vocabulary minimally**
   - Introduce controlled event enums (or a centrally shared constant set) for runtime/replay event types and standardize casing.

## Optional Improvements (small hardening)
- Include `policy_id`/`policy_version` in replay governance event emissions and trace payloads where policy decisions are applied.
- Add a parity test asserting runtime vs replay observability canonical fields for the same run chain.
- Add a test that forces trace emission failure and asserts governed execution blocks rather than continuing.

## Trust Assessment
NO

## Failure Mode Summary
Worst realistic failure: decision-grade execution continues and returns a valid governance decision while key trace events/artifact attachments silently fail, and replay persistence is assumed but absent. During incident reconstruction, logs and artifacts cannot be deterministically joined to the governed chain, causing low-confidence root-cause analysis and reduced policy/debug trust.
