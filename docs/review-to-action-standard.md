# Review-to-Action Standard

Required outputs and flow that must occur after every design review in the Spectrum Systems ecosystem. A review is only complete when its findings are transformed into tracked actions.

## Required post-review outputs
1. **Immutable Review Artifact** — the canonical review document stored under `docs/reviews/` (or repo-equivalent) with a stable filename and metadata.
2. **Action Tracker Update** — a structured tracker stored under `docs/review-actions/` derived from the review’s action items.
3. **Prioritized Implementation Backlog** — ordered list of recommended implementation tasks mapped to systems/contracts with priority tags.
4. **Recommended GitHub Issues** — proposed issue titles/contexts for critical items, scoped to the correct repo (governance vs implementation).
5. **Follow-up Review Trigger Conditions** — explicit triggers or dates that require the next review (e.g., after schema change, first deployment, or dependency readiness).

## Transformation steps (deterministic)
1. Confirm the review artifact uses the canonical structure in `docs/design-review-standard.md`.
2. Extract action items into the architecture action tracker template (see `docs/review-actions/action-tracker-template.md`).
3. Link every action item to its source gap/risk/recommendation and assign a priority.
4. Identify which items belong in governance repos (contracts, schemas, standards) versus implementation repos (code, pipelines); propose the correct target repo for GitHub issues.
5. Update `docs/review-registry.md` with links to the review artifact and action tracker.
6. Define follow-up triggers and due dates; record them in the registry.

## Action item requirements
- Include explicit acceptance criteria for each item.
- Add an evidence placeholder that must be filled with proof per `docs/review-evidence-standard.md` before closure.
- Record the target repository for execution (governance vs implementation) and any blocking relationships.
- Maintain stable finding IDs; follow-up reviews must reconcile prior findings by ID and mark closure, open status, or deferral with evidence.

## Completion criteria
- No review is considered done until the action tracker and registry entry exist.
- Critical items must include draft GitHub issue language to reduce ambiguity when filed.
- Backlog ordering must reflect priority and blocking relationships.

## Consumption guidance
- Implementation repos should import action items relevant to their scope without redefining governance artifacts.
- Governance repos (like `spectrum-systems`) hold the standards, registries, and canonical trackers; downstream repos execute implementation work.
