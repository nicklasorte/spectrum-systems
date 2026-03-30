# System Strategy (Authoritative)

## Authority
- **Path:** `docs/architecture/system_strategy.md`
- **Version:** `2026-03-30`
- **Role:** Governing intent for roadmap generation, review execution, and progression decisions.
- **Enforcement:** Any governed artifact missing this strategy reference is non-compliant and must fail closed.

## Core Invariants (Strategy Law)
1. Artifact-first outputs only (no free-text dependency as system input).
2. Schema-bound interfaces only (contracts are authoritative).
3. Eval judges, control decides, execution proposes.
4. Progression requires trust evidence before speed.
5. Missing lineage, trace, eval, or certification blocks progression.
6. Model components are replaceable execution engines; governance artifacts are durable.

## Control Boundaries
- Execution surfaces may propose actions and produce candidate artifacts.
- Eval surfaces judge quality/risk and emit structured evidence.
- Control surfaces issue progression decisions.
- Enforcement surfaces apply allow/block/remediation outcomes.
- Observability surfaces report drift and policy violations.

## Drift Rules
Treat the following as critical governance drift:
- strategy link missing from roadmap/review/progression artifact
- source grounding missing or unverifiable
- schema bypass or eval bypass
- control decision bypass
- certification bypass where required
- duplicate governance surface creation that overlaps existing seams

## Trust-Before-Speed Rule
Advancement is allowed only when all required trust artifacts are present and valid for the lifecycle stage:
- strategy linkage
- source grounding
- eval evidence
- trace/lineage evidence
- control decision
- certification evidence when promotion is requested
