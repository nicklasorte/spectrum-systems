# Google SRE Mapping — Structured Source Artifact

## Purpose
Repo-native structured source artifact for Source Authority Layer ingestion.

## machine_source_document
```json
{
  "source_id": "SRC-GOOGLE-SRE-MAPPING",
  "title": "Google SRE Mapping",
  "filename": "google_sre_mapping.pdf",
  "path": "docs/source_structured/google_sre_mapping.source.md",
  "source_type": "project_pdf",
  "status": "inactive",
  "notes": "FAIL_CLOSED: Automated PDF text extraction is unavailable in the current environment (no PDF parser tooling present). Source converted to inventory metadata only; no source-grounded obligations extracted.",
  "system_layers": [
    "operations",
    "reliability"
  ],
  "trust_boundaries": [
    "reliability_boundary",
    "control_feedback"
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
