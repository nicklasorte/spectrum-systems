# Review Artifacts Standard

`docs/reviews/` is the canonical repository location for governed markdown review artifacts.

## Canonical storage and naming

- Store new review documents in `docs/reviews/`.
- Use the canonical filename pattern:
  - `YYYY-MM-DD-<module>-<review-type>.md`
  - Example: `2026-03-23-governed_prompt_queue-codex_review.md`
- `<module>` and `<review-type>` must be lowercase and kebab-safe (`[a-z0-9._-]`).

## Required machine-readable metadata block

Every governed markdown review **must** begin with YAML frontmatter at the top of the file:

```yaml
---
module: governed_prompt_queue
review_type: codex_review
review_date: 2026-03-23
reviewer: Codex
decision: PASS
trust_assessment: YES
status: resolved
related_plan: docs/review-actions/PLAN-REVIEW-ARTIFACT-STANDARD-2026-03-23.md
---
```

Required frontmatter keys:

- `module`
- `review_type`
- `review_date`
- `reviewer`
- `decision` (`PASS` or `FAIL`)
- `trust_assessment` (`YES` or `NO`)
- `status` (`open`, `resolved`, or `superseded`)
- `related_plan` (path to the plan file in `docs/review-actions/`)

## Required review body sections

After frontmatter, include these sections in order for deterministic retrieval and downstream parsing:

1. `## Scope`
2. `## Decision`
3. `## Trust Assessment`
4. `## Critical Findings`
5. `## Required Fixes`
6. `## Optional Improvements`
7. `## Failure Mode Summary`

## Relation to `docs/review-actions/`

- A review documents findings and decisions.
- The corresponding action tracker in `docs/review-actions/` tracks remediation execution and closure.
- `related_plan` in review frontmatter must point to the governing plan that scoped the reviewed change.

## Open vs resolved tracking

- `status: open`: fixes are still outstanding.
- `status: resolved`: all required fixes are complete and verified.
- `status: superseded`: review replaced by a newer review artifact.

When status changes, keep the original review immutable and create a follow-on review artifact with a new date-based filename if new findings or decisions are introduced.

## Contract alignment

JSON review artifacts are governed by:

- Schema: `contracts/schemas/review_artifact.schema.json`
- Golden example: `contracts/examples/review_artifact.json`

Use `python scripts/validate_review_artifact.py` to validate JSON artifacts and markdown metadata compliance.
