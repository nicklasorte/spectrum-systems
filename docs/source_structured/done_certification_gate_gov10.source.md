# Done Certification Gate GOV10 Design — Structured Source Artifact

## Purpose
Repo-native structured source artifact for Source Authority Layer ingestion.

## machine_source_document
```json
{
  "source_id": "SRC-DONE-CERTIFICATION-GATE-GOV10",
  "title": "Done Certification Gate GOV10 Design",
  "filename": "done_certification_gate_gov10.pdf",
  "path": "docs/source_structured/done_certification_gate_gov10.source.md",
  "source_type": "project_pdf",
  "status": "inactive",
  "notes": "FAIL_CLOSED: Automated PDF text extraction is unavailable in the current environment (no PDF parser tooling present). Source converted to inventory metadata only; no source-grounded obligations extracted.",
  "system_layers": [
    "governance",
    "certification"
  ],
  "trust_boundaries": [
    "promotion_boundary",
    "control_gate"
  ],
  "control_loop_relevance": "unknown_unparsed",
  "learning_loop_relevance": "unknown_unparsed"
}
```

## machine_obligations
```json
[]
```

## ingestion_status
- parse_status: `failed_closed`
- parse_basis: `pdftotext not installed; Python PDF libraries unavailable in environment.`
- conversion_decision: `Create metadata-only structured artifact and withhold obligations until parseable extraction is available.`
