# Claude review protocol

Status: Accepted

Date: 2026-03-15

## Context
Major architectural changes need consistent, evidence-backed evaluation before adoption. Ad-hoc reviews risk missing governance gaps, duplicating debates, and promoting systems without maturity proof or roadmap alignment.

## Decision
Establish Claude-led design reviews as the canonical gate for major architecture and governance changes. Reviews must follow the design review standard, produce human-readable reports plus action trackers, and register findings so decisions can be traced and translated into ADRs.

## Consequences
- Significant architecture changes require a Claude review before acceptance; findings feed ADR updates and roadmap decisions.
- Review artifacts (report and action tracker) must map to evidence, maturity rubric, and registry updates to keep governance synchronized.
- Conflicts between proposals and existing ADRs must be surfaced; reviewers recommend updating the ADR or reconsidering the change.
- Review cadence and registry updates become part of readiness checks for promotion and deployment sequencing.

## Alternatives considered
- Informal peer reviews without structured outputs, which would lose traceability and weaken governance.
- Relying on post-hoc documentation after changes ship, which would codify drift and erode evidence quality.
- Delegating reviews to implementation repos, which would fragment governance and reduce cross-system consistency.

## Related artifacts
- `CLAUDE_REVIEW_PROTOCOL.md`
- `docs/design-review-standard.md`
- `design-reviews/claude-review-template.md`
- `docs/review-to-action-standard.md`
- `docs/review-registry.md`
