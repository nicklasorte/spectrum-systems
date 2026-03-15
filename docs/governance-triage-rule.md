# Governance Triage Rule for Claude Review Findings

## Purpose
Architecture reviews can produce many findings. This rule keeps the backlog organized, avoids issue fragmentation, and preserves structural insight by channeling new Claude-generated findings into the right buckets.

## Triage Outcomes
- Standalone issue
- Merge into existing workstream
- Convert to checklist item under an umbrella issue
- Close as duplicate / already addressed / not actionable

## Standalone Issue Criteria
Create a standalone issue only when most of these are true:
- affects system behavior or governance enforcement
- architecturally distinct from other open work
- has a clear owner repository
- substantial enough to justify its own implementation thread
- not already covered by an existing issue or workstream

## Merge Criteria
Merge the finding into an existing bucket when it is:
- part of a broader architectural theme already tracked
- a sub-part of a larger change already underway
- primarily documentation/template/example alignment for an existing issue
- too small to justify separate tracking

## Closure Criteria
Close the finding when it is:
- a duplicate of an existing item
- already resolved
- too vague to act on
- not materially useful to system evolution

## Canonical Workstream Buckets
- Review Artifact Hardening — improve review templates, schemas, validation, and ingest scripts.
- Validation and Testing — evaluation harnesses, fixtures, and automated checks.
- Governance Documentation — standards, lifecycle guides, and contributor-facing docs.
- Automation Plumbing — pipelines, project sync, and review-to-issue automation.
- Ecosystem Governance — cross-repo policies, registry updates, and ecosystem rules.
- Contract Evolution — contract/schema changes, versioning, and compatibility paths.

## Triage Workflow
1. New Claude finding appears.
2. Check for an existing bucket or umbrella issue.
3. Decide: standalone vs merge vs checklist vs close.
4. Apply labels, update the chosen issue/bucket, or note closure.
5. Only create or keep a dedicated issue when the standalone criteria are met.

## Backlog Discipline Rule
Default bias: merge new Claude findings into an existing architectural workstream unless there is a strong reason to keep a standalone issue.

## Suggested Labels
Use the label system in `docs/label-system.md` and, when present, apply: `claude-review`, `workstream`, `standalone`, `duplicate`, `required-change`, `optional-improvement`.
