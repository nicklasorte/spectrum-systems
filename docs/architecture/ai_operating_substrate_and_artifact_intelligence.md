# AI Operating Substrate and Artifact Intelligence

## Purpose
Define the required architecture for a governed AI operating substrate and the minimum artifact intelligence layer that turns execution traces into reusable operational judgment.

This document is an architectural authority for planning and sequencing. It defines what must exist before broader AI expansion is considered compliant.

## Scope
This authority covers:
- AI operating substrate boundaries
- expanded artifact taxonomy for model-mediated work
- artifact intelligence functions (measurement, comparison, reuse, governance, learning)
- build order constraints (`must-add` vs `should-have`)
- minimum viable artifact-intelligence slice

This document does not authorize unconstrained autonomy expansion.

## Design Thesis
A durable AI system is not model-first; it is substrate-first.

The substrate must make model activity:
- contract-bound
- observable
- replayable
- policy-governed
- measurable over time
- improvable through artifact reuse rather than ad hoc prompting

Artifact intelligence is the layer that converts emitted artifacts into governed, reusable judgment and planning leverage.

## Core Principles
1. **Artifact-first execution** — every consequential AI action emits governed artifacts.
2. **Adapter-only model access** — no direct model invocation outside approved contracts.
3. **Decision provenance completeness** — routing, context admission, and override decisions are all first-class artifacts.
4. **Evaluation before trust escalation** — capability expands only when eval coverage and control hooks are present.
5. **Judgment reuse over prompt drift** — decisions and outcomes are mined into reusable guidance artifacts.
6. **Fail-closed by default** — missing governance artifacts block progression.
7. **Learning loop closure** — observed failures produce eval and policy updates with traceable lineage.

## AI Operating Substrate Layers

### Layer 1 — Request/Response Contract Spine (Must-Add)
Canonical request/response contracts for model traffic are mandatory.

Required artifacts:
- `ai_model_request`
- `ai_model_response`

Minimum required fields:
- identity (`run_id`, `trace_id`, `step_id`)
- model/provider metadata
- prompt/template reference
- context bundle references
- declared output contract target
- latency/token/cost metadata
- refusal/error payload envelope

### Layer 2 — Prompt/Task Lifecycle Governance (Must-Add)
Prompt and task definitions must be versioned, admitted, and lifecycle-managed.

Required surfaces:
- prompt registry entry with immutable version identity
- task registry entry linking task intent to allowed prompt families
- admission and promotion policy hooks
- deprecation/revocation semantics

Output requirement:
- every model request must resolve to approved prompt/task lineage.

### Layer 3 — Routing Governance (Must-Add)
Routing decisions must be explicit artifacts, not hidden runtime behavior.

Required artifact:
- `routing_decision_record`

Required content:
- chosen route/model and candidate set
- policy constraints evaluated
- risk/latency/cost tradeoff summary
- confidence and fallback path
- reason code taxonomy

### Layer 4 — Context Admission Governance (Must-Add)
Context inclusion must be governed and replayable.

Required artifact:
- `context_source_admission_record`

Required content:
- source identities and trust tier
- inclusion/exclusion decisions and rationale
- sensitive-data and policy checks
- freshness and provenance assertions

### Layer 5 — Eval Registry and Slice Coverage (Must-Add)
Eval coverage must be cataloged against capabilities and risk classes.

Required artifacts:
- `eval_registry_entry`
- `eval_slice_summary` (or equivalent per run)

Required behavior:
- each substrate capability maps to one or more eval slices
- missing eval coverage blocks promotion

### Layer 6 — Override and Intervention Governance (Must-Add)
Human override and policy exceptions must produce deterministic artifacts.

Required artifacts:
- override decision artifact
- override rationale artifact
- override outcome artifact

Required behavior:
- override paths feed recurrence prevention and hotspot reporting.

### Layer 7 — Judgment Reuse Substrate (Must-Add)
The system must preserve and apply reusable judgment from prior runs.

Required artifacts:
- decision precedent index
- judgment application records
- judgment outcome labels

Required behavior:
- routing and control decisions can reference prior precedent bundles.

### Layer 8 — Derived Artifact Intelligence Jobs (Must-Add for MVP Intelligence)
Derived jobs synthesize decision-quality insights from operational artifacts.

Minimum required derived artifacts:
- `override_hotspot_report`
- `evidence_gap_hotspot_report`

Required behavior:
- periodic production (batch is acceptable for MVP)
- reproducible derivation inputs and lineage
- consumption by roadmap/control reviews

## Expanded Artifact Taxonomy
The taxonomy below separates base execution artifacts from intelligence derivatives.

### A. Execution Artifacts
- model request/response records
- prompt/task lineage records
- routing and context admission records
- output artifact envelope and provenance records

### B. Control Artifacts
- eval results/summaries
- control/enforcement decisions
- override/exception records
- policy lifecycle events

### C. Intelligence Artifacts
- hotspot reports
- cross-run comparison summaries
- evidence gap patterns
- judgment reuse efficacy summaries

### D. Governance Artifacts
- admission decisions
- promotion/freeze/revoke actions
- drift findings
- compliance snapshots

## Artifact Intelligence Layer Responsibilities

### Measurement Surface
Must provide metrics for:
- routing quality
- context source reliability
- override frequency and concentration
- eval slice coverage depth
- judgment reuse hit rate

### Comparison Surface
Must support:
- cross-run comparison by task family
- route/model policy comparison
- before/after policy-change comparison

### Reuse Surface
Must enable:
- precedent retrieval for similar decisions
- policy/routing hints from validated prior outcomes
- artifact templates for recurring failure modes

### Governance Surface
Must enforce:
- admission gating
- promotion gating
- expansion blocking when required artifacts absent
- explicit waiver artifacts for temporary exceptions

### Learning Surface
Must close loops:
- failure to eval slice creation/update
- eval outcomes to policy/routing updates
- override hotspots to design hardening backlog

## Must-Add Build Order (Hard Sequencing)
The following order is required before broader AI expansion:
1. request/response contract spine fully wired
2. prompt/task lifecycle governance
3. routing decision artifacts
4. context admission artifacts
5. eval registry + mandatory slice mapping
6. override governance artifacts
7. judgment reuse artifacts and precedent linkage
8. first derived intelligence jobs (override/evidence hotspots)

If any must-add layer is missing, partial, or bypassable:
- do not expand autonomy
- do not broaden model/provider matrix
- do not widen artifact-family breadth beyond required hardening

## Should-Have Build Order (After Must-Add Closure)
1. comparative route tournament analytics
2. dynamic policy tuning recommendations
3. artifact lineage graph query acceleration
4. proactive anomaly detection over artifact streams
5. multi-family derived intelligence dashboards

These are optional until must-add layers are governed and non-bypassable.

## Minimum Viable Artifact-Intelligence Slice (MVP)
A compliant MVP slice includes:
- governed prompt/task registry linkage
- canonical `ai_model_request`/`ai_model_response` production
- deterministic `routing_decision_record`
- deterministic `context_source_admission_record`
- `eval_registry_entry` plus at least one eval slice family wired to control
- one derived intelligence report (`override_hotspot_report` or `evidence_gap_hotspot_report`)

MVP acceptance criteria:
- golden path emits all required artifacts
- replay can reconstruct request, route, context admission, eval, and control outcomes
- at least one hotspot report is generated from real run artifacts
- roadmap/control process consumes hotspot findings for prioritization

## Drift Signals (Substrate-Specific)
Critical drift signals include:
- direct model calls outside adapter contracts
- prompt usage without lifecycle-governed registry identity
- routing decisions not emitted as artifacts
- context inclusion without admission artifacts
- eval registry absent or slice coverage stale
- recurring overrides without hotspot derivation
- judgment records created but not consumed
- AI capability expansion without parallel measurement/governance surface growth

## Hard Gates
The following gates block broader AI expansion:
1. any must-add substrate layer is missing
2. any must-add substrate layer is bypassable in production path
3. eval registry cannot demonstrate coverage for active task families
4. routing/context decisions are non-replayable
5. derived intelligence jobs are absent for active override/evidence patterns

## Repository Planning Requirements
Roadmap generation must:
1. inspect repository reality against this document,
2. classify each must-add component as `present_and_governed`, `present_but_partial`, `present_but_bypassable`, `missing`, or `ambiguous`,
3. sequence must-add closure before broader expansion,
4. publish explicit block reasons for any expansion-deferred steps,
5. report whether MVP artifact-intelligence slice is currently buildable.

## Governance Integration Requirements
This document must be treated as a required authority input by:
- strategy control document
- roadmap generator prompt
- roadmap authority notes and outputs
- gap analysis artifacts

Outputs that omit this authority input are non-compliant.

## Non-Goals for This Slice
- full artifact taxonomy implementation
- full intelligence-layer automation
- broad dashboard platform build-out
- broad autonomy expansion
- all-model orchestration optimization

## Definition of Done for Authority Adoption
Authority adoption is complete when:
1. this document is committed and referenced in authority stacks,
2. strategy and roadmap generation rules enforce substrate-first sequencing,
3. repository gap analysis exists against this document,
4. an MVP-first dependency-valid build plan is published,
5. broader AI expansion is explicitly gated on must-add substrate closure.
