# Architecture Review Action Tracker — 2026-03-14 Architecture Review

- **Source Review:** `docs/reviews/2026-03-14-architecture-review.md`
- **Owner:** Architecture Team / Claude (Reasoning Agent)
- **Last Updated:** 2026-03-14

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Add `docs/ecosystem-map.md` with authoritative repo map, contract flows, and data flow diagram | Codex | **Closed** | None | Addressed by PR #47; `docs/ecosystem-map.md` created with full repo table and Mermaid diagram |
| CR-2 | Add `systems/spectrum-pipeline-engine/` design coverage (system design, BN link, interface, workflow, failure modes, eval) | Codex | **Closed** | None | `systems/spectrum-pipeline-engine/` created with 5-doc coverage; `workflows/spectrum-pipeline-engine.md` added; listed as SYS-009 |
| CR-3 | Model `working-paper-review-engine` and `docx-comment-injection-engine` as systems (SYS-007, SYS-008) with full docs | Codex | **Closed** | None | `systems/working-paper-review-engine/` and `systems/docx-comment-injection-engine/` created; assigned SYS-007 and SYS-008 |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | Add `workflows/meeting-minutes-engine.md` workflow spec for SYS-006 | Codex | **Closed** | None | Addressed by PR #53; `workflows/meeting-minutes-engine.md` created |
| HI-2 | Complete `docs/implementation-boundary.md` for SYS-002 through SYS-006 | Codex | **Closed** (partial) | None | Addressed by PR #48; SYS-002 through SYS-006 added; SYS-007, SYS-008, SYS-009 still missing — carried to GA-002 in follow-up review |
| HI-3 | Add SYS-005 and SYS-006 to `docs/system-failure-modes.md` | Codex | **Closed** (partial) | None | Addressed by PR #51; SYS-005 and SYS-006 added; SYS-007, SYS-008, SYS-009 still missing — carried to GA-003 |
| HI-4 | Add SYS-005 and SYS-006 eval coverage to `eval/` with `eval/test-matrix.md` rows | Architecture Team | Open | None | Not yet addressed; carried to GA-011 in follow-up review |
| HI-5 | Add `systems/system-factory/` governance spec or `docs/system-factory-governance.md` | Architecture Team | Open | None | Not yet addressed; partially covered by ecosystem map; a formal governance spec for system-factory remains absent |

## Medium-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | Add `docs/change-request-process.md` defining RFC process for contract changes | Architecture Team | Open | None | Not yet addressed; carried to GA-005 |
| MI-2 | Standardize schema versioning format to semver across all schema and contract documents | Codex | **Closed** | None | Addressed by PR #50; `docs/schema-governance.md` and `CONTRACT_VERSIONING.md` aligned to semver |
| MI-3 | Expand `AGENTS.md` or consolidate into `CLAUDE.md`/`CODEX.md` | Codex | Open (partial) | None | Addressed by PR #52; expanded from 12 to 35 lines; ecosystem overview and navigation added; development cycle still misaligned with 9-stage lifecycle — carried to GA-010 |
| MI-4 | Update `docs/roadmap.md` to reflect current state (6 systems designed; Phase 1 complete) | Architecture Team | Open | None | Not yet addressed; roadmap still shows Phase 1 as in-progress |
| MI-5 | Add `docs/governance-conformance-checklist.md` for implementation repos | Codex | **Closed** | None | Addressed by PR #49; `docs/governance-conformance-checklist.md` created |

## Low-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| LI-1 | Address production code (`spectrum_systems/`) in design-first repo — move or formally declare as evaluation scaffold | Architecture Team | Open | None | Not yet addressed; carried to GA-008 in follow-up review |
| LI-2 | Add agent guidance template (CLAUDE.md / CODEX.md template) for implementation repos | Architecture Team | Open | None | Not yet addressed; `docs/agent-guidance-standard.md` exists but no template files |

## Blocking Items
- None currently blocking implementation progress; all critical items were resolved by PRs #47–#56.

## Deferred Items
- Labeled eval fixture data for SYS-001 through SYS-004: deferred to implementation pilot phase when real fixture data is available.
- `system-factory` full governance spec: deferred until system-factory design sprint is scheduled.
- Roadmap update (`docs/roadmap.md`): deferred; low risk while system registry is accurate.
