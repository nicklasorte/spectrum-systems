# ST-01 — Canonical Self-Testing System Architecture

## System Definition
Self-testing in Spectrum Systems is the governed closed-loop composition of:
- **eval**
- **control**
- **enforcement**
- **replay**
- **learning**

Self-testing is not optional telemetry; it is the runtime trust boundary that determines whether progression is allowed.

## Self-Testing Loop
Canonical loop:

**PQX → Artifact → Eval → Control → Enforcement → Replay → Learn**

Each stage is artifact-first, deterministic, and contract-validated.

## Required Artifact Families
The self-testing system requires six artifact families:
1. execution artifacts
2. eval artifacts
3. control artifacts
4. replay artifacts
5. human correction artifacts
6. intelligence artifacts

A missing required family is a trust-boundary failure.

## Fail-Closed Rules
Mandatory fail-closed outcomes:
- missing eval → **block**
- missing artifact → **block**
- replay mismatch → **freeze**
- indeterminate → **freeze**

No implicit allow path exists for missing/ambiguous trust evidence.

## PQX Self-Testing Model (Checklist)
For each PQX step, all of the following must be true:
- artifact exists
- schema valid
- evals run
- eval summary exists
- control decision exists
- enforcement exists
- replay path exists

If any check fails, control must emit non-allow and preserve deterministic traceability.

## Determinism Rules
Self-testing determinism requirements:
- canonical hashing (`sha256(canonical_json(...))`)
- stable ordering (`dedupe_preserve_order` where dedupe is required)
- versioned inputs (schema/policy/version references carried in artifacts)

## Learning Loop
Learning closure is mandatory:

**Failures → eval cases → datasets → roadmap inputs**

The loop is governance-constrained: learning artifacts inform future eval coverage and roadmap priorities, but do not bypass control authority.
