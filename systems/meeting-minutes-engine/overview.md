# Meeting Minutes Engine (SYS-006)

Purpose: convert meeting transcripts into governed, traceable minutes aligned to the canonical meeting minutes contract.

- **Bottleneck**: BN-005 — meeting output evaporates without structured minutes and transcript traceability.
- **Inputs**: meeting transcript with speaker/timestamps; meeting minutes DOCX template; optional prior context artifacts (prior minutes, meeting agenda, resolution matrices, supporting documents).
- **Outputs**: `meeting_minutes.json`, `meeting_minutes.docx`, `validation_report.json` aligned to `contracts/meeting_minutes_contract.yaml` with manifest and provenance.
- **Upstream Dependencies**: transcript capture with timestamps, template version control, upstream agenda and resolution artifacts when available.
- **Downstream Consumers**: agenda generation, spectrum-program-advisor readiness pipeline, data lake ingestion, decision/risk registries.
- **Related Assets**: `contracts/meeting_minutes_contract.yaml` (authoritative contract), `contracts/standards-manifest.json` entry for `meeting_minutes`, `systems/meeting-minutes-engine/interface.md`.
- **Lifecycle Status**: Design drafted; evaluation harness to be added per `docs/system-status-registry.md`.

Downstream repos must not add unsupported fields to the meeting minutes outputs and must preserve transcript traceability/provenance when available.
