# Spectrum Systems — Architectural Integrity Audit

**Date:** 2026-04-08
**Branch:** `claude/audit-spectrum-architecture-Rq5Hy`
**Scope:** Structural soundness, future failure modes, scale-readiness.
**Evidence base:** Direct code inspection of all primary implementation modules.

> This is a structural integrity and architectural correctness audit.
> It is not a code review. It is not a style review. It is not a unit test review.
> Assume this system will be scaled and stressed. These are the conditions under which it fails.

---

## PRELIMINARY NOTE

The system exhibits genuine engineering discipline: fail-closed defaults, schema-validated artifacts, deterministic ID generation, explicit transition tables, and rigorous checkpoint construction. The `blocking_findings_count: 0` claim is plausible for the current load profile. It will not survive scale.

What follows are the conditions under which the system will fail.

---

## TOP 5 ARCHITECTURAL RISKS (RANKED)

---

### RISK 1 — CRITICAL: The Permission Gate is Fabricated and Not on the Execution Path

**Evidence:** `spectrum_systems/modules/prompt_queue/queue_state_machine.py:172–211` (`_build_step_execution_inputs`)

The queue loop fabricates its own `gating_decision_artifact` inline with hardcoded values:

```python
gating_decision_artifact = {
    "gating_decision_artifact_id": f"generated-gating-{step['step_id']}",
    "decision_status": "runnable",
    "decision_reason_code": "runnable_within_policy",
    "approval_required": False,
    "gating_policy_id": "prompt_queue_execution_gating_policy.v1",
    ...
}
```

This artifact is then passed to `execution_runner.py:103–104` which validates it — but only checks that `decision_status == "runnable"`, which the fabricated artifact satisfies by construction.

The canonical module `permission_governance.py` (`evaluate_permission_decision`) is imported by exactly **2 files** in the entire codebase: itself and `codex_to_pqx_task_wrapper.py`. It is never called from the queue state machine loop, the execution runner, or the bundle orchestrator.

**What this means:** The queue loop's permission gate is a tautology. Every step that reaches `_build_step_execution_inputs` already carries a fabricated "runnable" approval. The actual policy (tool allowlist, write scope, human approval requirements) in `permission_governance.py` is enforced nowhere in the critical execution path. `permission_decision_record` is declared canonical, but it is not canonical on this path.

**Failure mode at scale:** Under high autonomy or new system onboarding, every queue step will be silently approved regardless of the tool, scope, or risk level of the actual work item.

---

### RISK 2 — CRITICAL: The Execution Layer is Permanently Simulated

**Evidence:** `spectrum_systems/modules/prompt_queue/execution_runner.py:20` and `:155–204`

```python
_SUPPORTED_EXECUTION_MODES = {"simulated"}
```

`run_simulated_execution` determines success or failure based solely on a lineage check:

```python
has_lineage = all([
    work_item.get("repair_prompt_artifact_path") or ...,
    work_item.get("gating_decision_artifact_path"),
    work_item.get("spawned_from_findings_artifact_path"),
    work_item.get("spawned_from_review_artifact_path"),
])
```

If all 4 paths are present → `execution_status = "success"`. If any are missing → `"failure"`. No actual execution occurs. The output reference points to a simulated artifact path generated as a string, not actually written.

**What this means:** The queue loop is a governance-routing harness that tests its own wiring, not production execution. A work item with complete lineage always succeeds; one without lineage always fails. The governing machinery (SEL, CDE, TLC, checkpoints, permissions) wraps a function that checks four string fields.

**Failure mode at scale:** If this mode is never switched to live execution, all metrics, observability, and enforcement artifacts reflect simulation results. Scaling simulation is not scaling execution.

---

### RISK 3 — HIGH: Dual Enforcement Schemas in Production

**Evidence:** `spectrum_systems/modules/runtime/enforcement_engine.py:76–157` and `:198–239`

Two structurally incompatible enforcement artifact shapes coexist:

| Field | Canonical (`enforce_control_decision`) | Legacy (`enforce_budget_decision`) |
|---|---|---|
| ID field | `enforcement_result_id` | `enforcement_id` |
| Schema version | `1.1.0` | none |
| `provenance` | present | absent |
| `fail_closed` flag | present | absent |
| `"warn"` action | does not exist | maps to `execution_permitted=True` |
| Caller restriction | open | `inspect.stack()` check |

The legacy caller guard uses `inspect.stack()` — fragile, non-deterministic under import variations — and allows all `test_` callers unconditionally. Downstream consumers receiving an enforcement artifact must guess which schema it has. The `"warn"` action in the legacy path silently permits execution; the canonical path has no such concept.

**Failure mode at scale:** As new systems onboard and consume enforcement artifacts, they will branch incorrectly on `enforcement_id` vs `enforcement_result_id` without a schema discriminant. "Warn" in one schema is a no-op signal; in the other it is a silent execution permit. Mixed consumers will diverge silently.

---

### RISK 4 — HIGH: SEL's PQX Boundary Enforcement is Self-Reported

**Evidence:** `spectrum_systems/modules/runtime/system_enforcement_layer.py:124–139`, `spectrum_systems/modules/runtime/pqx_execution_policy.py:27–35`

The SEL PQX entry check:

```python
pqx_entry = bool(request.get("pqx_entry")) or execution_context == "pqx_governed"
```

Both `pqx_entry` and `execution_context` are fields in the caller-provided context dict. There is no signed token, session proof, or runtime binding to the actual queue state machine. Any caller setting `pqx_entry = True` passes this check without restriction.

Additionally, `pqx_execution_policy.py` includes `"direct"`, `"unspecified"`, and `"exploration"` in `_ALLOWED_EXECUTION_CONTEXTS`. For paths not matching `_GOVERNED_PREFIXES` (a static hardcoded list), these contexts permit execution without PQX. New systems at novel paths are automatically non-governed.

**Failure mode at scale:** The SEL boundary is a documentation convention enforced only against honest callers. The moment execution surfaces expand — new systems, new paths — the SEL boundary degrades proportionally. Its "blocking_findings_count: 0" reflects clean wiring, not secure enforcement.

---

### RISK 5 — HIGH: Two Independent State Machines with No Atomic Binding

**Evidence:** `spectrum_systems/modules/prompt_queue/queue_state_machine.py` vs `spectrum_systems/modules/runtime/pqx_bundle_state.py`

Two structurally independent state tracking layers:

- **Queue layer:** `queue_status`, `current_step_index`, `step_results` (in `QueueState`)
- **Bundle layer:** `completed_step_ids`, `blocked_step_ids`, `active_bundle_id` (in `PQXBundleState`)

These are separate in-memory structures, written separately, with no atomic transaction guarantee. If execution succeeds and the bundle state update fails (or vice versa after a crash/restart), both states diverge permanently. The `resume_token` in `derive_resume_position` is derived only from the bundle layer and is not cross-validated against `queue_state.current_step_index`.

**Failure mode at scale:** Under concurrent execution or any restart-after-crash, state divergence accumulates silently. There is no reconciliation path.

---

## "LOOKS CORRECT BUT IS FRAGILE"

**A. Replay determinism claim is shallow and single-step.**
`replay_queue_from_checkpoint` (`queue_state_machine.py:544–638`) runs `run_queue_once` twice live and compares outputs. This does not test replay from a recorded trace — it tests whether two consecutive live executions agree. Since `run_simulated_execution` is deterministic by construction (field presence check), parity always matches in simulation. This says nothing about determinism of real execution. `replay_engine.py` says "no hidden re-derivation" but the queue replay does exactly that.

**B. `indeterminate_eval_behavior = "freeze"` default is not fail-closed.**
In `stage_contract_runtime.py:128`, when required evals return `indeterminate/unknown/pending`, the default behavior is `freeze`, not `block`. Under infrastructure degradation (eval service degraded, timeouts), this produces frozen-but-not-blocked stages that accumulate at scale and require manual intervention. There is no visible auto-escalation path.

**C. HNX async wait timeout defaults to "freeze", not "block".**
In `hnx_execution_state.py:213–219`, timeout behavior defaults to `state="freeze"`, returning `allowed=False, state="freeze"`. This is not fail-closed. Frozen states require external intervention. At scale with many parallel executions, frozen states multiply without bound.

**D. `enforce_budget_decision` "warn" is a silent execution permit.**
The legacy path maps `"warn"` to `action="warn", execution_permitted=True`. Systems consuming legacy artifacts and seeing `action="warn"` will allow execution. The canonical path has no such concept.

**E. `_GOVERNED_PREFIXES` is a static hardcoded list.**
`pqx_execution_policy.py:8–13` hardcodes governed prefixes. New systems onboarded at novel paths bypass PQX enforcement by default. This is a governance enrollment gap that scales with each new system addition.

---

## MISSING INVARIANTS

| # | Missing Invariant | Where It Should Be Enforced |
|---|-------------------|-----------------------------|
| I-1 | `gating_decision_artifact` must originate from `evaluate_permission_decision`; no fabricated artifacts permitted on execution path | `run_queue_once` before calling `run_queue_step_execution_adapter` |
| I-2 | `QueueState.current_step_index` and `PQXBundleState.completed_step_ids` must remain consistent at step boundaries | Resume entry point in both state machines |
| I-3 | Enforcement artifacts must carry a schema-version discriminant sufficient for consumers to identify schema without field inspection | Both enforcement artifact schemas |
| I-4 | `frozen` stages must have a bounded lifetime; no stage may remain frozen beyond a configured max age without escalation | `stage_contract_runtime.py` |
| I-5 | New system paths must be registered in a governed prefix registry before execution is permitted | `pqx_execution_policy.py` at evaluation time |
| I-6 | Baseline artifacts for drift detection must be younger than a configurable max age | `drift_detection.py` at comparison time |

---

## SAFE TO SCALE?

### Scale PQX execution: NOT YET

The execution layer is permanently in simulation mode. The permission gate is fabricated. These are not hardening gaps — they are structural missing elements. Until a live execution mode is wired to actual tool calls with real permission evaluation, scaling PQX execution scales a simulation harness.

### Onboard additional systems (FAQ, meeting minutes, working papers): NOT SAFE without remediation

New system paths bypass `_GOVERNED_PREFIXES` by default and are immediately non-governed. SEL's self-reported boundary check means any new system declaring itself `pqx_governed` passes without verification. The dual enforcement schema creates consumer ambiguity from day one of onboarding.

---

## CONCRETE RECOMMENDATIONS

Priority order — only what is structurally necessary:

**1. Route permission through the canonical module.**
Remove the inline `gating_decision_artifact` fabrication in `_build_step_execution_inputs`. Call `evaluate_permission_decision` from `permission_governance.py`. Add `provenance.producer` to the gating artifact schema and validate it at the execution runner boundary.

**2. Define a live execution mode.**
`_SUPPORTED_EXECUTION_MODES` must include a non-simulated path before PQX execution is meaningful. The simulation harness is valuable for testing governance logic — label it explicitly as a test mode and gate the production path separately.

**3. Consolidate enforcement to one schema.**
Hard-deprecate `enforce_budget_decision`. Set `_LEGACY_CALLER_ALLOWLIST = ()`. Migrate `control_executor` callers to `enforce_control_decision`. The canonical and legacy paths must not coexist as live production surfaces.

**4. Make the SEL boundary unforgeable.**
Replace self-reported `pqx_entry`/`execution_context` with a signed execution token issued by the queue state machine at step start and verified by SEL. Until then, declare explicitly in documentation that the SEL PQX check is advisory-only for honest callers.

**5. Add state consistency assertion on resume.**
Before any queue step executes, assert `queue_state.current_step_index == len(pqx_bundle_state.completed_step_ids)` for the linked bundle. Fail closed if they diverge. The `resume_token` in `derive_resume_position` is a start — it needs cross-validation against `current_step_index`.

**6. Replace hardcoded prefix list with a governed registry.**
Load `_GOVERNED_PREFIXES` from `docs/architecture/system_registry.md` at runtime. Require new system registration as a precondition to execution, not documentation.

---

## OVERALL ASSESSMENT

The system has excellent internal consistency within each individual module. The state machine logic, schema validation, and checkpoint mechanics are clean. Tests are comprehensive and catch wiring errors well.

The structural problem is one level up: the modules are wired correctly on the governance-routing plane, but the execution plane underneath them is a simulation, the permission gate they protect is fabricated, and the boundary enforcement is self-reported. The observability, drift detection, and replay machinery are measuring a governed shell around an unexecuted center.

This is not a readiness score problem. A readiness score above 80 with zero blocking findings is achievable precisely because the system is coherent at the layer that tests measure. The risks are in the layer those tests assume.
