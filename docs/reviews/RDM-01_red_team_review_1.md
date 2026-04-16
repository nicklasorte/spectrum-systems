# RDM-01 Red Team Review 1 — Schema / Contract / Boundary

## Prompt type
REVIEW

## Findings
- S3: Missing fail-closed ingest guard for non-DOCX source path. **Fixed** via `DownstreamFailClosedError` and source suffix check.
- S2: Missing ambiguity markers when speaker/timestamp parse fails. **Fixed** with deterministic `ambiguity_flags` and confidence downgrade.
- S2: Context bundle contract needed explicit excluded refs + manifest hash for replay. **Fixed** in `meeting_context_bundle` schema/module.
- S1: Transcript-only bias risk if raw text can bypass governed evidence refs. **Fixed** by requiring evidence refs across intelligence/product artifacts.

## Severity counts
- S4: 0
- S3: 1 (fixed)
- S2: 2 (fixed)
- S1: 1 (fixed)
- S0: 0
