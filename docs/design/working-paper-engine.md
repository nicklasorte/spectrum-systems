# Working Paper Engine — Design Document

**Module:** `workflow_modules.working_paper_engine`
**Status:** Planned
**Version:** 1.0.0
**Classification:** DRAFT / PRE-DECISIONAL

---

## Purpose

The Working Paper Engine generates engineering-grade federal spectrum-study working papers from structured inputs. It is **not a summarizer**. It surfaces uncertainty, never fabricates quantitative results, and produces governed, traceable output artifacts suitable for agency review.

The engine addresses a core traceability gap in spectrum study workflows: the path from raw technical discussion (transcripts, source documents, study plans) to a defensible, structured working paper is error-prone and opaque. This module makes that transformation deterministic and auditable.

---

## Architecture

The engine is implemented as a **module-first capability** inside `spectrum_systems/modules/working_paper_engine/`. It does not require a separate repository.

### File Structure

```
spectrum_systems/modules/working_paper_engine/
├── __init__.py        — public API: run_pipeline, WorkingPaperInputs, WorkingPaperBundle
├── models.py          — all typed dataclasses and enums
├── observe.py         — OBSERVE stage
├── interpret.py       — INTERPRET stage
├── synthesize.py      — SYNTHESIZE stage
├── validate.py        — VALIDATE stage
├── artifacts.py       — bundle assembly, serialization, markdown rendering
└── service.py         — pipeline orchestrator + inputs_from_dict
```

Supporting files:

```
scripts/run_working_paper_engine.py
contracts/schemas/working_paper_bundle.schema.json
contracts/schemas/working_paper_gap_register.schema.json
contracts/schemas/working_paper_faq.schema.json
tests/test_working_paper_engine.py
docs/module-manifests/workflow_modules/working_paper_engine.json
```

---

## Pipeline Stages

### Stage 1: OBSERVE

**File:** `observe.py`

Extracts raw items from all input excerpts with lightweight semantic tagging. No interpretation beyond tagging.

- Tags: `assumption`, `constraint`, `open_issue`, `uncertainty`, `methodology`, `decision`, `fact`
- Preserves: `source_artifact_id`, `source_type`, `source_locator` on every item
- Sources: source documents, transcripts (with speaker), study plan excerpts
- Output: flat ordered list of `ObservedItem` instances

### Stage 2: INTERPRET

**File:** `interpret.py`

Maps observed items into structured concern buckets and generates gap candidates.

Concern buckets:
- `methodology` → Section 3
- `data` → Section 5
- `assumptions` → Section 4
- `constraints` → Sections 3, 4
- `agency_concerns` → Sections 2, 7
- `contradictions` → Sections 6, 7
- `missing_elements` → Sections 5, 6

Also:
- Detects numeric contradictions across sources (conflicting distances, power levels, frequencies)
- Flags missing required methodology elements (propagation model, link budget, interference, path loss)

### Stage 3: SYNTHESIZE

**File:** `synthesize.py`

Generates all seven report sections, FAQ items, gap register, results readiness status, and traceability requirements.

**Section layout:**

| Section | Title |
|---------|-------|
| 1 | Introduction |
| 2 | Background and Study Context |
| 3 | Methodology |
| 4 | Parameters and Assumptions |
| 5 | Data and Modeling Framework |
| 6 | Results Framework and Observations |
| 7 | Conclusions and Path Forward |

**Critical safety rule — Section 6:**

If quantitative results are not available, Section 6 **must** include the `RESULTS NOT YET AVAILABLE` marker and describe the results framework without implying any numeric outcomes. The engine checks for numeric content in the DATA bucket to determine results availability.

**Synthesis rules (hard-coded):**
- Frame the problem as system-level and interdependent
- Separate feasibility analysis from implementation decisions
- Use controlled vocabulary: `Feasible / Constrained / Infeasible`, `Candidate assignments`, `Modeled conditions`, `Normalized representations`
- Mark undefined items as `[need additional information]`
- Never make policy recommendations

### Stage 4: VALIDATE

**File:** `validate.py`

Runs eight structured validation checks:

| Check ID | Description | Category |
|----------|-------------|----------|
| VAL-001 | All required sections present | completeness |
| VAL-002 | Section 6 does not imply unavailable results | safety |
| VAL-003 | Section 7 does not overstate findings | safety |
| VAL-004 | FAQ section references are valid | consistency |
| VAL-005 | Gap register items reflected in report | consistency |
| VAL-006 | No forbidden output patterns | safety |
| VAL-007 | Traceability requirements are complete | traceability |
| VAL-008 | Results readiness consistency | results_readiness |

Each check emits a `ValidationFinding` with severity `pass`, `warning`, or `error`.

---

## Governed Outputs

### WorkingPaperBundle

The canonical output artifact. All fields are governed by `working_paper_bundle.schema.json` (JSON Schema Draft 2020-12).

Key fields:
- `artifact_id` — unique `WPE-*` identifier
- `report` — seven sections
- `faq` — extracted FAQ items
- `gap_register` — structured gap entries
- `validation_checklist` — all validation findings
- `results_readiness` — readiness status
- `traceability_requirements` — required artifacts, mappings, reproducibility inputs
- `validation` — categorized passes/warnings/errors
- `metadata` — engine version, timestamp, input summary

### WorkingPaperGapRegister

Standalone gap register (`working_paper_gap_register.schema.json`). Each entry includes:
- `gap_type`: Data / Methodology / Assumption / Validation / Coordination / Modeling / Other
- `impact`: High / Medium / Low
- `blocking`: bool — blocks results reporting if true

### WorkingPaperFAQ

Standalone FAQ artifact (`working_paper_faq.schema.json`). Each item references a report section and source observed items.

---

## Safety / Trustworthiness Rules

1. **No fabricated results.** The engine cannot produce quantitative claims unless they appear in the input DATA bucket with numeric content. Section 6 includes an explicit `RESULTS NOT YET AVAILABLE` marker when results are absent.

2. **No policy recommendations.** Synthesis templates are designed to describe engineering observations, not make decisions.

3. **Forbidden pattern detection.** The VALIDATE stage checks for patterns like `most links`, `many clusters`, invented percentages, and overstatement language (`proves`, `clearly shows`, `definitively`).

4. **Explicit gap marking.** All undefined or missing items are marked `[need additional information]` in the report.

5. **Deterministic output.** Given identical structured inputs, the engine produces identical outputs. No randomness, no LLM calls.

6. **Schema-governed output.** All output artifacts are validated against JSON Schema Draft 2020-12 contracts before writing.

---

## Known Limitations

- **No LLM integration.** The engine uses rule-based heuristics. Complex domain-specific reasoning (e.g., interference model selection) requires human review.
- **No semantic deduplication.** Near-duplicate observed items from multiple sources are not merged.
- **Contradiction detection is numeric-only.** Logical contradictions in prose are not detected automatically.
- **FAQ coverage is gap-driven.** FAQ items are generated only from missing-element and contradiction concerns; coverage depends on input quality.
- **Results detection is heuristic.** The engine uses numeric pattern matching to determine if results are available; edge cases may require manual review.

---

## Future Extensions

1. **Integration with `workflow_modules.slide_intelligence`** — ingest `SlideIntelligencePacket` as a fourth input type for richer claim extraction.

2. **Integration with `workflow_modules.meeting_intelligence`** — consume `MeetingMinutesRecord` directly rather than raw transcript excerpts.

3. **Integration with `shared.provenance`** — emit `ProvenanceRecord` objects for each synthesized claim.

4. **Integration with `control_plane.evaluation`** — run evaluation metrics against golden working papers for regression detection.

5. **LLM-assisted draft refinement** — after deterministic synthesis, allow an optional LLM pass to improve prose quality while maintaining gap markers and section structure.

6. **Multi-band support** — extend inputs to support multiple band descriptions and cross-band interference analysis sections.

---

## Why Module-First

This capability is implemented as a module inside `spectrum_systems/modules/` rather than a separate repository because:

1. It shares governed types (`ArtifactEnvelope`, `ProvenanceRecord`, etc.) with other modules in the same package.
2. It relies on the same test infrastructure, schema validation tooling, and CI pipeline.
3. The output artifacts (`WorkingPaperBundle`) are consumed by other modules in the same system (`control_plane.evaluation`, `workflow_modules.meeting_intelligence`).
4. Creating a separate repo would fragment the governance model and require a separate contract enforcement loop.

---

## Report-Ready Artifacts for Federal Spectrum Studies

The Working Paper Engine is designed to produce artifacts that are **structurally ready** for federal agency review:

- **DRAFT / PRE-DECISIONAL** classification is explicit in Section 1 and the Markdown report header.
- **FCC/NTIA-defensible structure** — the seven-section layout follows standard engineering working paper conventions used in spectrum sharing studies.
- **Explicit uncertainty** — all assumptions, constraints, and gaps are surfaced, not hidden.
- **Traceability** — every claim in the report can be traced back to a source observed item via the traceability requirements block.
- **No policy overreach** — the engine explicitly avoids policy language and cannot generate conclusions stronger than the data support.

---

## CLI Usage

```bash
# Basic usage
python scripts/run_working_paper_engine.py \
    --inputs path/to/inputs.json \
    --output path/to/bundle.json

# With Markdown report
python scripts/run_working_paper_engine.py \
    --inputs path/to/inputs.json \
    --output path/to/bundle.json \
    --pretty-report-out path/to/report.md

# Inline JSON inputs
python scripts/run_working_paper_engine.py \
    --inputs '{"title": "3.5 GHz Study", "band_description": "3550-3700 MHz"}' \
    --output /tmp/bundle.json
```

Exit codes: `0` = success, `1` = validation errors, `2` = runtime/input errors.
