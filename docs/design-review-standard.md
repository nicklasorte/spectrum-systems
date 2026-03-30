# Design Review Standard

Canonical structure for architecture and design reviews performed by Claude or any reasoning agent across the Spectrum Systems ecosystem. This format is reusable in all czar repos and is the only accepted structure for captured design reviews.

## Purpose
- Standardize review outputs so they can be stored, searched, and transformed into action.
- Keep reviews deterministic, comparable, and portable across repos.
- Ensure every review produces actionable follow-up, not just observations.

## Scope of use
- All architecture/design reviews in governance repos (e.g., `spectrum-systems`) and implementation repos.
- Applies to both initial design evaluations and iterative follow-up reviews.

## Required review sections
Reviews **must** follow this order and include each section:
1. **Review Metadata** — review date, repository/name, commit or document version, reviewer/agent id, inputs consulted.
2. **Scope** — what was in-bounds, what was out-of-bounds, and why.
3. **Executive Summary** — 3–7 bullet synthesis of the most important findings and direction.
4. **Maturity Assessment** — current level (0–20), evidence summary, unmet criteria, and next-level blockers; reference the maturity playbook and tracker.
5. **Strengths** — validated positives that should be preserved.
6. **Structural Gaps** — missing components, incomplete flows, absent contracts/schemas.
7. **Risk Areas** — architectural, data, governance, or operational risks; note severity and likelihood where known.
8. **Recommendations** — concrete, testable fixes mapped to gaps/risks; include expected outcome.
9. **Priority Classification** — tag each recommendation as `Critical`, `High`, `Medium`, or `Low` with rationale.
10. **Extracted Action Items** — numbered list ready for tracking; each item includes owner placeholder, expected artifact, and acceptance criteria.
11. **Blocking Items** — blockers that prevent progress until resolved.
12. **Deferred Items** — intentionally postponed work with review trigger/condition.
- System reviews must explicitly confirm defined inputs, outputs, and evaluation tests.

## Output format and determinism
- Use markdown headings matching the section names above.
- Keep numbering stable to allow machine parsing and registry ingestion.
- Each recommendation and action item must reference the related gap or risk.
- Include explicit links to schemas, contracts, or workflow docs when cited; schemas remain authoritative.

## Review completion rules
- A review is **not complete** until action items are extracted and linked to an action tracker.
- Every review must produce an immutable artifact stored under `docs/reviews/` (or repo-equivalent) and an entry in the review registry.
- Registry entries are recorded in `docs/reviews/review-registry.json` (canonical) and mirrored to `docs/review-registry.md` for human readability; follow-up reviews should reference the prior `review_id` and note any carried-forward findings.

## Relationships to other standards
- Action extraction and follow-through are governed by `docs/review-to-action-standard.md`.
- Registrations are captured in `docs/review-registry.md`.
- Implementation repos consuming these outputs must respect the governance separation defined in this repo.

## Strategy and source compliance requirements
- Reviews must include a **Strategy Compliance Check** subsection under **Risk Areas** with explicit pass/fail for invariant adherence and control-loop role separation.
- Reviews must include a **Source Grounding Check** subsection under **Structural Gaps** listing source authorities used and any missing grounding evidence.
- Reviews must include a **Governance Drift Check** subsection under **Blocking Items** covering schema bypass, control bypass, missing eval/trace/certification, and duplicate governance surface creation.

## Mandatory operational checks
Each review must record yes/no outcomes for:
- strategy alignment
- source grounding
- eval evidence present
- traceability evidence present
- certification evidence present when required
- control decision/enforcement separation preserved
