# TRN-11 Red Team Review 1 — Parsing + Schema + Fail-Closed

## Scope
Parser determinism, schema strictness, ambiguity encoding, evidence anchors, malformed source handling.

## Findings
- S2: Normalized transcript line objects allowed weak structure; evidence linking risk.
- S2: Chunk artifacts did not require explicit evidence spans.
- S2: Parser ambiguity encoding did not preserve conflicting attribution markers.
- S1: Failure artifact shape was not standardized.

## Fixes applied
- Hardened transcript schemas to `1.1.0` with strict required fields and `additionalProperties: false`.
- Added deterministic ambiguity flags (`unknown_speaker`, `missing_timestamp`, `conflicting_attribution`, `uncertain_section_boundary`, `low_confidence_region`).
- Added required `evidence_spans` in chunk artifacts and stronger evidence spans in fact artifacts.
- Added explicit `transcript_ingest_failure_artifact` generation path.

## Severity counts
- S0: 0
- S1: 1
- S2: 3
- S3: 0
- S4: 0
