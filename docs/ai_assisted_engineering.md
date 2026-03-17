# AI-Assisted Engineering Playbook

This document defines where AI should assist in this ecosystem, where it should not have final authority, and the operational rules that govern AI-generated artifacts at every stage.

The meeting-minutes workflow (SYS-006) is the baseline operational example throughout.

---

## Where AI Should Help

### 1. Extraction
AI transforms semi-structured or unstructured inputs (transcripts, documents, simulation outputs) into governed structured artifacts. This is the core use case in the current ecosystem.

**Rules**:
- Extraction prompts are versioned in `prompts/` and governed under `docs/prompt-standard.md`
- Outputs are validated against the artifact contract before the run is considered complete
- Extraction coverage (field population rate) is measured per run and tracked as an SLI

**Meeting minutes example**: The engine extracts meeting facts, action items, decisions, risks, and metadata from a transcript. The human reviewer verifies accuracy — they do not re-extract from scratch.

### 2. Transformation
AI reformats or restructures content to match a governed schema or delivery format. This is distinct from extraction — transformation takes already-identified content and converts its representation.

**Rules**:
- Transformation outputs must be schema-conformant; validation is mandatory
- The transformation logic (prompt or rule) is versioned and testable against known-good fixtures
- Transformation may not alter the semantic meaning of source material; only structure and format

### 3. Validation Assistance
AI can flag likely schema violations, missing required fields, or structural anomalies before formal validation runs. This is a triage aid, not a replacement for schema validation.

**Rules**:
- AI-flagged issues are advisory; they do not replace `scripts/validate_evaluation_contract.py` or equivalent CI checks
- False negatives (failing to flag a real violation) are tracked as quality events

### 4. Recommendation Generation
AI generates bounded, reviewable suggestions: follow-up items, ownership assignments, risk flags, priority signals, and advisories.

**Rules**:
- Recommendations are delivered as schema-conformant artifacts, not free-form prose
- The recommendation artifact is never treated as authoritative without human review and acceptance
- Recommendation quality is measured and tracked; material misses are logged

**Meeting minutes example**: The engine suggests follow-up owners and next-step priorities. The human reviewer accepts, modifies, or rejects each suggestion before the minutes artifact enters the operational record.

### 5. Test-Case and Fixture Generation
AI can propose new test fixtures and edge-case inputs to extend the evaluation harness. This helps expand coverage without requiring engineers to manually author every fixture.

**Rules**:
- AI-generated fixtures are reviewed before addition to the canonical fixture set
- Fixtures must be deterministic (same input → same expected output) and labeled with their coverage purpose
- AI must not generate fixtures that assert incorrect expected outputs

### 6. Documentation Drafting
AI can draft initial versions of governance documents, interface specs, schema annotations, and operational guides from structured inputs (existing schemas, contracts, workflow descriptions).

**Rules**:
- AI-drafted documentation is a starting point, not a final artifact
- A human author is responsible for reviewing, correcting, and owning the final document
- AI-drafted documents are clearly marked as drafts until accepted by a human reviewer
- Documentation that enters the repo as authoritative must have human sign-off

---

## Where AI Should Not Have Final Authority

| Domain | Reason |
|---|---|
| **Accepting artifacts into the operational record** | An artifact in the operational record is authoritative. Only a human can accept that authority. |
| **Assigning ownership of actions or decisions** | Ownership carries accountability. AI can suggest; a human must confirm. |
| **Declaring governance compliance** | AI can check schema validity. Whether an artifact meets governance intent requires human judgment. |
| **Promoting prompt or schema versions** | Promotion requires evidence review. Evidence interpretation is a human responsibility. |
| **Escalating or resolving incidents** | Incident response requires judgment about impact, root cause, and remediation adequacy. |
| **Determining maturity advancement** | Maturity claims require evidence review by a human, following the rubric in `docs/review-maturity-rubric.md`. |
| **Publishing external-facing content** | Any artifact that leaves the internal ecosystem requires explicit human approval. |

These are not arbitrary restrictions. They reflect the principle that AI augments human judgment; it does not replace accountability.

---

## Human Review Rules

Every AI-generated artifact has a mandatory human review checkpoint before it is treated as authoritative. Review requirements by artifact type:

| Artifact Type | Review Requirement |
|---|---|
| Extraction output (e.g., meeting minutes) | Human reviewer checks coverage and accuracy before artifact enters operational record |
| Recommendation output | Human accepts, modifies, or rejects each recommendation before action is taken |
| AI-drafted documentation | Human author reads, corrects, and signs off before document is committed as authoritative |
| AI-generated fixture | Engineering reviewer verifies correctness before fixture is added to canonical set |
| Governance check result | Human interprets flagged issues before any remediation action is taken |

Review is not rubber-stamping. A reviewer who finds material errors must log them, even if the overall artifact passes schema validation.

---

## Explainability Requirements

AI-generated artifacts must be explainable in terms of what they contain and why.

**For extraction outputs**: The source section or passage that supports each extracted field must be identifiable (by reference or direct quotation) if a reviewer asks. The engine does not need to produce this automatically for every field, but the answer must be reconstructable from the input.

**For recommendations**: The basis for a recommended action or ownership assignment should be traceable to a statement in the source material. Recommendations without any traceable basis are a quality failure.

**For governance flags**: An AI validation flag must identify what rule or schema constraint was violated and where.

Explainability is a design requirement for prompts, not a post-hoc feature. Prompts should be written to produce explainable outputs, not opaque judgments.

---

## Deterministic Wrapping

AI model outputs are inherently non-deterministic across runs. Governance requires determinism for reproducibility. The resolution is to wrap AI model calls in deterministic governance:

- **Fixed prompt versions**: The exact prompt text and version are recorded and locked per run
- **Fixed model configuration**: Model, temperature, and relevant parameters are recorded in the run manifest
- **Fixture-based regression**: The same input + same prompt version produces structurally equivalent outputs, verified against fixtures
- **Schema validation as a hard gate**: Structural non-conformance is never silently accepted; it surfaces as a run failure

The artifact is the governed output. The model call is a mechanism. Governance wraps the mechanism so the artifact is reproducible and auditable even if the model call is not deterministic at the token level.

---

## Artifact Preservation

Every AI-generated artifact must be preserved with its full provenance context:

- **run_id**: Unique identifier for the run that produced the artifact
- **prompt version**: The exact prompt version used
- **input provenance**: Source file, timestamp, version of input material
- **model configuration**: Model name, relevant parameters
- **schema version**: The contract version the output was validated against

Artifacts without this metadata are not governed artifacts. They may not be used as inputs to downstream systems.

See `docs/data-provenance-standard.md` for the full provenance metadata standard.

---

## Meeting Minutes Workflow: Operational Baseline

The meeting-minutes workflow (SYS-006) demonstrates these rules in practice:

| Rule | How It Applies |
|---|---|
| Extraction in bounded scope | Engine extracts only what the `meeting_minutes` contract defines; it does not invent fields |
| Prompt versioning | The extraction prompt is versioned; changes require fixture re-runs before promotion |
| Schema validation gate | Output is validated against the contract before the run is complete |
| Human review checkpoint | Structured minutes artifact is delivered to a human reviewer before entering the operational record |
| Recommendation bounds | Suggested owners and follow-ups are advisory; the reviewer accepts or modifies them |
| Evidence bundle | Every run emits `run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, `provenance.json` |

The meeting-minutes workflow is the first end-to-end example of these rules working together. Subsequent workflows should inherit this pattern before adding new capabilities.
