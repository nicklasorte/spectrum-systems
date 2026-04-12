# DASHBOARD-NEXT-PHASE-SERIAL-02 — Red Team Review 01

## Prompt type
REVIEW

## Scope
DASH-01 through DASH-30 implementation seam in `dashboard/lib/**`, `dashboard/components/**`, and `dashboard/tests/**`.

## Findings

### Blockers
1. Causal/trace/evidence panels were not explicitly declared in the surface contract registry; this created certification blind spots for source ownership.
2. Certification checks did not assert that every panel contract includes blocked-state allowance and non-empty provenance requirements.

### Top 5 surgical fixes
1. Add `causal_chain`, `decision_trace`, `multi_artifact_correlation`, and `evidence_strength` to `surface_contract_registry` and `panel_capability_map`.
2. Add field-level provenance with transformation path traces for causal edges.
3. Extend read-model compiler with fail-closed blocked diagnostics for the four new panels.
4. Harden status normalization to explicit enum mapping for freshness/result variants.
5. Add serial-02 targeted tests to lock panel ownership, provenance fidelity, and gate checks.

## Trust boundary check
No selector/compiler authority reassignment observed; dashboard remains read-only consumer.

## Overclaim check
No panel should claim policy authority. Existing and proposed panels must continue artifact-backed rendering only.
