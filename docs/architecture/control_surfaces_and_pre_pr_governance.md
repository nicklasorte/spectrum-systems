# Control Surfaces and Pre-PR Governance (HR-C)

## Why CI-only discovery is insufficient

CI-only governance discovery is late and expensive: it permits local authoring drift, pushes unresolved contract violations into shared pipelines, and creates avoidable PR churn. HR-C moves that detection to the local authoring seam so governed change sets are blocked (or deterministically repaired) before PR progression.

## Local pre-PR closure flow

The local pre-PR closure loop is fail-closed and deterministic:

1. run targeted tests for changed governed surfaces
2. run contract enforcement
3. run contract preflight on changed governed paths
4. inspect preflight strategy gate result
5. attempt bounded auto-repair for deterministic safe classes only
6. rerun preflight after repair
7. block PR progression when strategy gate remains `BLOCK` or `FREEZE`

The implementation entrypoint is `run_local_pre_pr_governance_closure(...)` and is wired into the TLC repair-to-merge seam.

## Bounded auto-repair philosophy

Auto-repair is intentionally narrow:

- allowed: deterministic registration/wiring classes (manifest/schema registration and required-surface linkage classes)
- disallowed: policy threshold mutation, gate weakening, strategy downgrade, trust-spine bypass, or skip behavior

If deterministic repair cannot produce `ALLOW|WARN`, progression remains blocked.

## Human checkpoint artifact family

HR-C introduces canonical schema-bound artifacts:

- `human_checkpoint_request`
- `human_checkpoint_decision`
- `approval_boundary_record`

Human checkpoints are now explicit records in governed execution, not workflow convention or free-text notes.

## Permission artifact family

HR-C introduces canonical permission artifacts:

- `permission_request_record`
- `permission_decision_record`

Every permission evaluation now emits a structured decision (`allow`, `deny`, `require_human_approval`) with policy reference, reason codes, trace, and provenance.

## Relationship to HNX and policy authority

- HNX remains the structure/time harness authority for stage execution constraints.
- Permission and approval decisions remain externalized artifacts, not implicit model behavior.
- Policy modules remain the authority for allow/deny/approval-required outcomes.
- TLC/PQX seams consume these decisions fail-closed.
