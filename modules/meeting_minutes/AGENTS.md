# AGENTS.md — modules/meeting_minutes

## Ownership
Meeting Minutes module — transcript-to-structured-minutes pipeline.
Implementation source of truth: `spectrum_systems/modules/meeting_minutes_pipeline.py`
Artifact packager: `spectrum_systems/modules/artifact_packager.py`

## Local purpose
Transform meeting transcripts into structured minutes, signals, study state snapshots, and recommendations.
All outputs must conform to the `meeting_minutes_record` contract (`contracts/schemas/meeting_minutes.schema.json`).
The artifact packager emits a deterministic 7-file output bundle under `/artifacts/<run_id>/meeting_minutes/`.

## Constraints
- Output must be fully deterministic: same transcript input → same structured output.
- All JSON output: `indent=2, sort_keys=True`.
- The 7-file artifact bundle structure (meeting_minutes.docx, structured_extraction.json, signals.json, study_state.json, recommendations.json, validation_report.json, execution_metadata.json) is a contract boundary — do not add or remove files without a PLAN prompt.
- Do not modify the `meeting_minutes_record` schema without a corresponding contract version bump in `contracts/standards-manifest.json`.

## Required validation surface
Before any `BUILD` or `WIRE` prompt is marked complete:
1. Run `pytest tests/test_meeting_minutes_contract.py`.
2. Verify at least one golden-path case in `cases/meeting_minutes/examples/` produces a valid artifact bundle.
3. Run `.codex/skills/golden-path-check/run.sh meeting_minutes_record`.

## Files that must not be changed casually
| File | Reason |
| --- | --- |
| `contracts/schemas/meeting_minutes.schema.json` | Output contract — changes require PLAN + version bump |
| `contracts/schemas/meeting_agenda_contract.schema.json` | Downstream contract — changing breaks agenda generation |
| `spectrum_systems/modules/artifact_packager.py` | Shared packager — changes affect all modules that emit bundles |
| `contracts/standards-manifest.json` | Version registry — update only after a contract version bump |

## Nearby files (read before editing)
- `spectrum_systems/modules/meeting_minutes_pipeline.py` — pipeline orchestration
- `spectrum_systems/modules/artifact_packager.py` — artifact bundle emission
- `spectrum_systems/modules/study_state.py` — study state tracking
- `contracts/schemas/meeting_minutes.schema.json` — output contract
- `contracts/examples/` — golden-path fixtures
- `cases/meeting_minutes/examples/` — realistic test cases
- `tests/test_meeting_minutes_contract.py` — primary test surface
