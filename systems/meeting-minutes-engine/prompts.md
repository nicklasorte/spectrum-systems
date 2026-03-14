# Meeting Minutes Engine — Prompts (SYS-006)

Prompting and rules must enforce the canonical minutes structure and deterministic outputs.

## Objectives
- Generate contract-aligned minutes from transcripts while preserving transcript traceability (speaker, timestamp, agenda item).
- Populate required sections: executive summary, decisions made, agenda-item summaries, action items, risks/open questions, next meeting, and traceability.
- Respect prior context artifacts (prior minutes, agenda, resolution matrices) when provided; carry forward unresolved items explicitly.

## Prompt Requirements
- State that outputs must match `contracts/meeting_minutes_contract.yaml` exactly; no extra fields or renamed keys.
- Require deterministic generation given identical inputs and seeds; avoid stochastic sampling that could reorder items.
- Instruct models to attach source references (speaker, timestamp, agenda item) to every decision, action item, and agenda-item summary when transcripts allow.
- Enforce separation of fact vs. inference; mark low-confidence items and route them to human review paths.
- Preserve wording fidelity for decisions and action items; avoid policy expansion beyond transcript evidence.
- Use the provided DOCX template structure for section ordering to keep JSON and DOCX aligned.

## Review Hooks
- Surface low-confidence items and agenda alignment ambiguities for human approval.
- Emit validation flags in `validation_report.json` when traceability or parity checks fail.

## Versioning
- Version prompts/rules alongside template versions; include both in the run manifest captured in `validation_report.json`.
