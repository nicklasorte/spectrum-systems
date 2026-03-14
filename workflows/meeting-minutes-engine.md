# Meeting Minutes Engine

## Purpose
Convert raw meeting transcripts into contract-governed minutes (JSON + DOCX) with transcript traceability, determinism, and downstream readiness for the spectrum-pipeline-engine.

## Steps
1. Ingest transcript payload and template; normalize encoding, timezone, and speaker identifiers; block if contract pins or template versions are missing.
2. Parse speaker labels and timestamps; segment utterances and align to agenda items when context is available.
3. Generate structured minutes (executive summary, decisions, agenda-item summaries, action items, risks/open questions, next meeting, traceability anchors) strictly mapped to `meeting_minutes_contract`.
4. Validate structured JSON against the contract schema and provenance requirements; fail on extra/missing fields or incomplete traceability when timestamps/speakers exist.
5. Render DOCX from the supplied template using the structured payload; verify JSON ↔ DOCX content parity and template compatibility.
6. Emit validation report and run manifest capturing contract/template versions, prompt/rule/model pins, determinism checks, and artifact checksums.

## Inputs
- Meeting transcript with speaker labels and timestamps (required; rejection on absence).
- Meeting minutes DOCX template (required, version-controlled).
- Contract schema reference: `contracts/meeting_minutes_contract.yaml` (authoritative fields and nesting).
- Optional contextual artifacts: prior minutes, meeting agenda, resolution matrices/comment dispositions, supporting documents, policy context notes.
- Run configuration: prompt/rule versions, model hash/seed, determinism policy, template identifier, contract version pins.

## Outputs
- `meeting_minutes.json` conforming exactly to `meeting_minutes_contract` with transcript span references.
- `meeting_minutes.docx` rendered from the supplied template and parity-checked against the JSON payload.
- `validation_report.json` detailing contract validation, template compatibility, determinism, and provenance coverage.
- Artifact manifest entry capturing input checksums, output artifact references (JSON/DOCX/validation), contract/template/prompt/rule/model pins, and operator metadata.

## Interface with spectrum-pipeline-engine
- Provides validated minutes (JSON + DOCX + validation report + manifest entry) as upstream inputs to agenda generation and readiness bundling.
- Minutes must retain identifiers and traceability anchors so the pipeline can link agenda items and readiness artifacts back to transcript spans and decisions.
- Pipeline consumption requires the manifest to declare contract/template versions and checksums; any drift or missing validation report must block orchestration.

## Failure Modes
- Transcripts without timestamps (block; insufficient traceability).
- Transcripts without speaker labels (block; attribution missing).
- Malformed transcript segments (non-parseable timestamps, overlapping spans, or speaker collisions).
- Template mismatch with contract schema (missing placeholders, ordering drift, or incompatible version).

## References
- Interface: `systems/meeting-minutes-engine/interface.md`
- Design: `systems/meeting-minutes-engine/design.md`
- Contracts: `contracts/meeting_minutes_contract.yaml`, `contracts/standards-manifest.json`
- Prompts: `systems/meeting-minutes-engine/prompts.md`
- Evaluation: `systems/meeting-minutes-engine/evaluation.md`
