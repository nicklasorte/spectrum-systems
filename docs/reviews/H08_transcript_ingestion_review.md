# H08 — Transcript Ingestion Red-Team Review

- **Review id:** `RVA-H08-INGEST-001`
- **Reviewer:** `ARA-H08`
- **Reviewed batch:** `BATCH-H08`
- **Review signal:** `revision_recommended` (all S2+ findings closed in-batch — see `H08_fix_actions.json`)
- **Authority boundary:** This is a non-authority review signal. Control authority remains with CDE; compliance authority remains with SEL; release authority remains with REL/GOV. Nothing here is a routing or release ruling.
- **Date:** 2026-04-27

## Scope

Adversarial review of the H08 transcript ingestion path:

- `contracts/schemas/transcript_pipeline/transcript_artifact.schema.json`
- `spectrum_systems/modules/transcript_pipeline/transcript_ingestor.py`
- `spectrum_systems/modules/orchestration/pqx_step_harness.py` (consumer-side checks only)
- `spectrum_systems/modules/runtime/artifact_store.py` (consumer-side checks only)
- `tests/transcript_pipeline/fixtures/`

## Attack surface

| Vector | What we tried |
|---|---|
| Schema bypass | Add unknown fields, drop required envelope fields, malformed `session_id`, empty `speaker_turns`. |
| Trace gaps | Drop `trace`, send malformed `trace_id` / `span_id`. |
| Provenance gaps | Drop `provenance`, omit `produced_by`. |
| Malformed input pass-through | Pure prose with no `Speaker:` markers, whitespace-only, empty file. |
| Inconsistent parsing | Repeated lines, mixed-case speakers, oversize file, non-UTF-8 bytes. |
| Direct artifact writes | Skip the PQX harness and call `ArtifactStore.register_artifact` directly. |
| Replay collision | Re-ingest the same input file (deterministic id). |

## Findings (severity ladder S0–S4)

| ID | Severity | Description | Recommendation | Blocking |
|---|---|---|---|---|
| F-001 | S3 | Empty / whitespace-only input could silently produce a zero-turn payload. | Reject in `parse_transcript_text` with `EMPTY_TRANSCRIPT`; schema requires `minItems: 1` on `speaker_turns`. | yes |
| F-002 | S3 | Pure prose without speaker delimiters could be admitted as a "raw" transcript with no structure. | Require `NO_SPEAKER_TURNS` failure in parser; schema rejects empty `speaker_turns`. | yes |
| F-003 | S2 | Oversize input could be opened and read into memory before parsing. | Bound input at 5 MiB; raise `INPUT_FILE_TOO_LARGE` before any read. | yes |
| F-004 | S2 | Non-UTF-8 byte streams could leak `UnicodeDecodeError` into the harness as `EXECUTION_EXCEPTION` with low diagnostic value. | Catch `UnicodeDecodeError` and re-raise as `INPUT_NOT_UTF8`. | yes |
| F-005 | S3 | Re-ingesting the same file could create two artifacts with different ids, breaking replay. | Derive `session_id` and `artifact_id` deterministically from `(filename, raw_text)`; rely on `ArtifactStore` `DUPLICATE_ARTIFACT_ID`. | yes |
| F-006 | S2 | Hand-crafted artifacts could be passed directly to `ArtifactStore.register_artifact`, bypassing PQX trace propagation. | Already validated by store envelope checks; add explicit regression test (`test_F006`). | yes |
| F-007 | S1 | `trace_id` / `span_id` not validated by the ingestor — relies entirely on PQX. | Add format guard in `ingest_transcript` (32-hex / 16-hex) so the function is safe to call outside the harness in tests. | no |
| F-008 | S0 | Documentation does not state that `content_hash` is computed by the artifact store, not the ingestor. | Add explicit note in module docstring and ingestor return-value comment. | no |

No S4 findings.

## Outcome

All S2+ findings closed in-batch with code + regression tests. See:

- `contracts/review_actions/H08_fix_actions.json`
- `docs/review-actions/H08_fix_plan.md`
- `tests/transcript_pipeline/test_transcript_ingestor_h08.py::TestRedTeamRegressions`

Post-fix run: `pytest tests/transcript_pipeline -q` → all green (296 tests).

## Remaining risk

- Source formats other than `txt` are accepted in the schema but parsing is currently
  txt-only. `vtt|srt|json|docx` parsers are out of scope for H08 and must be added
  before those source formats are admitted in production. Tracked for H09+.
- Duplicate input lines are preserved as ordered turns. Downstream normalization
  (H09 / context bundle assembly) is responsible for dedup signalling.
