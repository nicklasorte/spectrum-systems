# Execution Change Impact Gate

Execution change impact is the deterministic pre-execution governance gate for runtime/control-path file changes.

## Purpose

`execution_change_impact_artifact` complements contract impact analysis:
- **Contract impact gate (G13)** protects schema/contract compatibility.
- **Execution change impact gate (G14)** protects runtime/orchestration/control/review/certification semantics.

Both are pre-execution gates. Neither is optional when their triggering inputs are present.

## Deterministic operating model

The operating model remains unchanged:
- plan many steps
- authorize one step
- evaluate risk before execution
- block on insufficient trust
- preserve deterministic governance

No LLM judgment, no network calls, no probabilistic scoring.

## Fail-closed rules

The execution change impact gate blocks PQX when any of the following are true:
1. `blocking=true`
2. `indeterminate=true`
3. `safe_to_execute!=true`

The analyzer is fail-closed by design:
- Unclassifiable governed-candidate paths are marked `unknown` and force `indeterminate=true`.
- Runtime/orchestration/control/PQX path changes require review + eval evidence.
- Governance operating-model docs are treated as governance-sensitive, not default-low-risk.
- Critical-governed code changes without critical test evidence are not automatically safe.

## Artifact contract

Analyzer output must validate against:
- `contracts/schemas/execution_change_impact_artifact.schema.json`

Artifact includes deterministic path-level assessments, required evidence, explicit gating decision fields, rationale, and provenance.

## PQX integration

PQX now evaluates two gates before execution:
1. contract impact gate
2. execution change impact gate

PQX does not override gate outcomes. Control-layer supremacy is preserved: block decisions are terminal until stronger evidence is provided.
