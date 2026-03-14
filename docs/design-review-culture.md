# Design Review Culture

Spectrum Systems uses an automated design review culture: reviews are durable artifacts, not transient meetings. Findings become tracked actions, and architecture evolves through repeated review loops with preserved governance memory.

## Purpose
- Make design reviews repeatable, comparable, and auditable across the czar repository organization.
- Ensure every review produces actions, owners, and follow-up triggers.
- Keep governance standards separate from implementation execution while enabling reuse.

## Core principles
- **Reviews are artifacts:** Every review is captured as an immutable document under `docs/reviews/` using the canonical format.
- **Actions are mandatory:** A review is incomplete until action items are extracted into `docs/review-actions/` and recorded in `docs/review-registry.md`.
- **Governance memory:** This repository is the constitutional record; downstream implementation repos execute changes but do not redefine standards.
- **Determinism:** Stable section ordering and priority labels enable machine parsing and cross-repo reuse.
- **Separation of concerns:** Governance items (contracts, schemas, standards) stay in `spectrum-systems`; implementation items move to the appropriate engine repos.

## Standard flow
1. Conduct review using `docs/design-review-standard.md`.
2. Store the immutable artifact in `docs/reviews/`.
3. Extract actions via `docs/review-to-action-standard.md` into `docs/review-actions/action-tracker-template.md`.
4. Update `docs/review-registry.md` with links to the artifact, tracker, and follow-up triggers.
5. File or draft GitHub issues in the correct repos for critical items; schedule the next review when triggers fire.

## Triggers for new reviews
- Major contract or schema changes.
- New system introductions or deprecations.
- Completion of critical action items.
- Pre-release checkpoints for implementation repos.

## What stays out of this repo
- Operational automation code or review engines.
- Runtime implementations of workflows; this repo defines standards, formats, and governance only.
