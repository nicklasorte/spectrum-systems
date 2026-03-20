# Working Paper Engine

**Module:** `spectrum_systems/modules/working_paper_engine/`  
**Status:** Active  
**Version:** 1.0.0  
**Classification:** DRAFT / PRE-DECISIONAL

---

## Purpose

The `working_paper_engine` module generates engineering-grade, federal spectrum-study working papers with full traceability, explicit uncertainty, and governed JSON output bundles.

It is **not a summarizer**. Its purpose is to:

- Ingest source documents, meeting transcripts, and study plan / tasking guidance
- Extract structured evidence without interpretation first
- Map evidence into analytical buckets and identify gaps
- Synthesize a structured 7-section working paper in neutral engineering tone
- Validate the output for internal consistency, safety, and traceability compliance

Every output must support human verification. The engine **never fabricates quantitative results** and **always surfaces uncertainty** through explicit markers and a gap register.

---

## Module-First Architecture

This module follows the `spectrum-systems` module-first principle: new capability goes into a module in `spectrum-systems`, not a new repository. The `working_paper_engine` is self-contained, independently testable, and schema-led.

It is placed at:

```
spectrum_systems/modules/working_paper_engine/
```

This placement allows it to:

1. Share the existing `contracts/schemas/` governance layer
2. Integrate with the `artifact_lineage` and `provenance` shared modules when needed
3. Be composed into the `orchestration/pipeline` layer without a cross-repo dependency
4. Be validated by the existing test infrastructure (`pytest` + `jsonschema`)

---

## Architecture

The engine implements a 4-stage deterministic pipeline:

```
[Inputs]
  source_documents + transcripts + study_plans
        │
        ▼
  ┌─────────────┐
  │   OBSERVE   │  Stage 1: Extract raw facts, questions, constraints,
  │             │  assumptions, open issues. Lightweight tagging only.
  │  observe.py │  Preserves source provenance.
  └──────┬──────┘
         │ ObserveResult
         ▼
  ┌─────────────┐
  │  INTERPRET  │  Stage 2: Map items into buckets (methodology, data,
  │             │  assumptions, constraints, agency_concerns,
  │ interpret.py│  contradictions, missing_elements). Flag gap candidates.
  └──────┬──────┘
         │ InterpretResult + GapItems
         ▼
  ┌─────────────┐
  │ SYNTHESIZE  │  Stage 3: Generate Sections 1–7 using template-driven
  │             │  deterministic assembly. Extract FAQ items. Integrate
  │synthesize.py│  gap markers. Section 6 switches to results-framework
  └──────┬──────┘  mode if no quantitative results are available.
         │ SynthesizeResult
         ▼
  ┌─────────────┐
  │  VALIDATE   │  Stage 4: Rule-based consistency and safety checks.
  │             │  Checks for fabricated claims, missing sections,
  │ validate.py │  overstatement, FAQ/gap alignment, readiness consistency.
  └──────┬──────┘
         │ ValidateResult
         ▼
  ┌─────────────┐
  │  ASSEMBLE   │  artifacts.py: Build the governed JSON output bundle.
  └─────────────┘  JSON Schema validation against working_paper_bundle.schema.json.
```

---

## Pipeline Stages

### Stage 1: OBSERVE (`observe.py`)

**Purpose:** Extract raw facts, questions, constraints, assumptions, and open issues from all inputs.

**Rules:**
- No interpretation beyond lightweight tagging
- Each item preserves `source_artifact_id`, `source_type`, and `source_locator`
- Tags are assigned using regex-based pattern matching: `question`, `assumption`, `constraint`, `open_issue`, `fact`
- Confidence is set to 1.0 for documents, 1.0 for study plans, 0.9 for transcripts

**Output:** `ObserveResult` containing `List[ObservedItem]`

### Stage 2: INTERPRET (`interpret.py`)

**Purpose:** Map observed items into structural analytical buckets.

**Buckets:**
| Bucket | Section Refs | Description |
|---|---|---|
| `methodology` | 3, 4 | Analytical methods, models, procedures |
| `data` | 5 | Data sources, measurements, records |
| `assumptions` | 4 | Working assumptions, modeled-as conditions |
| `constraints` | 4, 5 | Protection criteria, regulatory limits |
| `agency_concerns` | 2, 6 | Federal agency questions and concerns |
| `contradictions` | 6, 7 | Conflicting claims or inconsistencies |
| `missing_elements` | 5, 6 | Missing data, unknown parameters |

**Gap candidate promotion:** Items in `missing_elements`, `data`, and `contradictions` buckets, plus all `question`- and `open_issue`-type items, are flagged as gap candidates.

**Output:** `InterpretResult` + `List[GapItem]`

### Stage 3: SYNTHESIZE (`synthesize.py`)

**Purpose:** Generate Sections 1–7 using template-driven deterministic assembly.

**Section mapping:**
| Section | Title | Sources |
|---|---|---|
| 1 | Introduction | All inputs (meta-level) |
| 2 | Background and Study Context | Agency concerns, context items |
| 3 | Methodology | Methodology bucket |
| 4 | Parameters and Assumptions | Assumptions + constraints |
| 5 | Data and Modeling Framework | Data + missing elements |
| 6 | Results Framework and Observations | Results (or framework if none) |
| 7 | Conclusions and Path Forward | Contradictions + blocking gaps |

**Safety rule for Section 6:** If `quantitative_results_available=False`, Section 6 inserts a prominent `NOTICE` and switches to results-framework / preliminary-observations mode. It does **not** imply completed results.

**FAQ extraction:** Items in `agency_concerns` and `missing_elements` buckets, plus any item containing question language, are promoted to FAQ items.

**Vocabulary rules applied consistently:**
- `"Feasible / Constrained / Infeasible"` for feasibility assessments
- `"Candidate assignments"` for frequency proposals  
- `"Modeled conditions"` for simulation scenarios
- `"Normalized representations"` for derived input data
- `"[need additional information]"` for undefined or missing items

**Output:** `SynthesizeResult`

### Stage 4: VALIDATE (`validate.py`)

**Purpose:** Rule-based consistency and safety checking.

**Checks implemented:**
| Check | Category | Severity |
|---|---|---|
| All required sections (1–7) present | completeness | error |
| Section 6 does not imply results if none | safety | error |
| Section 7 does not overstate findings | safety | error |
| No unsupported quantitative claims | safety | error |
| FAQ items reference valid sections | traceability | warning |
| Gap items reference valid sections | traceability | warning |
| Blocking gaps visible in Section 7 | completeness | warning |
| Results-readiness flag consistent | consistency | error |
| FAQ extraction completeness | completeness | warning |

**Output:** `ValidateResult` with `passes`, `warnings`, `errors`

---

## Governed Outputs

### Output Bundle (`working_paper_bundle.schema.json`)

The primary output is a governed JSON bundle validated against:
`contracts/schemas/working_paper_bundle.schema.json`

Schema properties:
- Draft 2020-12
- `additionalProperties: false` at root and all nested objects
- Enums for `gap_type`, `impact`, `provenance_mode`, `category`
- All required fields explicitly declared

Supporting schemas:
- `contracts/schemas/working_paper_gap_register.schema.json`
- `contracts/schemas/working_paper_faq.schema.json`

---

## Safety / Trustworthiness Rules

1. **No fabricated results.** Section 6 never claims results exist if `quantitative_results_available=False`. Validation enforces this.

2. **No unconstrained generation.** All prose is assembled from templates and extracted evidence items. No free-form LLM generation is used.

3. **Explicit uncertainty.** All missing information is marked `[need additional information]`. Gaps are logged in the gap register with IDs.

4. **No policy recommendations.** The engine is scoped to feasibility analysis framing. Policy-language patterns are not generated.

5. **Forbidden quantitative patterns.** The validator rejects percentages, "most links", "many clusters", "nearly all", "majority of", "proves that", etc. unless verified.

6. **Provenance on every item.** All observed, interpreted, and gap items carry `source_artifact_id`, `source_type`, and `source_locator`.

7. **Schema governance.** Every output bundle is validated against a governed JSON Schema before the CLI exits.

8. **Explicit validation exit codes.** The CLI exits nonzero on schema errors (code 2) or validation errors (code 3).

---

## Known Limitations

1. **Template-driven synthesis quality.** The engine uses deterministic template assembly, not LLM prose generation. Generated sections are functional and structured but may require editorial polish before external release.

2. **Tag-based evidence extraction.** The OBSERVE and INTERPRET stages use regex pattern matching. Complex or ambiguous phrasing may be miscategorized. Review the gap register and FAQ before finalizing.

3. **No cross-section contradiction detection between synthesized content.** The VALIDATE stage checks for overstatement and results implication, but does not perform deep semantic comparison between sections.

4. **Provenance mode is `best_effort` by default.** Full strict provenance requires all inputs to include `artifact_id` and `source_locator` fields. These are optional in the input model.

5. **Gap resolution suggestions.** All gap items are initially given `[need additional information]` as the suggested resolution. Human review should refine these before the paper is shared.

---

## Future Extensions

1. **Integration with `runtime/working_paper_synthesis.py`:** The existing synthesis decision artifact could be consumed as an additional input to pre-populate methodology and evidence sections.

2. **Integration with `meeting_minutes_pipeline.py`:** Meeting minute records could be automatically converted to `TranscriptExcerpt` inputs.

3. **Integration with `slide_intelligence.py`:** Slide intelligence packets could be converted to `SourceDocumentExcerpt` inputs.

4. **LLM-augmented synthesis:** A future variant could use the template skeleton as a structured prompt and allow LLM polish, while the validation stage enforces the same safety rules.

5. **Gap resolution tracking:** The gap register could integrate with the `gap_detection.py` module and feed into the `study_state.py` study readiness tracker.

6. **Provenance strict mode:** A future strict-provenance mode would reject any input without an `artifact_id` and validate all source locators against a known artifact registry.

---

## Example CLI Usage

```bash
# Run the engine with a JSON inputs file
python scripts/run_working_paper_engine.py \
    --inputs path/to/inputs.json \
    --output path/to/bundle.json \
    --pretty-report-out path/to/report.md

# Use inline JSON
python scripts/run_working_paper_engine.py \
    --inputs '{"title_hint":"My Study","source_documents":[{"content":"..."}],"transcripts":[],"study_plans":[]}' \
    --output bundle.json
```

**Input JSON format:**

```json
{
  "title_hint": "Radar-5G Coexistence Study Working Paper",
  "study_id": "NTIA-STUDY-2026-001",
  "quantitative_results_available": false,
  "source_documents": [
    {
      "content": "The study analyzes...",
      "artifact_id": "DOC-001",
      "source_locator": "p.1",
      "title": "Study Technical Report"
    }
  ],
  "transcripts": [
    {
      "content": "Alice: What are the protection criteria?",
      "artifact_id": "TRANS-001",
      "speaker": "Alice",
      "meeting_title": "Technical Working Group Meeting 1"
    }
  ],
  "study_plans": [
    {
      "content": "The study shall evaluate feasibility...",
      "artifact_id": "PLAN-001",
      "study_title": "NTIA Tasking Document"
    }
  ]
}
```

**Exit codes:**
- `0` — Success
- `1` — Input or runtime error
- `2` — Output bundle failed JSON Schema validation
- `3` — Validation errors in the output bundle

---

## Integration with the Spectrum-Systems Module Architecture

This module is placed in `spectrum_systems/modules/working_paper_engine/` to align with the `workflow_modules/working_paper_review` slot in the target module tree defined in `docs/architecture/module-pivot-roadmap.md`.

It produces governed artifacts compatible with the artifact envelope standard (`contracts/schemas/artifact_envelope.schema.json`) and is designed to feed into:

- Human review workflows (via `docs/design-review-standard.md`)
- Agency coordination processes
- Study readiness assessments (`study_readiness_assessment.schema.json`)
- The SLO control chain when results become available
