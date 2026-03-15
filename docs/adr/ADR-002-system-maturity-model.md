# System maturity model

Status: Accepted

Date: 2026-03-15

## Context
The ecosystem needed a consistent way to measure progress, gate risk, and prioritize roadmap steps across heterogeneous systems. Without a shared maturity model, promotion decisions would be subjective, governance gaps could be missed, and downstream engines would advance without evidence.

## Decision
Adopt a Level 0–20 maturity model with explicit criteria, evidence requirements, and review checkpoints. Each level captures operational capabilities, governance alignment, and evidence expectations. Promotion requires Claude review and proof mapped to the playbook and maturity rubric.

## Consequences
- Systems must declare their current level and provide evidence for promotion requests.
- Roadmap planning and dependency tracking anchor to maturity milestones, keeping sequencing disciplined.
- Claude reviews and registries use the model to evaluate readiness, block unjustified promotions, and surface risks.
- Documentation (playbook, rubric) must stay synchronized with ADR-aligned expectations as the ecosystem evolves.

## Alternatives considered
- A binary “ready/not ready” gate, which lacks nuance for sequencing and risk management.
- Custom maturity definitions per system, which would fragment governance and make cross-system alignment impossible.
- Informal progress narratives without structured evidence, which would erode trust and repeat debates.

## Related artifacts
- `docs/system-maturity-model.md`
- `docs/level-0-to-20-playbook.md`
- `docs/review-maturity-rubric.md`
- `docs/review-registry.md`
- `docs/roadmap.md`
