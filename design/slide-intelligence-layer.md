# Slide Intelligence Layer — Design Document

## Overview

The Slide Intelligence Layer is a post-P roadmap capability that makes uploaded
slide decks first-class governed artifacts within the spectrum-systems pipeline.
This document explains the design rationale, integration model, and extension
points for future roadmap phases.

---

## Why Slides Are Structured Intelligence, Not Transcript Text

Transcripts are temporal: they record a sequence of spoken statements in the
order they were uttered. Slide decks are compositional: each slide is a
deliberately structured unit of information — a claim, a set of assumptions, a
methodology summary, or a visual exhibit.

Flattening slides into transcript-like text loses:
- the structural hierarchy of titles, bullets, and notes
- the signal that bullet ordering carries
- the distinction between a figure slide (best as an exhibit) and an
  assumption slide (best as a structured block)
- the ability to detect gaps (e.g., an interference claim without a supporting
  propagation model)

The Slide Intelligence Layer therefore normalises each slide into a **slide
unit** — a structured dict with explicit fields for title, bullets, notes,
raw text, figure/table presence, and provenance — before any downstream
processing occurs.

This preserves the full semantic structure of the slide and allows every
subsequent operation (scoring, role classification, claim extraction, etc.) to
operate on explicitly typed fields rather than on a flat string.

---

## The Four Integration Roles

Every slide unit is assigned one of four integration roles. These roles
determine how the slide's content flows into the working paper.

### `source_text`
Stable, factual, or descriptive content that can become paper prose directly.
Typical examples: background context, study scope statements, system descriptions.

### `source_claim`
An assertion that needs attribution and may require validation before it appears
in the working paper. Typical examples: interference findings, coexistence
conclusions, sufficiency claims.

Slides assigned `source_claim` are candidates for the Preliminary Findings or
Risk Assessment sections, and their claims are tracked in the extracted-claims
list with confidence levels.

### `source_question`
An unresolved issue, agency ask, or open prompt. Content containing "TBD",
"unknown", "unclear", "open issue", or an explicit question mark is classified
here.

Slides assigned `source_question` map to the Open Questions section and
generate entries in the recommended agency questions list.

### `source_exhibit`
Figure- or table-heavy material that is better treated as a numbered exhibit
than as inline prose. Figure slides without bullet content are assigned this
role automatically.

Slides assigned `source_exhibit` are routed to the Appendix / Exhibits section
and generate suggested exhibit records in the intelligence packet.

---

## Why Assumptions Extraction Matters in Spectrum Studies

Spectrum coexistence studies depend critically on their input assumptions. A
propagation model, an EIRP level, a deployment density, a guard-band width —
these inputs directly determine study conclusions. Different agencies may use
different assumptions, and reconciling those differences is a primary function
of the working group.

The Slide Intelligence Layer extracts assumptions from slide content and
produces structured `assumptions_registry_entry` records for each:
- `type` — what kind of assumption (EIRP, propagation_model, guard_band, etc.)
- `value` — the numeric value with unit, if stated
- `applies_to` — the system or scenario the assumption governs
- `source_slide_id` — traceable back to the slide that stated the assumption

This makes cross-agency assumption comparison tractable without manual
extraction, and seeds the consolidated assumptions registry that later
roadmap phases can populate.

---

## How Claims and Relationships Seed Later Knowledge Graph Capabilities

Each claim extracted from a slide is a declarative assertion about spectrum
behaviour: "5G NR may interfere with federal radar within 5 km." Each such
claim:
- has a `claim_id` for tracking
- carries a `confidence` level based on the language used
- is linked to `related_entities` (systems, bands, agencies)
- is traceable to its source slide

The entity-and-relationship extraction function goes further, pulling directed
edges such as:
- `5G NR` → `interferes_with` → `radar`
- `guard band` → `mitigated_by` → `power control`
- `slide_id` → `assumes` → `ITM propagation model`

These edges are the seed records for the Spectrum Intelligence Map — the
knowledge graph that will eventually track positions, relationships, and changes
across meetings and studies. The current implementation uses deterministic
pattern matching only; the schema is designed so that future graph ingestion
engines can consume these records directly.

---

## What "Gap Detection" / Negative Space Means

Gap detection is the process of identifying what is missing from a slide's
technical content — the negative space.

The Slide Intelligence Layer applies five gap-detection rules:

1. **Interference claim without propagation model** — An interference assertion
   requires a stated propagation model to be defensible. If none is present,
   a `high`-severity gap is raised.

2. **Technical conclusion without supporting assumptions** — A finding or result
   without stated input assumptions cannot be reproduced or challenged.

3. **Mitigation claim without criteria** — A claim that interference is
   "manageable with guard bands" must state the guard-band size, threshold, or
   conditions. Without those, the claim is unverifiable.

4. **Result without method** — Calculated or simulated results must cite the
   analysis method used.

5. **Recommendation without stated basis** — A recommendation to adopt a policy
   or technical approach must explain why.

Each gap produces a `gap_id`, a `description`, a `severity` (high / medium /
low), and a list of `related_claim_ids`. Gaps flow into the packet's
`analysis_gaps` list and influence the `validation_status` field.

The goal is to surface weak slides before working-paper authoring begins, so
that the study team can request additional information from the presenting
agency.

---

## The Observe → Interpret → Recommend Golden Path

The Slide Intelligence Layer is explicitly designed to advance the golden path:

**Observe** — slide_deck artifacts are ingested alongside transcripts and
meeting minutes. The `extract_slide_units` function normalises raw slide data
into structured units.

**Interpret** — the pipeline of signal scoring, role classification, claim
extraction, assumption extraction, entity/relationship extraction, and gap
detection transforms raw slide content into machine-readable intelligence.

**Recommend** — working-paper section mapping, paper-ready rewriting, and
cross-artifact comparison produce actionable recommendations: which slides
become which sections, what questions to ask agencies, which slides should be
exhibits, and what gaps need resolution.

The `slide_intelligence_packet` is the artifact that carries all three layers
of output in a single governed structure.

---

## Why This Phase Belongs After P in the Roadmap

Prompt P established the working-paper generator and its input contract. At
that point, the pipeline could consume transcripts and meeting minutes but had
no mechanism to ingest the structured technical content that agencies bring to
working-group sessions in slide form.

The Slide Intelligence Layer fills that gap by:
- extending the governed input artifact set to include `slide_deck`
- producing a `slide_intelligence_packet` that the working-paper generator can
  consume as a structured input alongside the existing transcript/minutes flow
- seeding the assumptions registry and knowledge graph with content that would
  otherwise be locked in presentation files

This phase is scoped narrowly to the deterministic foundation. No LLM
inference, no network calls, no embedding models. The extension points for
later phases are explicit in the architecture.

---

## Extension Points for Later Roadmap Phases

| Extension Point | Description |
|---|---|
| `knowledge_graph_edges` field | Ready for ingestion by a graph database engine without schema changes |
| `assumptions_registry_entries` field | Ready for consolidation across meetings by an assumptions-registry module |
| `recommended_agency_questions` field | Ready for inclusion in meeting agenda generation |
| `traceability_index` | Enables position-tracking over time as decks from successive meetings are compared |
| `validation_status` field | Can be promoted to a lifecycle gate in the pipeline once review workflows exist |
| `compare_with_transcript_and_paper` | Keyword overlap is the baseline; embedding-based similarity can be added as a provider behind the same interface |
| `rewrite_for_working_paper` | Style modes map cleanly to template-based or generative prose expansion in later phases |

---

## Contract and Governance Alignment

This design follows the Module-First Architecture Rule:
- All logic lives in `spectrum_systems/modules/slide_intelligence.py`
- New artifact types (`slide_deck`, `slide_intelligence_packet`) are registered
  in `contracts/standards-manifest.json` with `artifact_class: work`
- Schemas are added to `contracts/schemas/`
- The module manifest at `docs/module-manifests/workflow_modules/slide_intelligence.json`
  declares inputs, outputs, dependencies, and forbidden responsibilities
- No shared-truth structures (artifact models, ID schemes, lineage, provenance)
  are redefined in this module; all are imported from `shared.*`

No contract drift is introduced. The new artifact types follow the same
envelope and classification conventions as existing types.
