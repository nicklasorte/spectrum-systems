# Source Authority Layer

## Purpose
The source authority layer makes design-source usage deterministic, auditable, and fail-closed for roadmap generation, architecture reconstruction, and governed extraction.

## Core model

### 1) Raw PDFs are inputs, not runtime authority
Files in `docs/source_raw/` are preserved as raw source inputs.
They are not directly authoritative for runtime workflows, roadmap prompts, or governance decisions.

### 2) Structured extraction artifacts are the usable design surface
Each source in `docs/source_raw/*.pdf` maps to a governed structured artifact in `docs/source_structured/*.json`.
These artifacts are validated by `contracts/schemas/source_design_extraction.schema.json` and carry explicit:
- components
- invariants
- authority boundaries
- required schemas
- sequencing constraints
- failure and fail-closed requirements
- replayability and observability requirements
- certification requirements
- SRE alignment
- non-goals
- roadmap implications
- source traceability rows

### 3) Deterministic indexes are the enforcement spine
`python scripts/build_source_indexes.py` validates every structured extraction and emits:
- `docs/source_indexes/source_inventory.json`
- `docs/source_indexes/obligation_index.json`
- `docs/source_indexes/component_source_map.json`

Outputs are stable-sorted and fail-closed:
- malformed structured files terminate generation
- undocumented duplicate `obligation_id` values terminate generation
- missing raw PDFs are represented as `status: "missing"` in inventory instead of inferred content

## Source authority hierarchy
Roadmap and architecture generation must apply this precedence order:

1. **Repository implementation** (code, tests, contracts)
2. **Source documents** (as represented through structured extraction artifacts)
3. **Architectural invariants** (explicitly declared and validated)
4. **Inferred gap fill** (allowed only when explicitly marked and traceable)

## Prompt consumption rule
Roadmap prompts must consume `docs/source_indexes/source_inventory.json` and `docs/source_indexes/obligation_index.json` to prove:
- which sources were included
- which obligations were derived
- which components each source obligation constrains

Prompts must not rely on raw PDF files alone as evidence.

## Fail-closed behavior expectations
- If a source PDF is unavailable, the structured extraction may exist with `source_document.status = "missing"` and explicit notes.
- The index layer continues to report missing status; it does not invent obligations from unavailable source content.
- Any malformed extraction blocks index generation until corrected.
