# Meeting Minutes Engine — Interface (SYS-006)

## Purpose
Transform raw meeting transcripts into structured institutional memory while emitting contract-governed minutes in JSON and DOCX formats.

## Inputs
- Meeting transcript with speaker labels and timestamps (required).
- Meeting minutes DOCX template (required, version-controlled).
- Optional prior context artifacts: prior minutes, meeting agenda, resolution matrices/comment dispositions, supporting documents, and policy context notes.
- Run configuration capturing prompt/rule versions, model settings, and template identifiers.

## Contracts and Schemas
- Canonical contract: `contracts/meeting_minutes_contract.yaml` (authoritative field names and nesting).
- Provenance expectations: align to `docs/data-provenance-standard.md`; run manifests must record contract version, template version, model hash, and prompt/rule versions.
- Downstream repos must not invent unsupported fields or rename contract keys; extensions require a contract update published in this repo.

## Outputs
- `meeting_minutes.json` conforming exactly to `meeting_minutes_contract` (no extra fields). Must include executive summary, decisions, agenda-item summaries, action items, risks/open questions, next meeting, and transcript traceability.
- `meeting_minutes.docx` rendered from the supplied template with the same content as the JSON payload and stable ordering.
- `validation_report.json` capturing contract validation results, template/render checks, determinism checks, and provenance/run manifest references.

## Validation Rules
- Fail if transcripts are missing timestamps or speakers, or if the template is absent or version-mismatched.
- Reject outputs that introduce fields not defined in `meeting_minutes_contract` or that omit required sections.
- Ensure JSON ↔ DOCX parity (content, ordering, identifiers); mismatches block publication.
- Require linkage to source transcript spans (speaker, timestamp, agenda item) for all summarized content when source data supports it.
- Require deterministic regeneration: repeated runs with identical inputs and prompts must produce byte-stable JSON aside from run metadata.

## Human Review Points
- Review executive summary, decisions, and action items for fidelity to transcript intent.
- Verify traceability links (timestamps, speakers, agenda items) and completeness of optional context usage.
- Approve validation report outcomes before downstream publication.
