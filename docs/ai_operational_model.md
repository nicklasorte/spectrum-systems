# AI Operational Model

This document defines the operating model for AI-assisted systems in the Spectrum Systems ecosystem. It describes the core loop, maps loop stages to ecosystem components, and establishes the boundary between AI-generated outputs and human decision authority.

---

## The Core Loop: Observe → Interpret → Recommend → Act → Learn

Every governed AI workflow in this ecosystem operates on a five-stage loop:

| Stage | Description |
|---|---|
| **Observe** | Ingest governed inputs: transcripts, documents, simulation outputs, prior artifacts, context signals |
| **Interpret** | Extract structured facts, classifications, assessments, and metadata from ingested inputs |
| **Recommend** | Generate bounded, reviewable outputs: action suggestions, follow-ups, risk flags, advisories |
| **Act** | Execute or apply a recommendation — only after human review and acceptance; not autonomous |
| **Learn** | Feed evaluation results, override signals, and outcome evidence back to improve prompts, schemas, and fixtures |

**Current MVP scope**: The meeting-minutes workflow implements Observe → Interpret → Recommend end to end. Act and Learn are planned but not yet operational. This document clearly distinguishes current state from target state throughout.

---

## Loop Stage Details

### Observe

Observation is not passive. It requires:
- Schema-validated input artifacts (transcripts, templates, context bundles)
- Provenance metadata attached at ingestion (source, timestamp, version, run context)
- Rejection of malformed or non-conformant inputs before processing begins

Observation quality determines the ceiling for everything downstream. Garbage-in is not correctable by better interpretation.

**Ecosystem role**: data lake (storage and lineage), pipeline engine (ingestion orchestration), governance contracts (input schema enforcement)

### Interpret

Interpretation is the core AI function: transforming raw or semi-structured inputs into governed structured artifacts. The engine applies prompts, rules, and schema contracts to extract:
- Facts (dates, participants, topics, quantities)
- Actions (owner, description, due date, priority)
- Decisions (what was decided, by whom, rationale if stated)
- Risks and assumptions (surfaced during the meeting or document review)
- Metadata signals (meeting type, program area, urgency indicators)

Interpretation must be:
- **Deterministic by fixture**: the same input + prompt version produces structurally equivalent outputs across runs
- **Schema-conformant**: outputs are validated against the governing contract before the run is considered complete
- **Auditable**: the prompt version, model configuration, and input provenance are recorded in the evidence bundle

**Ecosystem role**: operational engines (e.g., meeting-minutes-engine, working-paper-review-engine), prompt catalog, schema registry

### Recommend

Recommendations are bounded, reviewable outputs — not autonomous decisions. The system suggests; humans decide.

A recommendation output includes:
- Proposed next steps or follow-ups
- Suggested ownership assignments
- Flagged risks, gaps, or decision points requiring human attention
- Operational signals for downstream consumers (pipeline, advisor, register)

Recommendations are never treated as authoritative without human review and acceptance. The artifact is delivered to a human review checkpoint before it enters the operational record.

**Ecosystem role**: engines (recommendation generation), program advisor (advisory synthesis), pipeline (routing to review)

### Act (Target State — Not Yet Operational)

In target state, accepted recommendations trigger governed actions: creating tracked work items, updating registers, routing artifacts to next workflow stages. This stage requires human acceptance as the trigger. Fully autonomous action is not a design goal in the near term.

**Planned ecosystem role**: pipeline engine (action routing), governance automation (work item generation)

### Learn (Target State — Not Yet Operational)

In target state, evaluation outcomes, human overrides, and acceptance/rejection signals are fed back to improve prompt versions, update fixtures, and inform maturity advancement. This closes the operational feedback loop.

**Planned ecosystem role**: eval harness, maturity tracker, prompt governance

---

## Ecosystem Component Mapping

| Loop Stage | Primary Component(s) | Governance Artifact |
|---|---|---|
| Observe | Data lake, pipeline engine | Input contracts, provenance schema |
| Interpret | Operational engines, prompt catalog | Artifact contracts, eval harness |
| Recommend | Operational engines, program advisor | Output contracts, review checkpoint |
| Act | Pipeline engine, governance automation | Work item schema, acceptance log |
| Learn | Eval harness, maturity tracker | Evaluation results, override log |

Component names are role-based, not tied to specific repository names. The registry in `ecosystem/ecosystem-registry.json` maps roles to concrete repos.

---

## Meeting Minutes MVP

The meeting-minutes workflow (SYS-006) is the current end-to-end implementation of the loop.

### Observe
- **Input**: Raw meeting transcript or structured transcript template; participant roster; meeting context document
- **Validation**: Inputs are checked against schema before processing
- **Provenance**: Source file, timestamp, and context metadata are attached to the ingestion record

### Interpret
- **Engine**: meeting-minutes-engine
- **Extracts**: Meeting facts, action items with ownership and due dates, decisions with stated rationale, risks, assumptions, and structured metadata
- **Contract**: Outputs conform to the `meeting_minutes` artifact contract in `contracts/schemas/`
- **Evidence**: Run produces `run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, and `provenance.json` with a shared `run_id`

### Recommend
- **Outputs**: Suggested follow-up items, ownership assignments, next-step priorities, and operational signals
- **Review gate**: The structured minutes artifact is delivered for human review before it enters the authoritative operational record
- **Format**: Schema-conformant artifact, not free-form prose; downstream consumers (pipeline, advisor) can parse it reliably

### Current Limits
- Act and Learn are not implemented. Human review triggers any downstream action manually.
- Feedback loops to improve extraction quality are informal; no structured override-log or prompt improvement pipeline exists yet.
- The MVP establishes the governed loop shape; subsequent development extends it.

---

## Boundaries of AI Authority

These boundaries are firm and apply across all workflows, not just the MVP:

| AI may | AI may not |
|---|---|
| Extract and structure facts from governed inputs | Decide which facts are authoritative |
| Generate suggested actions and ownership assignments | Assign ownership without human acceptance |
| Flag risks and surface patterns | Declare something a risk without review |
| Produce schema-conformant output artifacts | Publish artifacts to the operational record without human sign-off |
| Support test-case and fixture generation | Replace evaluation harnesses with self-assessment |

Violating these boundaries is a governance incident. See `docs/incident_response.md`.
