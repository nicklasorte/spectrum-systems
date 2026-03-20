# Strategic Knowledge Layer Foundation

## Repository split

- `spectrum-data-lake` is the durable storage plane for raw and extracted Strategic Knowledge artifacts.
- `spectrum-systems` is the governed execution plane for schemas, validators, path contracts, CLIs, and tests.
- The split prevents extraction orchestration from becoming a production artifact store.

## Artifact-first architecture

The foundation is designed around governed artifact contracts before extraction logic:

- source references are registered in `source_catalog.json`
- extraction outputs must conform to strategic knowledge artifact schemas
- lineage/provenance are first-class required fields

## Data-lake structure (governed target)

```text
strategic_knowledge/
  raw/books/
  raw/transcripts/
  raw/slides/
  processed/book_intelligence/
  processed/transcript_intelligence/
  processed/slide_intelligence/
  processed/story_bank/
  processed/tactic_registers/
  processed/viewpoint_packs/
  processed/assumption_registers/
  processed/contradiction_findings/
  processed/evidence_maps/
  indexes/
  metadata/
  lineage/
```

`python scripts/strategic_knowledge_init.py --data-lake-root <path>` provisions and verifies this deterministic structure.

## Source and artifact types

### Source types
- `book_pdf`
- `transcript`
- `slide_deck`

### Artifact types
- `book_intelligence_pack`
- `transcript_intelligence_pack`
- `story_bank_entry`
- `tactic_register`
- `viewpoint_pack`
- `evidence_map`

## Provenance model

Each extracted artifact family is scaffolded to carry:

- `source_id`, `source_type`, `source_path`
- `extraction_run_id`, `extractor_version`
- `artifact_version`, `schema_version`
- `created_at`
- evidence anchors for source grounding

## Evidence anchors

Contracts support both:

- PDF anchors (`page_number`, optional `text_span`, optional `quote_snippet`)
- Transcript anchors (`timestamp_start`, `timestamp_end`, optional `speaker`, optional `quote_snippet`)

## Pathing contract

`strategic_knowledge.pathing` provides deterministic source and artifact path builders so future extractors can write artifacts into the correct data-lake directories without ad hoc path assembly.

## What later prompts should implement

1. **Book extraction module**: parse PDFs, create governed `book_intelligence_pack` + downstream artifacts.
2. **Transcript extraction module**: parse transcripts with timestamp/speaker anchoring and emit transcript-specific intelligence packs.
3. **Indexing and retrieval**: populate `strategic_knowledge/indexes/` with deterministic retrieval indexes and lookup manifests.

This foundation intentionally excludes extraction intelligence, ranking logic, embedding infrastructure, or retrieval runtime services.
