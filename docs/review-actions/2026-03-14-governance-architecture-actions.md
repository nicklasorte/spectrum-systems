# Architecture Review Action Tracker

- **Source Review:** `docs/reviews/2026-03-14-governance-architecture-review.md`
- **Owner:** Architecture Team / Claude (Reasoning Agent)
- **Last Updated:** 2026-03-14

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| GA-001 | Register prior review and create action trackers — populate `docs/review-registry.md` with rows for both the 2026-03-14-architecture-review and this review; create `docs/review-actions/2026-03-14-architecture-actions.md` closing items addressed by PRs #47–#56 and leaving open the remaining gaps | Architecture Team | Open | None | Pre-condition for all future reviews; registry must be populated before review process is considered operational |
| GA-002 | Extend `docs/implementation-boundary.md` with SYS-007 (working-paper-review-engine), SYS-008 (docx-comment-injection-engine), SYS-009 (spectrum-pipeline-engine) boundary mappings using the same template as SYS-001 through SYS-006 | Architecture Team | Open | None | Gaps G-3; implementation repos for these systems will begin work without formal declaration requirements if unresolved |
| GA-003 | Add SYS-007, SYS-008, SYS-009 failure mode entries to `docs/system-failure-modes.md`; include PDF anchor extraction failures (SYS-007), injection location mismatches (SYS-008), and orchestration loop / version mismatch / partial bundle failures (SYS-009) | Architecture Team | Open | None | Gap G-4; SYS-009 failure propagation is the highest cascade risk in the ecosystem |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| GA-004 | Promote `external_artifact_manifest` from `draft` to `stable` in `contracts/standards-manifest.json` after verifying schema readiness; update `docs/artifact-flow.md` and `CONTRACTS.md` accordingly | Architecture Team | Open | Schema readiness verification | Gap G-5; draft contract required by stable systems creates governance inconsistency; must resolve before implementation begins external artifact storage |
| GA-005 | Create `docs/change-request-process.md` defining RFC content, review periods (5 days MINOR / 10 days MAJOR), pre-merge update requirements, and GitHub notification mechanism; add cross-reference in `CONTRACT_VERSIONING.md` | Architecture Team | Open | None | Gap G-6; must exist before any MINOR or MAJOR contract change is made |
| GA-006 | Document the SYS-009 ↔ SYS-006 bidirectional dependency with explicit termination condition in `systems/spectrum-pipeline-engine/interface.md`, `systems/meeting-minutes-engine/interface.md`, and `docs/artifact-flow.md` | Architecture Team | Open | None | Risk R-3; loop risk unmodeled in either system's design |
| GA-007 | Create `contracts/governance-declaration.template.json` with SYS-001 example entry; update `docs/governance-conformance-checklist.md` to require machine-readable declaration; mark Phase 1 initiated in `docs/governance-enforcement-roadmap.md` | Architecture Team | Open | None | Risk R-6; Phase 1 is unblocked and unstarted; initiation does not require CI tooling |

## Medium-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| GA-008 | Resolve production Python code in design-first repo: move `spectrum_systems/study_runner/` and `run_study.py` to `spectrum-pipeline-engine` repo or formally declare as evaluation scaffold in `DECISIONS.md`; add boundary note in `docs/implementation-boundary.md` | Architecture Team | Open | None | Risk R-5 from prior review; carried forward unresolved; undermines design-first philosophy |
| GA-009 | Create `docs/deprecation-policy.md` defining deprecation marking criteria, deprecated-but-present window, consumer notification, and removal procedure; add cross-reference in `CONTRACT_VERSIONING.md` | Architecture Team | Open | None | Gap G-7; no active deprecations yet but will matter on first field removal |

## Low-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| GA-010 | Rewrite `AGENTS.md` to align development cycle with 9-stage system lifecycle and add agent-specific guidance for SYS-007 through SYS-009; or consolidate into `CLAUDE.md` | Architecture Team | Open | None | Gap G-9; current 35-line state adds minimal value; low urgency |
| GA-011 | Create `eval/` harness directories for SYS-005 through SYS-009 with README files following `eval/comment-resolution/` pattern; add rows for SYS-005 through SYS-009 to `eval/test-matrix.md` | Architecture Team | Open | None | Gap G-10; makes evaluation pattern consistent across all nine systems |

## Blocking Items
- **GA-001 blocks closure of this review** — the review is not complete under `docs/review-to-action-standard.md` until both the registry entry and action tracker exist.
- **GA-005 blocks any MINOR or MAJOR contract changes** — the RFC process must exist before contract semantics change.
- **GA-004 blocks production use of external artifact storage** — draft contract must stabilize before implementation repos register artifacts.

## Deferred Items
- Eval harness labeled fixture data for SYS-001 through SYS-004 (carried from prior review, open in `docs/review-actions/2026-03-14-architecture-actions.md`) — defer to implementation pilot phase when real fixture data becomes available from test runs.
- CI-based conformance checks (Phase 3 of governance enforcement roadmap) — deferred until Phase 1 and Phase 2 are complete; not actionable now.
