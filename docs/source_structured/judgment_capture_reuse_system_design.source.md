# Judgment Capture Reuse System Design — Structured Source Artifact

## Purpose
Repo-native structured source artifact for Source Authority Layer ingestion.

## machine_source_document
```json
{
  "source_id": "SRC-JUDGMENT-CAPTURE-REUSE-SYSTEM-DESIGN",
  "title": "Judgment Capture Reuse System Design",
  "filename": "judgment_capture_reuse_system_design.pdf",
  "path": "docs/source_structured/judgment_capture_reuse_system_design.source.md",
  "source_type": "project_pdf",
  "status": "inactive",
  "notes": "FAIL_CLOSED: Automated PDF text extraction is unavailable in the current environment (no PDF parser tooling present). Source converted to inventory metadata only; no source-grounded obligations extracted.",
  "system_layers": [
    "learning",
    "governance"
  ],
  "trust_boundaries": [
    "learning_boundary",
    "policy_boundary"
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
