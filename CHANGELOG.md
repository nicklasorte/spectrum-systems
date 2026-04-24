# Changelog

## Added
- 2026-04-24 — Strengthen core loops: closed 5 disconnected feedback paths in the governed execution runtime (PR #1170).
  - **FailureToEvalPipeline** (`modules/feedback/failure_to_eval_pipeline.py`): Routes classified errors into governed `eval_candidate` artifacts so each failure class improves future eval coverage. Closes `failure → classified → (dead end)`.
  - **ReviewConvergenceController** (`modules/review_convergence_controller.py`): Wraps the review-fix cycle in a convergence loop that retries until output is clean or `max_iterations` is exceeded. Closes `review → fix → (assume clean)`.
  - **Drift-Aware Admission** (`govern/govern.py`): `policy_check()` now accepts an optional `drift_state`; critical signals block admission to prevent amplification during recovery, warning signals log but allow. Closes `drift detected → (no throttle)`.
  - **WPG Judgment Persistence** (`orchestration/wpg_pipeline.py`): Valid WPG judgments are persisted to `JudgmentCorpus` via `_persist_judgment_if_valid` for precedent reuse. Closes `WPG judgments → (discarded)`.
  - **In-Memory Judgment Handoff** (`orchestration/cycle_runner.py`): Judgment artifacts are carried in `manifest["_judgment_inmem"]` and surfaced in the `run_cycle` return value, eliminating a redundant file re-read. Closes `judgment → file → re-read`.
  - 15 new tests across 5 test files; 0 regressions on the existing suite.
- 2026-03-14 — Added the meeting agenda contract (schema v1.0.0) with canonical inputs, outputs, agenda item/source reference schemas, JSON/Markdown/DOCX targets, and examples for agenda generation.
- 2026-03-14 — Published the PDF-anchored DOCX comment injection contract as a czar-level artifact (schema v1.0.1) with fixed column order, status normalization, audit reporting, and duplicate guards.
- 2026-03-13 — Added governance documents to guide system design (CONTRIBUTING.md, GLOSSARY.md, VALIDATION.md, DATA_SOURCES.md, REPO_MAP.md, SYSTEM_TEMPLATE.md, CHANGELOG.md, DECISIONS.md).
- 2026-03-13 — Added system navigation and hardening docs (`docs/system-map.md`, `docs/system-philosophy.md`, `docs/system-interface-spec.md`, `docs/system-lifecycle.md`, `docs/system-status-registry.md`, `docs/system-failure-modes.md`, `docs/reproducibility-standard.md`, `docs/repo-maintenance-checklist.md`, `docs/doc-governance.md`, `docs/terminology.md`).
- 2026-03-13 — Added system directory with per-system overviews, interfaces, designs, evaluation notes, and prompt references under `systems/`.
- 2026-03-13 — Added evaluation test matrix and eval README for cross-system coverage.

## Changed
- 2026-03-13 — Linked governance documents from README.md.
- 2026-03-13 — Hardened README, SYSTEMS index, schemas (versioned with provenance requirements), prompt registry, and workflows for consistent navigation and terminology.

## Removed
- None to date.
