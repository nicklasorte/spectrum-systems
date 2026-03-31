# Agent Eval Integration Design — Structured Source Artifact

## Purpose
Repo-native structured source artifact for Source Authority Layer ingestion.

## machine_source_document
```json
{
  "source_id": "SRC-AGENT-EVAL-INTEGRATION-DESIGN",
  "title": "Agent Eval Integration Design",
  "filename": "agent_eval_integration_design.pdf",
  "path": "docs/source_structured/agent_eval_integration_design.source.md",
  "source_type": "project_pdf",
  "status": "inactive",
  "notes": "FAIL_CLOSED: Automated PDF text extraction is unavailable in the current environment (no PDF parser tooling present). Source converted to inventory metadata only; no source-grounded obligations extracted.",
  "system_layers": [
    "evaluation",
    "integration"
  ],
  "trust_boundaries": [
    "adapter_boundary",
    "source_authority"
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
