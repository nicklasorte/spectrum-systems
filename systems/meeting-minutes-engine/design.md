# Meeting Minutes Engine — Design (SYS-006)

## Purpose
Produce deterministic, contract-governed meeting minutes that convert transcripts into structured institutional memory with transcript traceability.

## Pipeline
1. **Ingest & normalize transcripts**: load transcript with speaker/timestamps; normalize speaker names and agenda references when provided.
2. **Context assembly**: pull prior minutes, agenda, and resolution matrices (if provided) to inform carry-forward items and agenda alignment.
3. **Segmentation & tagging**: segment utterances, align to agenda items or topics, and capture source references (speaker, timestamp, agenda item).
4. **Content extraction**: extract executive summary bullet candidates, decisions, agenda-item summaries, action items, risks/open questions, next meeting details, and transcript traceability anchors.
5. **Structuring**: map extracted content into the exact fields defined in `contracts/meeting_minutes_contract.yaml`; refuse to add ad hoc fields.
6. **Rendering**: produce `meeting_minutes.json` (canonical), render `meeting_minutes.docx` via the supplied template, and ensure parity between JSON and DOCX.
7. **Validation**: validate outputs against the contract and reproducibility requirements; generate `validation_report.json` with run manifest, template/version info, provenance completeness, and determinism checks.
8. **Human review**: route summaries, decisions, and action items for approval when confidence is low or changes are high impact; block publication if review is required and missing.

## Failure Modes
- Missing or ambiguous transcript timestamps leading to weak traceability.
- Agenda misalignment when context artifacts are absent or inconsistent.
- Introduction of non-contract fields or omission of required sections.
- JSON and DOCX divergence due to template drift or rendering errors.
- Non-deterministic outputs across reruns with identical inputs/prompts.

## Mitigations
- Enforce timestamp and speaker presence; surface blocking validation errors when absent.
- Record which context artifacts were available and mark derived outputs accordingly.
- Compare JSON and DOCX content hashes; fail if mismatched.
- Capture prompt/rule versions, model hash, and template version in the run manifest to support deterministic regeneration.

## Implementation Notes
Implementation belongs in a downstream repository. That repo must consume the authoritative contract from `spectrum-systems`, must not invent unsupported fields, and must preserve provenance/traceability whenever the input transcript supports it.
