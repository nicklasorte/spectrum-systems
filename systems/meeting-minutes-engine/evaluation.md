# Meeting Minutes Engine — Evaluation (SYS-006)

## Evaluation Goals
- Validate `meeting_minutes.json` against `contracts/meeting_minutes_contract.yaml` with zero extra fields.
- Confirm JSON ↔ DOCX parity for executive summary, decisions, agenda-item summaries, action items, risks/open questions, and next-meeting details.
- Ensure every summary element carries transcript traceability (speaker, timestamp, agenda item) when the source provides it.
- Verify determinism across reruns with identical inputs, prompts, and template versions.
- Assert validation reports capture manifest/provenance completeness and block publication on failures.

## Assets
- Contract: `contracts/meeting_minutes_contract.yaml`.
- Template: meeting minutes DOCX template (version-controlled in downstream repo).
- Fixtures: transcripts with speaker/timestamps plus optional context artifacts (prior minutes, agenda, resolution matrices) — to be added under `eval/meeting-minutes-engine`.

## Test Matrix
- **Contract compliance**: schema/contract validation of `meeting_minutes.json`; failure on additional properties or missing required sections.
- **Traceability coverage**: assert each decision, action item, and agenda-item summary includes transcript references when available.
- **Parity checks**: diff JSON vs. DOCX content; mismatches are blocking.
- **Determinism**: rerun with fixed seeds/prompts/model hash/template version and compare outputs byte-for-byte aside from run metadata.
- **Context sensitivity**: add/remove prior minutes or resolution matrices and verify carry-forward items and decisions update accordingly.
- **Validation reporting**: ensure `validation_report.json` records contract version, template version, prompt/rule versions, model hash, provenance completeness, and any blocking errors.

## Metrics
- Validation pass rate.
- Traceability coverage (% of items with timestamp + speaker + agenda item).
- JSON↔DOCX parity status.
- Deterministic run stability rate.

## Review Gates
- Human approval of executive summary, decisions, and action items when confidence is low or when agenda alignment is ambiguous.
- Manual spot checks of traceability links against transcript excerpts.

## Tooling
- Use contract validation utilities from `spectrum_systems` downstream to enforce `meeting_minutes_contract`.
- Keep prompts/rules versioned and captured in run manifests for reproducibility.
