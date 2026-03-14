# Program-State Model

The program-state model normalizes canonical artifacts into a single structure keyed by `program_id`. It is the backbone for decision-readiness scoring and advisory outputs.

## Entities
- **Decisions** (`decision_log`): `decision_id`, status, readiness, needed-by, options, dependencies, evidence.
- **Risks** (`risk_register`): `risk_id`, category (technical, data, schedule, stakeholder, process/legal, coordination, narrative), likelihood, impact, readiness effect, links to decisions/milestones/assumptions.
- **Assumptions** (`assumption_register`): `assumption_id`, status, confidence, validation plan, related risks/decisions, mitigation if false.
- **Milestones** (`milestone_plan`): `milestone_id`, status, dependencies (milestone/decision/risk/assumption), decision gates, readiness notes.
- **Readiness** (`study_readiness_assessment`): gate checks, missing evidence, artifact status, dependency risks.
- **Actions** (`next_best_action_memo`): `action_id`, priority, owner, due date, dependencies, expected impact.

## Relationships
- Decisions reference risks, assumptions, and milestones; readiness capped by unresolved dependencies.
- Risks reference decisions, milestones, and assumptions; readiness effect feeds the readiness score.
- Milestones reference decisions and assumptions; blocking milestones reduce readiness.
- Actions reference decisions, risks, assumptions, and milestones; prioritized to clear readiness blockers.
- Source artifacts (`source_artifacts`, `source_reference`) connect each entity back to canonical inputs for traceability.

## Derived Views
- **Top risks**: risks sorted by exposure and readiness effect.
- **Open decisions**: decisions with status not in `approved/rejected/superseded`, sorted by `needed_by`.
- **Missing evidence**: union of readiness missing-evidence list and artifact statuses marked `missing` or `stale`.

## Determinism
- Sorting: risks by exposure desc, decisions by `needed_by` asc, actions by priority (`urgent`→`low`) then due date.
- Scoring: readiness score capped by least-ready gate; blocking risks/assumptions reduce score by fixed increments before AI assistance.
- Identifiers: reuse upstream IDs; do not create new IDs during aggregation.
