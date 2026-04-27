# H08 — Transcript Ingestion Fix Plan

- **Plan id:** `H08-FIX-PLAN`
- **Source review:** `RVA-H08-INGEST-001` (`docs/reviews/H08_transcript_ingestion_review.md`)
- **Batch:** `BATCH-H08`
- **Date:** 2026-04-27
- **Status:** all eight findings closed in-batch (`contracts/review_actions/H08_fix_actions.json`).

## Findings → fixes

| Finding | Severity | Fix id | Closure |
|---|---|---|---|
| F-001 empty / whitespace-only input | S3 | H08-FIX-001 | parser raises `EMPTY_TRANSCRIPT`; schema requires `speaker_turns` minItems: 1. |
| F-002 prose without delimiters | S3 | H08-FIX-002 | parser raises `NO_SPEAKER_TURNS`. |
| F-003 oversize input | S2 | H08-FIX-003 | 5 MiB cap with `INPUT_FILE_TOO_LARGE` raised before any read. |
| F-004 non-UTF-8 bytes | S2 | H08-FIX-004 | `UnicodeDecodeError` → `INPUT_NOT_UTF8`. |
| F-005 non-deterministic ids | S3 | H08-FIX-005 | `session_id` / `artifact_id` derived from `sha256(filename || raw_text)`; replay caught by store. |
| F-006 direct artifact writes | S2 | H08-FIX-006 | regression test asserts envelope-check rejection. |
| F-007 trace_id/span_id format | S1 | H08-FIX-007 | ingestor boundary validates 32-hex / 16-hex. |
| F-008 content_hash boundary docs | S0 | H08-FIX-008 | module docstring + return-value comment. |

## Tests

Regression tests live under `tests/transcript_pipeline/test_transcript_ingestor_h08.py::TestRedTeamRegressions`
and the per-step test classes (`TestSchemaAudit`, `TestParserDeterminism`,
`TestIngestPayload`, `TestPQXIntegration`, `TestArtifactStoreInvariants`).

## Re-run results

```
$ python -m pytest tests/transcript_pipeline -q
...
296 passed
```

(38 new H08 tests, 258 pre-existing tests, all green.)

## Residual risk

- `vtt|srt|json|docx` source formats are accepted by the schema but parsed only as
  `txt`. Tracked for a follow-up batch.
- Duplicate input lines preserved verbatim — context-bundle assembly (H09) is
  responsible for downstream dedup signalling.
