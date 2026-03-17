# System Philosophy

**Status:** Active  
**Version:** 1.0.0  
**Date:** 2026-03-17  
**Scope:** Ecosystem-wide — all modules and pipelines in spectrum-systems

---

## Purpose

This document captures the governing design philosophy for all modules, pipelines, and artifacts implemented in `spectrum-systems`.  These rules are not aspirational — they are enforced by the module architecture and the validation layer.

---

## Rule 1 — Module-First

**New capability is built as a module inside `spectrum-systems`, not as a new repository.**

The prior approach of creating a dedicated repository per capability produced useful design artifacts but not a coherent system.  Contracts diverged.  Schemas were redefined locally.  There was no shared state, no unified lifecycle, and no institutional memory.  Each engine operated in isolation.

The module-first rule supersedes that model.

**What this means:**
- New capability lives in `spectrum_systems/modules/`
- Modules import contracts and schemas from the canonical locations in this repo
- Modules do not redefine schemas that already exist in `contracts/schemas/` or `schemas/`
- New repositories are only created when there is a clear runtime, product, or deployment boundary that cannot be served by a module

**What this does not mean:**
- Existing engine repositories are not immediately dissolved
- Downstream consumers (operational engines) may still exist as separate repos when justified
- The module is not a microservice; it is a Python module with deterministic inputs and outputs

---

## Rule 2 — Golden Path

**One canonical way to do each thing.  No parallel implementations of the same capability.**

The golden path is the single, tested, governed way to accomplish a task within the ecosystem.  When a golden path exists, it must be used.  When one does not exist, the first implementation that achieves production quality becomes the golden path and is documented as such.

**What this means:**
- Signal extraction: use `cases/meeting_minutes/signal-extraction.yaml` as the canonical spec
- Artifact packaging: use `spectrum_systems/modules/artifact_packager.py`
- Study state construction: use `spectrum_systems/modules/study_state.py`
- Pipeline orchestration: use `spectrum_systems/modules/meeting_minutes_pipeline.py`

**What this does not mean:**
- The golden path is frozen; it evolves with evidence and design reviews
- Experimental implementations are prohibited; they must be clearly labelled as experimental

---

## Rule 3 — Study-State-First Architecture

**The study state is the primary product of every meeting minutes run.  All other artifacts are derived from or validated against it.**

The study state (`study_state.json`) is not a side effect of the pipeline.  It is the canonical output.  Every pipeline run must produce a study state, and every downstream consumer (working paper generator, program advisor, study compiler) must consume the study state as its primary input.

**What this means:**
- `study_state.json` is always emitted — never optional, never stub-only
- The pipeline is: load → extract → signals → **build_study_state** → package
- Downstream systems read `study_state.json`, not raw extraction outputs
- The study state accumulates across the lifecycle of the study; it is never reset

**What this does not mean:**
- The study state replaces the structured extraction; both are always packaged
- The study state is a final product; it is enriched over time

---

## Rule 4 — Reliability-First

**Deterministic, reproducible outputs are non-negotiable.  Stochastic or non-reproducible behavior is a defect.**

Every module must:
- Accept the same inputs and produce the same outputs every time it is run
- Write all output files in a canonical format (JSON with `indent=2`, `sort_keys=True`)
- Use a deterministic run_id derived from input content, not from wall clock time
- Record `generated_at` timestamps but not use them to derive output content

**What this means:**
- `artifact_packager.package_artifacts()` always writes the same files to the same paths for the same `run_id`
- `build_study_state()` always produces the same document for the same inputs
- The pipeline does not call external services during artifact construction
- Random IDs (UUIDs) are used only for fields where no deterministic ID is available from the extraction output

**What this does not mean:**
- Timestamps are removed; they are recorded for provenance
- UUIDs are prohibited; they are used as fallback IDs when no stable ID is present in the source

---

## Rule 5 — No Dropped Signal

**Every signal extracted from a transcript must appear in the artifact package.  Silent drops are defects.**

The no-dropped-signal rule is the strongest data integrity guarantee in the system.  It means:

- Every `action_item` extracted from a transcript must appear in `study_state.action_items`
- Every `risk_or_open_question` must appear in `study_state.risks`
- Every `decision` must appear in `study_state.decisions`
- If a signal cannot be mapped, it must appear in `validation_report.json` with an explanation

The validation layer in `artifact_packager.validate_package()` enforces this rule by checking count parity between source documents and the study state.

**What this means:**
- Count mismatches between `structured_extraction.action_items` and `study_state.action_items` are validation errors
- Count mismatches between `signals.risks_or_open_questions` and `study_state.risks` are validation errors
- Validation errors do not block package writing but are always surfaced in `validation_report.json`

**What this does not mean:**
- Every signal is published without review; low-confidence signals are flagged for human review
- Signals are never filtered; filtering requires an explicit human decision recorded in the validation report

---

## Rule 6 — Always Emit All Files

**The artifact package always contains all seven required files.  Missing inputs produce stubs, not omissions.**

The canonical package shape is:

```
/artifacts/<run_id>/meeting_minutes/
    meeting_minutes.docx
    structured_extraction.json
    signals.json
    study_state.json
    recommendations.json
    validation_report.json
    execution_metadata.json
```

Every run that completes the package stage must produce all seven files.  If a file's content is not available, a stub marker is written.  Stubs are valid; absent files are defects.

This rule ensures that downstream consumers always have a predictable directory structure to read from, regardless of which pipeline stages completed successfully.

---

## Summary

| Rule | One-liner |
|------|-----------|
| Module-first | Build inside `spectrum-systems`, not in a new repo |
| Golden path | One canonical way; no parallel implementations |
| Study-state-first | The study state is the primary product of every run |
| Reliability-first | Deterministic, reproducible outputs always |
| No dropped signal | Every extracted signal appears in the artifact package |
| Always emit all files | Seven files, every run; stubs are valid, omissions are defects |

---

## See Also

- `docs/architecture/study_state_model.md` — study state schema and lifecycle
- `docs/architecture/signal_extraction_model.md` — signal types and extraction rules
- `docs/architecture/action_item_continuity.md` — action item propagation rules
- `docs/architecture/module-pivot-roadmap.md` — the architectural pivot to module-first
