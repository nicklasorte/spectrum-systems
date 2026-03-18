# Roadmap Inventory Action Tracker

- **Source Review:** `docs/reviews/2026-03-18-roadmap-inventory-review.md`
- **Owner:** TBD
- **Last Updated:** 2026-03-18

## Critical Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| RI-001 | Add deprecation notice to `docs/roadmap.md` pointing to `docs/roadmaps/codex-prompt-roadmap.md` as the replacement | Copilot | Resolved (2026-03-18) | None | `docs/roadmap.md` now opens with `⚠️ DEPRECATED` header, names the replacement, and instructs agents not to execute from it. |
| RI-002 | Update `Status:` field in `docs/architecture/module-pivot-roadmap.md` from `Active` to `Reference` and add a navigation note pointing to `docs/roadmaps/codex-prompt-roadmap.md` for Codex prompt sequencing | Copilot | Resolved (2026-03-18) | None | `module-pivot-roadmap.md` now opens with `📘 REFERENCE` header and `Status: Reference`; directs readers to `codex-prompt-roadmap.md` for execution. |

## High-Priority Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| RI-003 | Add a "Single ACTIVE Roadmap" note to `AGENTS.md` or `CODEX.md` explicitly naming `docs/roadmaps/codex-prompt-roadmap.md` as the sole Codex execution driver | Copilot | Resolved (2026-03-18) | RI-001, RI-002 | Both `AGENTS.md` and `CODEX.md` now contain a "Roadmap Execution Rule" section naming `codex-prompt-roadmap.md` as the sole ACTIVE roadmap and stating REFERENCE/DEPRECATED documents must not drive execution. |

## Medium-Priority Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| RI-004 | Resolve open blocking actions RM-002 (Canonical ID Standard) and RM-004 (Canonical Knowledge Model) from `docs/review-actions/2026-03-16-roadmap-review-actions.md` before any Layer 2 module work begins | TBD | Open | None | RM-002 blocks cross-engine artifact linking; RM-004 blocks Knowledge Capture and Institutional Memory modules from being built with consistent schemas |

## Low-Priority Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| RI-005 | Evaluate whether `docs/system-planning-framework.md` and `docs/system-planning-steps.md` should be merged into a single document, given that `system-planning-framework.md` is a subset of `system-planning-steps.md` | TBD | Open | None | Minor cleanup; both are REFERENCE and not execution-blocking |

## Blocking Items

- **RI-001, RI-002, and RI-003** are all Resolved as of 2026-03-18. `docs/roadmaps/codex-prompt-roadmap.md` is now unambiguously the single ACTIVE execution roadmap for all agents.
- **RM-002 (Canonical ID Standard)** from `docs/review-actions/2026-03-16-roadmap-review-actions.md` still blocks any Layer 2 module work (S–W in codex-prompt-roadmap.md).

## Deferred Items

- Formal deletion of `docs/roadmap.md` — defer until the deprecation notice (RI-001) has been merged and no downstream references are found.
- Consolidation of `docs/system-planning-framework.md` and `docs/system-planning-steps.md` — defer until after RI-001 through RI-003 are resolved.
