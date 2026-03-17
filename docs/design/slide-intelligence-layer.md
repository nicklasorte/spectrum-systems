# Slide Intelligence Layer

## Purpose

The Slide Intelligence Layer fuses presented slide content with meeting
transcripts to produce a structured, aligned, and analysis-ready
representation. Its primary purpose is to:

- Treat slide decks as **first-class governed artifacts**, not mere
  attachments.
- Surface claims, assumptions, and proposals embedded in presentation
  content.
- Align slide evidence with the spoken record to identify gaps, support
  decisions, and seed working-paper generation.
- Feed the downstream working-paper generation pipeline with structured,
  traceable intelligence.

---

## Architecture Diagram (Textual)

```
Slide Deck (PDF / JSON fixture)
    │
    ▼
┌──────────────────────────────────┐
│  A. ingest_slides(pdf_path)      │  Raw per-slide objects
│     • PDF parser (pdfplumber /   │  slide_number, title,
│       pypdf)                     │  bullet_points, full_text
│     • JSON fixture support       │
└─────────────────┬────────────────┘
                  │
                  ▼
┌──────────────────────────────────┐
│  B. normalize_slides(raw)        │  Normalized schema:
│     • Canonical slide_id         │  slide_id, title, bullets,
│     • Keyword extraction         │  raw_text, keywords
│       (noun-heavy heuristics)    │
└─────────────────┬────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
┌─────────────────┐  ┌──────────────────────────────┐
│  C. extract_    │  │  D. align_slides_to_          │
│     slide_      │  │     transcript(slides, segs)  │
│     signals()   │  │     • TF-IDF cosine sim       │
│  claims         │  │     • Keyword overlap          │
│  assumptions    │  │     • Many-to-many mapping    │
│  proposals      │  └──────────────┬───────────────┘
│  metrics        │                 │
│  open_questions │                 │
└────────┬────────┘                 │
         │                          │
         └────────────┬─────────────┘
                      │
                      ▼
         ┌──────────────────────────────┐
         │  E. merge_slide_transcript_  │
         │     outputs(structured,      │
         │     signals, alignment_map)  │
         │  • Attach slide_support      │
         │  • source_slide_ids          │
         │  • Identify slide-only       │
         │  • Identify discussion-only  │
         └──────────────┬───────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │  F. compute_slide_           │
         │     transcript_gaps(record)  │
         │  • unpresented_discussions   │
         │  • undiscussed_slides        │
         │  • weak_alignment_areas      │
         │  • recommended_followups     │
         └──────────────┬───────────────┘
                        │
                        ▼
                ┌───────────────┐
                │  Gap Report   │ → agency questions
                │               │ → working paper gaps
                └───────────────┘
```

The module also exposes a richer per-slide analysis API
(`extract_slide_units`, `score_slide_signal`, `classify_slide_role`,
`extract_claims`, `extract_assumptions`, `detect_gaps`,
`rewrite_for_working_paper`, `build_slide_intelligence_packet`) which
produces a full `slide_intelligence_packet` governed artifact.

---

## Data Flow

### Inputs

| Input | Type | Required |
|-------|------|----------|
| Slide deck | PDF or JSON fixture | Optional |
| Transcript | Plain text or segmented dict | Optional (for alignment) |
| Structured extraction | Meeting-minutes dict | Optional (for merge) |

### Outputs

| Output | Description |
|--------|-------------|
| `normalized_slides` | Canonical per-slide records with keywords |
| `alignment_map` | Slide ↔ transcript segment mapping with confidence scores |
| `slide_signals` | Claims, assumptions, proposals, metrics, questions |
| `enriched_record` | Structured extraction enriched with slide evidence |
| `gap_report` | Unpresented discussions, undiscussed slides, follow-ups |
| `slide_intelligence_packet` | Full governed artifact (all of the above + KG edges) |

### Contract Integration

The `meeting_minutes_record` schema accepts the following **optional** fields:

- `slides_present` — boolean, whether slides were processed
- `slide_alignment` — alignment map (slide_id → matched_segments + confidence)
- `slide_signals` — extracted signals (claims, assumptions, proposals, etc.)
- `gap_analysis` — gap report (unpresented, undiscussed, weak areas, followups)

These fields are validated when present but are never required, ensuring full
backward compatibility with existing pipeline runs.

---

## Pipeline Integration

The `meeting_minutes_pipeline.run_pipeline()` function accepts an optional
`slide_deck` parameter. When provided:

1. The slide deck is processed through `build_slide_intelligence_packet()`.
2. The resulting `slide_intelligence_packet` is attached to the package result
   under the `slide_intelligence` key.
3. If slide processing fails for any reason, the error is logged as a warning
   and the pipeline continues — **slides are always optional**.

```python
from spectrum_systems.modules.meeting_minutes_pipeline import run_pipeline

result = run_pipeline(
    transcript_text="...",
    structured_extraction={...},
    signals={...},
    slide_deck={          # ← optional; pipeline succeeds without it
        "artifact_id": "SLIDE-DECK-001",
        "artifact_type": "slide_deck",
        "presenting_org": "FCC OET",
        "slides": [...],
    },
)
# result["slide_intelligence"] contains the full packet when slides present
```

---

## Known Limitations

1. **PDF parsing is best-effort.** Slide layout, multi-column text, and
   embedded images are not fully captured. The extractor operates on raw
   text only.
2. **Keyword extraction is heuristic.** The noun-heavy tokenizer uses
   stop-word filtering and capitalization signals, not a true NLP model.
   Domain-specific technical terms are explicitly boosted via keyword tables.
3. **Alignment is TF-IDF-based.** The cosine similarity approach may miss
   semantic relationships that differ in vocabulary (synonymy, paraphrase).
4. **No figure/table content extraction.** Figures and tables referenced in
   slides are noted (via `figures_present` / `tables_present` flags) but
   their actual visual content is not analyzed.
5. **Many-to-many alignment is bounded.** Very long transcripts may produce
   noisy alignment matches. A confidence threshold (0.05) is applied to
   filter low-quality matches.

---

## Future: LLM-Based Semantic Alignment *(NOT implemented)*

The current implementation is intentionally **deterministic and rule-based**
(no LLM calls, no embeddings, no network access). Future work may include:

- **Semantic alignment** using sentence embeddings (e.g., SBERT) for
  higher-fidelity slide-to-transcript matching.
- **LLM-assisted claim verification** to cross-check slide claims against
  cited sources and prior working-paper drafts.
- **Automated figure description** using multimodal models to extract
  signal from slide charts, diagrams, and tables.
- **Incremental alignment updates** as transcript streams arrive in real time.

Any LLM integration must be introduced as an optional, clearly-flagged
enhancement layer that does not alter the deterministic baseline behaviour.

---

## Related Artifacts

- `spectrum_systems/modules/slide_intelligence.py` — implementation
- `contracts/schemas/slide_deck.schema.json` — governed slide deck schema
- `contracts/schemas/slide_intelligence_packet.schema.json` — packet schema
- `contracts/schemas/knowledge_graph_edge.schema.json` — KG edge schema
- `contracts/schemas/meeting_minutes_record.schema.json` — enriched record
- `tests/test_slide_intelligence.py` — full test suite
- `tests/fixtures/slide_deck_fixture.json` — test fixture
- `docs/module-manifests/workflow_modules/slide_intelligence.json` — manifest
- `docs/slide-intelligence-usage.md` — usage guide
