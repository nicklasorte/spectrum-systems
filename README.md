# Spectrum Systems

Spectrum Systems is a governed execution runtime and control-plane repository.

Its durable value is control: governed artifact contracts, deterministic execution rules, and evidence that makes decisions auditable. Promotion is evidence-based and fails closed when evidence is missing.

## Runtime Spine (Authoritative)

The canonical runtime spine is:

**AEX → PQX → EVL → TPA → CDE → SEL**

Mandatory gate overlays on this spine:

- **REP** — replay integrity gate
- **LIN** — lineage completeness gate
- **OBS** — observability completeness gate

These nine authorities are the minimal hard runtime architecture. They are the only first-class canonical runtime authorities.

## Architecture Layers

### 1) Hard runtime authorities
Hard runtime authorities can block progression and enforce fail-closed behavior:

- AEX, PQX, EVL, TPA, CDE, SEL, REP, LIN, OBS

### 2) Support planes (important, non-spine)
Support planes are required for runtime quality and operations but are not peer authorities in the minimal spine:

- TLC — orchestration
- FRE — repair planning
- RIL — interpretation
- PRG — program governance

### 3) Subsystems and supporting surfaces
Judgment, contract/integrity, intelligence/drift, dataset/test, override/audit, and routing/prompt/context surfaces are grouped support constructs. They are not peer runtime authorities unless promoted through canonical system-addition rules.

Advisory, analytical, and placeholder surfaces are not authoritative runtime peers.

## Non-Negotiable Runtime Rules

1. **Artifact-first execution**: required state transitions must be represented as governed artifact records.
2. **Fail-closed behavior**: missing or invalid required evidence blocks progression.
3. **Promotion requires certification**: no promotion without required certification evidence.

Additional hard constraints:

- no hidden execution paths
- no duplicated ownership
- no downstream progression without required evidence

## Brutal Enforcement Semantics

The runtime must apply explicit gate outcomes:

- **BLOCK** when required artifact/eval/policy/lineage/observability/replay/certification evidence is missing or schema-invalid.
- **FREEZE** when replay mismatch, indeterminate required eval, drift threshold breach, or budget/governance threshold exhaustion occurs.
- **ALLOW** only when all required artifacts, evals, policy admissibility, lineage, observability, replay (where required), and certification evidence pass.

## Canonical Architecture Documents

- Canonical index and rules: `docs/architecture/system_registry.md`
- Core authorities and support planes: `docs/architecture/system_registry_core.md`
- Grouped support families: `docs/architecture/system_registry_support.md`
- Reserved/non-active systems: `docs/architecture/system_registry_reserved.md`
- Runtime enforcement semantics: `docs/architecture/runtime_spine.md`

## How to Use This Repository

1. Start with the runtime spine and hard gate semantics.
2. Use governed artifact contracts from `contracts/` and schemas from `schemas/`.
3. Keep prompts and governance behavior explicit in repository markdown and contracts.
4. Treat this repository as control-plane governance; place product/business runtime code in implementation repositories.

## Philosophy

The system controls execution.

Models can change. Governance cannot be implicit.
