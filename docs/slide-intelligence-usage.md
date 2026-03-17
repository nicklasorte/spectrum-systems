# Slide Intelligence — Usage Guide

This guide covers how to use the Slide Intelligence Layer operationally:
expected input shapes, expected output shapes, and concrete examples for each
major output type.

---

## Expected Input: `slide_deck` Artifact

A `slide_deck` artifact is a JSON dict with the following top-level fields.

```json
{
  "artifact_id": "SLIDE-DECK-001",
  "artifact_type": "slide_deck",
  "presenting_org": "Agency Name (optional)",
  "meeting_id": "MTG-2026-03-001 (optional)",
  "study_id": "STUDY-3500-001 (optional)",
  "slides": [
    {
      "slide_number": 1,
      "title": "Slide Title",
      "bullets": ["Bullet 1", "Bullet 2"],
      "notes": "Speaker notes (optional)",
      "raw_text": "Full text blob (optional; built from title+bullets if absent)",
      "has_figure": false,
      "has_table": false,
      "type": "text"
    }
  ]
}
```

**Field notes:**
- `artifact_id` — required; stable identifier used in all traceability fields
- `artifact_type` — must be `"slide_deck"`
- `slides` — ordered array; `slide_number` is required per slide (1-indexed)
- `title` — preferred if present; first non-empty line of `raw_text` is used if absent
- `bullets` and `content` are equivalent; `bullets` is preferred
- `has_figure` / `has_table` — explicit flags; also inferred from `type` or
  keyword presence if not set
- `type` — hint values: `"text"`, `"figure"`, `"table"`, `"diagram"`, `"chart"`, `"image"`

---

## Expected Output: `slide_intelligence_packet`

```json
{
  "artifact_type": "slide_intelligence_packet",
  "source_artifact_id": "SLIDE-DECK-001",
  "slide_to_paper_candidates": [...],
  "extracted_claims": [...],
  "assumptions_registry_entries": [...],
  "knowledge_graph_edges": [...],
  "analysis_gaps": [...],
  "validation_status": "provisional",
  "recommended_agency_questions": [...],
  "suggested_exhibits": [...],
  "signal_scores": [...],
  "traceability_index": [...]
}
```

**`validation_status` values:**
- `needs_review` — high-severity gaps or many low-confidence claims detected
- `provisional` — claims extracted, no high-severity gaps
- `informational` — no claims extracted (e.g., background or exhibit-only deck)

---

## Invoking the Module

```python
from spectrum_systems.modules.slide_intelligence import build_slide_intelligence_packet

# Minimal usage
packet = build_slide_intelligence_packet(slide_deck_artifact)

# With optional cross-artifact inputs
packet = build_slide_intelligence_packet(
    slide_deck_artifact,
    transcript_artifact=transcript,
    working_paper_artifact=paper,
)
```

---

## Example: Slide → Paper-Ready Prose

**Input slide (assumptions)**

```json
{
  "slide_number": 2,
  "title": "Analytical Assumptions",
  "bullets": [
    "5G NR EIRP: 46 dBm per sector, per 3GPP TS 38.104",
    "OOBE level: -13 dBm/MHz at band edge",
    "Propagation model: ITM (Longley-Rice) for terrain-sensitive paths",
    "Receiver threshold: -107 dBm for radar protection criterion"
  ]
}
```

**Output: `slide_to_paper_candidates` entry**

```json
{
  "slide_id": "SLIDE-DECK-001-slide-2",
  "section": "Assumptions and Inputs",
  "integration_role": "source_text",
  "technical_tags": ["assumptions", "link_budget", "propagation"],
  "style_mode": "assumptions_block",
  "proposed_text": "The following assumptions were applied to the analytical assumptions analysis:\n\n  - 5G NR EIRP: 46 dBm per sector, per 3GPP TS 38.104\n  - OOBE level: -13 dBm/MHz at band edge\n  - Propagation model: ITM (Longley-Rice) for terrain-sensitive paths\n  - Receiver threshold: -107 dBm for radar protection criterion\n\nThese inputs should be validated against the consolidated assumptions register before the working paper is finalized.",
  "confidence": "high",
  "caution_flags": [],
  "traceability": {
    "source_slide_id": "SLIDE-DECK-001-slide-2",
    "source_artifact_id": "SLIDE-DECK-001",
    "mapped_section": "Assumptions and Inputs"
  }
}
```

---

## Example: Slide → Assumption Entry

**Input bullet:** `"Guard band: 10 MHz assumed between licensed allocations"`

**Output: `assumptions_registry_entries` entry**

```json
{
  "assumption_id": "ASM-SLIDE-DECK-001-slide-2-GUARD_BAND",
  "type": "guard_band",
  "value": "10 MHz",
  "applies_to": "unspecified",
  "source_slide_id": "SLIDE-DECK-001-slide-2",
  "source_artifact_id": "SLIDE-DECK-001"
}
```

Assumptions with no extractable numeric value will have `"value": null` —
these partial entries signal that the type was detected but the value must be
confirmed from the source material.

---

## Example: Slide → Gap

**Input slide (interference findings, no propagation model stated):**

```json
{
  "slide_number": 3,
  "title": "Interference Analysis Results",
  "bullets": [
    "5G NR base stations may interfere with federal radar receivers within 5 km",
    "Aggregate interference exceeds the protection threshold under dense deployment"
  ]
}
```

**Output: `analysis_gaps` entry**

```json
{
  "gap_id": "GAP-SLIDE-DECK-001-slide-3-001",
  "description": "Interference claim present without stated propagation model.",
  "severity": "high",
  "related_claim_ids": [
    "CLAIM-SLIDE-DECK-001-slide-3-001"
  ],
  "source_slide_id": "SLIDE-DECK-001-slide-3"
}
```

A `high`-severity gap drives `validation_status` to `needs_review` at the
packet level, signalling that the study team should request the propagation
model documentation from the presenting agency before finalising the paper.

---

## Example: Slide → Generated Agency Question

**Input slide (open issues):**

```json
{
  "slide_number": 5,
  "title": "Open Issues and Questions for Agency Review",
  "bullets": [
    "What is the DoD radar receiver threshold under worst-case multipath conditions?",
    "Are coordination zone boundaries aligned with existing federal frequency assignments?",
    "TBD: clutter model for coastal/maritime deployment scenarios"
  ]
}
```

**Output: `recommended_agency_questions` entries**

```json
[
  {
    "slide_id": "SLIDE-DECK-001-slide-5",
    "question_text": "What is the DoD radar receiver threshold under worst-case multipath conditions?",
    "source_artifact_id": "SLIDE-DECK-001"
  },
  {
    "slide_id": "SLIDE-DECK-001-slide-5",
    "question_text": "Are coordination zone boundaries aligned with existing federal frequency assignments?",
    "source_artifact_id": "SLIDE-DECK-001"
  }
]
```

Questions are identified from bullets containing `"?"`, `"TBD"`, `"unknown"`,
or similar open markers. They are forwarded directly to the
`recommended_agency_questions` list in the packet and can be picked up by the
meeting agenda generator for the next session.

---

## Example: Slide → Exhibit Recommendation

**Input slide (figure-only):**

```json
{
  "slide_number": 4,
  "title": "Path Loss vs. Distance (Figure 3)",
  "bullets": [],
  "has_figure": true,
  "type": "figure"
}
```

**Output: `suggested_exhibits` entry**

```json
{
  "slide_id": "SLIDE-DECK-001-slide-4",
  "title": "Path Loss vs. Distance (Figure 3)",
  "suggested_section": "Appendix / Exhibits",
  "note": "[Exhibit Candidate] The slide titled 'Path Loss vs. Distance (Figure 3)' contains visual or tabular material suitable for inclusion as an exhibit in the 'Appendix / Exhibits' section. The exhibit should be accompanied by a descriptive caption and traceable source reference."
}
```

Figure slides with no bullet content are automatically classified as
`source_exhibit` and appear in `suggested_exhibits`. The working-paper author
should assign a figure number, write a caption, and include the traceable
source reference from `source_artifact_id`.

---

## Traceability Index

Every packet includes a `traceability_index` with one entry per slide,
summarising what was extracted:

```json
{
  "slide_id": "SLIDE-DECK-001-slide-3",
  "slide_number": 3,
  "source_artifact_id": "SLIDE-DECK-001",
  "section": "Preliminary Findings",
  "integration_role": "source_claim",
  "signal_score": 0.55,
  "claim_count": 4,
  "assumption_count": 0,
  "gap_count": 1
}
```

This index enables downstream modules (working-paper generator, assumptions
registry, knowledge graph) to quickly locate the slides that contributed the
most signal without processing the full packet.

---

## Signal Score Reference

| Range | Interpretation |
|---|---|
| 0.0 | No technical signal detected (title/overview/placeholder slide) |
| 0.1–0.2 | Minimal signal (system names or generic keywords only) |
| 0.3–0.5 | Moderate signal (parameters or model reference present) |
| 0.6–0.8 | High signal (multiple technical dimensions: params + model + interference) |
| 0.9–1.0 | Very high signal (parameters + model + interference + table/figure) |

Signal scores are used for prioritisation, not filtering. Every slide unit is
processed regardless of its score.

---

## Integration with Working-Paper Generator

The `slide_to_paper_candidates` list maps directly to working-paper sections.
Each candidate carries:
- `section` — the target section name
- `proposed_text` — report-ready prose
- `style_mode` — how the text should be formatted
- `caution_flags` — provisional or unsupported language warnings
- `confidence` — low / medium / high

The working-paper generator can consume this list by section name and incorporate
the proposed text as a draft, with the author applying judgment on caution flags.

---

## Known Limitations (Deterministic Baseline)

- Entity extraction uses keyword matching; compound multi-word entity names may
  be partially captured.
- Claim detection is pattern-based; nuanced implicit claims may be missed.
- Value extraction uses a single numeric regex; multi-value ranges (e.g.,
  "20–30 dBm") capture only the first number.
- Cross-artifact comparison uses word-overlap; semantic similarity is not
  computed.

These are the intended limitations of the deterministic baseline. Extension
points for model-assisted inference are noted in the design document.
