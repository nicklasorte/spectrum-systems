# Artifact Classification Standard

This standard introduces a canonical artifact-class model for the spectrum-systems ecosystem. Every governed artifact belongs to one of four classes: coordination, work, review, or governance. Contracts, manifests, and engines should use these classes to simplify integration and traceability.

## Canonical classes
- **coordination** — Align people, decisions, schedules, and next steps. Typical outputs capture who, when, and what happens next. Examples: roster, agenda, transcript, meeting minutes, action items, FAQ, schedule.
- **work** — Technical analysis or study outputs produced during execution. These carry substantive calculations or narrative content. Examples: study plan, engineering outputs, working paper, updated working paper, report sections, figures, tables.
- **review** — Comments, critique, adjudication, and approval/revision states. Examples: agency review, reviewer comment set, comment resolution matrix, adjudicated matrix, decision log, review findings.
- **governance** — Policy, control, assurance, and compliance artifacts that govern when systems may proceed. Examples: routing policy, evaluation control decision, trust posture snapshot, governance manifests, policy lifecycle records.

## Allowed transitions
Only the following class transitions are allowed without additional justification:
- coordination -> coordination
- coordination -> work
- coordination -> governance
- work -> work
- work -> review
- review -> work
- review -> coordination
- review -> governance
- governance -> coordination
- governance -> review

Introducing a new transition later must include an explicit, documented justification in the standards manifest and design reviews.

## Cross-class flow examples
- Meeting coordination (agenda, minutes) -> work updates (revised sections, figures) -> review (comment set, resolution matrix) -> coordination (decision log, action items).
- Study plan (work) -> reviewer comment set (review) -> adjudicated matrix (review) -> program brief (coordination) for governance boards.
- Transcript (coordination) -> working paper updates (work) -> review findings (review) -> updated schedule and owners (coordination).

## Contract guidance
- All future contracts must declare an `artifact_class` aligned to this standard and the machine-readable registry in `contracts/artifact-class-registry.json`.
- Manifests and schemas should reference these classes to reduce bespoke integration logic across engines.
- Downstream engines should treat `artifact_class` as a first-class routing and validation dimension alongside `artifact_type`.
