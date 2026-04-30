# CLP-02 — PR-Ready Admission Expectations for AEX/PQX

## Purpose

CLP-02 introduces:

- `docs/governance/core_loop_pre_pr_gate_policy.json` — TPA-owned policy
  describing required CLP checks, allowed warn reason codes, and block rules.
- `scripts/check_agent_pr_ready.py` — observation-only PR-ready guard that
  produces an `agent_pr_ready_result` artifact.
- `agent_core_loop_run_record` integration — AGL fails closed on missing or
  blocking PR-ready evidence.

This document records the expectations CLP-02 imposes on AEX and PQX, and
the remaining hard-enforcement gap.

## Authority boundary (unchanged)

CLP is observation-only. It does not approve, certify, promote, admit, or
enforce. Authority remains as declared in `docs/architecture/system_registry.md`:

| System | Owns                                  |
|--------|---------------------------------------|
| AEX    | admission                             |
| PQX    | bounded execution / closure transitions|
| EVL    | eval evidence                         |
| TPA    | policy adjudication                   |
| CDE    | continuation / closure decisions      |
| SEL    | final compliance enforcement          |

CLP-02 only emits structured PR-ready evidence; downstream owners decide
what to do with it.

## AEX expectation

Repo-mutating agent admission should require a future `agent_pr_ready_result`
with `pr_ready_status = ready` before the slice may be handed off as
PR-ready. AEX should:

1. Treat `outputs/core_loop_pre_pr_gate/agent_pr_ready_result.json` as
   admission evidence.
2. Refuse to mark admission complete when the artifact is absent, malformed,
   or carries `pr_ready_status != ready`.
3. Surface `clp_evidence_missing` and `pre_pr_gate_blocked` reason codes
   into existing admission records when present.

CLP-02 does not modify the AEX runtime path directly. Instead, AGL
(`spectrum_systems/modules/runtime/agent_core_loop_proof.py`) and the
existing required_pr_checks pytest gate consume the guard artifact. Any
future hard enforcement inside AEX must be added by the AEX owner, not by
CLP.

## PQX expectation

Bounded execution closure / PR-ready handoff should require a
`pr_ready_status = ready` guard. PQX should:

1. Inspect the guard artifact before transitioning a slice to a
   PR-ready terminal state.
2. Refuse the closure transition when `pr_ready_status != ready` and
   defer to PRL/FRE/CDE for repair coordination.
3. Carry `clp_result_ref` and `agent_pr_ready_result_ref` in execution
   trace metadata so downstream replay/lineage can reproduce the gate
   result.

CLP-02 does not modify the PQX runtime path directly. The required-checks
pytest gate (already CI-required) consumes the AGL record as the
canonical observation-only signal.

## Remaining hardening gap

Direct hard enforcement inside the AEX admission path and the PQX
execution closure path is intentionally out of scope for CLP-02. CLP-02
documents the expectation and wires the guard into:

- `spectrum_systems/modules/runtime/agent_core_loop_proof.py` (AGL fail-closed)
- `spectrum_systems/modules/prl/failure_classifier.py` (PRL failure mapping)
- `tests/test_agent_core_loop_requires_clp.py` (pytest gate)

Hard enforcement inside AEX/PQX must be tracked as a follow-up batch
owned by the AEX/PQX system owners. CLP must not redefine those entry
paths.

## Reason code surface

CLP-02 reason codes that AEX/PQX/CDE consumers should recognize:

| Reason code                          | Meaning                                                     |
|--------------------------------------|-------------------------------------------------------------|
| `clp_evidence_missing`               | Repo-mutating slice with no CLP result                      |
| `clp_gate_block`                     | CLP gate_status=block (generic)                             |
| `clp_warn_unapproved`                | CLP warn with reason code outside `allowed_warn_reason_codes` |
| `clp_authority_scope_invalid`        | CLP artifact authority_scope drifted from observation_only  |
| `agent_pr_ready_evidence_invalid`    | Guard ref provided but file missing or malformed            |
| `pre_pr_gate_blocked`                | Guard not_ready (covers downstream consumers)               |

Existing CLP failure classes
(`authority_shape_violation`, `authority_leak_violation`,
`tls_generated_artifact_stale`, `contract_preflight_block`,
`pytest_selection_missing`, `selected_test_failure`,
`missing_required_artifact`, `missing_required_check_output`,
`policy_mismatch`, `system_registry_mismatch`) flow through the guard's
`reason_codes` field unchanged.
