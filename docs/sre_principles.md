# Spectrum Systems Reliability Principles

Reliability in Spectrum Systems is not uptime-centric. This is not a web service. Reliability here means: governed workflows produce correct, complete, traceable outputs consistently and reproducibly. Failures surface explicitly, are detected early, and are corrected before they propagate.

---

## What Reliability Means Here

| Dimension | Definition |
|---|---|
| **Reproducibility** | Given the same inputs and prompt/schema versions, a run produces structurally equivalent outputs. |
| **Correctness** | Extracted facts, decisions, actions, and risks match the ground-truth source material within defined tolerance. |
| **Completeness** | Required output fields are populated; no mandatory sections are silently absent. |
| **Availability** | Governed workflows can be invoked by authorized operators when needed, without undocumented dependencies blocking execution. |
| **Auditability** | Every run emits a correlated evidence bundle (`run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, `provenance.json`) traceable back to inputs and prompt versions. |
| **Governance Compliance** | Outputs conform to the canonical artifact contract and pass schema validation before downstream consumption. |

---

## Adapted SLI / SLO Language

Standard SRE terminology maps onto this ecosystem as follows.

### Service Level Indicators (SLIs)

SLIs are observable, measurable signals for a governed workflow.

| SLI | Measurement |
|---|---|
| Extraction field coverage | Fraction of required output fields populated in a completed artifact |
| Schema validation pass rate | Fraction of completed runs where the output artifact passes JSON Schema validation |
| Contract conformance rate | Fraction of runs where the artifact envelope and payload conform to the governing contract |
| Reproducibility delta | Structural diff score between two runs on the same fixture input |
| Evidence bundle completeness | Fraction of runs that emit all four required evidence files with a consistent `run_id` |

### Service Level Objectives (SLOs)

SLOs are internal targets, not external commitments. They are set per workflow and reviewed when error budgets are exhausted.

| SLO | Target (example, set per release) |
|---|---|
| Required field coverage | ≥ 95% of fields populated per run |
| Schema validation pass rate | ≥ 98% of completed runs |
| Evidence bundle completeness | 100% — this is a hard gate, not a target |
| Reproducibility delta on fixture set | ≤ defined structural tolerance per eval cycle |

SLOs are aspirational targets that guide investment in hardening. They do not automatically block deployment, but exhausting an error budget does — see `docs/error_budget_policy.md`.

### Error Budgets

An error budget is the allowed failure margin before hardening work takes priority over feature expansion. Budgets apply per workflow and per SLI class. Full error budget policy is in `docs/error_budget_policy.md`.

---

## MVP Application: Meeting Minutes Workflow

The meeting-minutes workflow (SYS-006) is the first end-to-end implementation of the Observe → Interpret → Recommend loop and is the primary proving ground for these reliability principles.

### Inputs (Observe)

- Raw meeting transcript (text or structured template)
- Meeting context and participant roster
- Agenda, if available

Reliability expectation: inputs must be traceable (provenance metadata attached) and schema-validated before the engine processes them.

### Extraction (Interpret)

The engine extracts:
- Meeting facts (date, attendees, topics covered)
- Action items (owner, due date, description)
- Decisions and rationale
- Risks and assumptions raised
- Structured metadata (meeting type, program area, priority signals)

SLI target: required extraction fields are populated at the defined coverage rate. Missing required fields (e.g., no action items extracted from a meeting that clearly discussed them) constitute extraction failures logged in `evaluation_results.json`.

### Output Completeness (Recommend)

The engine produces:
- A structured minutes artifact conforming to the `meeting_minutes` contract
- Suggested follow-ups, ownership assignments, and operational signals

Reliability expectation: the artifact passes schema validation; all mandatory sections are present; the evidence bundle is emitted with a consistent `run_id`.

### Deterministic Packaging

A run that produces an identical transcript input under the same prompt version should produce structurally equivalent outputs across executions. Fixture-based regression testing verifies this. Divergence beyond the defined structural tolerance triggers an evaluation review before the changed prompt version is promoted.

---

## Failure Handling

Silent failures are not acceptable. If a required field cannot be extracted, the output artifact must record the gap explicitly (e.g., a null or an `extraction_incomplete` flag) rather than omitting the field. Downstream systems (pipeline, advisor) must treat incomplete artifacts as requiring human review before use.

See `docs/error_budget_policy.md` for budget thresholds and response actions.  
See `docs/incident_response.md` for triage and postmortem expectations.
