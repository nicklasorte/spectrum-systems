# Data Lake Strategy for Spectrum Systems

## Overview
This document defines the data collection strategy for the Spectrum Systems Lab Notebook. The goal is not to collect every possible file or dataset. The goal is to collect the structured data that sits between documents and decisions so future automation systems can operate on a traceable and reusable knowledge foundation.

The data lake should focus on:
- sources
- assumptions
- artifacts
- decisions

The data lake should preserve:
- provenance
- traceability
- revision history
- human review
- schema consistency

## Core Design Principle
The most valuable data is often not the raw engineering input, but the structured record of how expert judgment moved from input to output.

## Tier 1 — Highest-Value Data to Start Collecting Now

### 1. Comment-resolution history
Collect:
- comment ID
- agency
- comment text
- source document
- cited section or line
- proposed response
- final disposition
- final inserted text
- revision number
- reviewer

Why this is valuable: anchors how regulator feedback was interpreted, traced, and resolved, enabling deterministic reproduction of dispositions and report edits.

### 2. Meeting and TIG transcript outputs
Collect:
- transcript ID
- meeting date
- meeting type
- speaker
- agency
- extracted question
- concern or constraint
- topic or band
- disposition status
- required follow-up analysis
- linked report section

Why this is valuable: provides structured questions and concerns that drive backlog items, clarifies provenance, and keeps audit trails of verbal commitments.

### 3. Assumption registry
Collect:
- assumption ID
- study name
- assumption text
- source
- rationale
- sensitivity or impact level
- who approved it
- date approved
- later changes

Why this is valuable: captures explicit, reviewable assumptions that shape study outputs and can be sensitivity-tested or revised with lineage.

### 4. Study artifact metadata
Collect:
- artifact ID
- study
- artifact type
- title
- input datasets used
- code version
- assumptions used
- section where it appeared
- revision history
- reviewer

Why this is valuable: links generated artifacts to their inputs, code, and approval trail, supporting reproducibility and selective regeneration.

### 5. Prior study and waiver precedents
Collect:
- precedent ID
- band or frequency
- proposed action
- incumbents affected
- analytical method used
- mitigation or protection logic
- final outcome
- rationale
- year
- source documents

Why this is valuable: accelerates future studies with comparable cases, mitigation patterns, and decision rationales that can be cited or adapted.

## Tier 2 — Data That Makes the Lake Useful

### 6. Source-document registry
Collect:
- source document ID
- title
- source type
- author or owner
- date
- revision
- extracted entities
- machine-readable status
- trust level

### 7. Allocation and footnote extraction tables
Collect:
- frequency range
- federal services
- federal footnotes
- designation
- source edition
- extraction timestamp

### 8. Engineering method library
Collect:
- method ID
- propagation model
- clutter model
- reliability slice
- threshold or protection criterion
- use case
- limitations
- studies used in

### 9. Open questions and issue tracker records
Collect:
- issue ID
- issue text
- category
- owner
- dependency
- due date
- related meeting
- related report section
- current status

### 10. Revision-linked working paper corpus
Collect:
- working paper ID
- revision number
- changed sections
- linked comments
- inserted text
- rationale for change
- date

## Tier 3 — Data That Unlocks Simulation and Decision Engines

### 11. Simulation run registry
Collect:
- run ID
- study
- code commit hash
- inputs
- parameter set
- random seed
- output location
- runtime
- reviewer
- validation status

### 12. Normalized incumbent system characteristics
Collect:
- system ID
- service type
- location
- antenna height
- frequency range
- bandwidth
- emissions characteristics
- protection criteria
- time or operational constraints

### 13. Geography-linked reference layers
Collect:
- layer ID
- layer type
- geography scope
- source
- date
- resolution
- applicable studies

### 14. Output-to-report language pairs
Collect:
- pair ID
- technical input
- intermediate interpretation
- final report-ready text
- approver edits
- study

### 15. Risk and tradeoff records
Collect:
- record ID
- risk statement
- affected stakeholders
- technical basis
- legal or policy constraint
- tradeoff accepted
- decision maker
- date

## Tier 4 — Long-Game Infrastructure Data

### 16. Taxonomy and ontology tables
Collect:
- term ID
- term type
- normalized name
- aliases
- definition
- parent category

### 17. Validation and evaluation datasets
Collect:
- eval ID
- workflow type
- test case
- expected output
- actual output
- score
- reviewer

### 18. Data quality and provenance fields
All data classes should eventually include:
- source_document
- source_location
- timestamp
- confidence_score
- generated_by_system
- reviewer
- review_date

## Initial Priority Recommendation
The first five data classes to collect should be:
1. comment-resolution history
2. transcript outputs
3. assumption registry
4. source-document registry
5. study artifact metadata

These provide the strongest support for the first three planned systems: Comment Resolution Engine, Transcript-to-Issue Engine, and Study Artifact Generator.

## Provenance Requirements Across the Data Lake
Every Tier 1 through Tier 4 data class should eventually support the provenance standard. Provenance is not an optional metadata extra; it is the trust layer that makes the data lake reusable for automation and AI-assisted workflows.

## Data Lake Logical Architecture
The lake consists of four linked layers:

- Sources: authoritative documents, transcripts, and prior precedents captured with provenance.
- Assumptions: registries of explicit assumptions and methods that shape analyses.
- Artifacts: intermediate and final study artifacts, code versions, and revision-linked outputs.
- Decisions: dispositions, approvals, and tradeoff records derived from artifacts and assumptions.

Diagram:
```
Sources
↓
Assumptions
↓
Artifacts
↓
Decisions
```

## Manifest metadata expectations
- All artifact manifests that land in the lake must declare both `artifact_class` and `artifact_type` so orchestration layers can route, validate, and enforce class transitions.
- Manifest records should continue to carry versions, provenance, and checksums; the class identifier complements `artifact_type` and schema version to keep storage governance deterministic.

## Sidecar manifest alignment to the artifact envelope
- Sidecar manifests stored with lake objects should mirror the envelope fields: `artifact_class`, `artifact_type`, `contract_name`, `contract_version`, `produced_by`, and `derived_from`.
- Envelope-aligned sidecars let the lake index, deduplicate, and trace artifacts without reading the payload; payload validation still occurs via the contract schema.
- When ingesting governed artifacts, persist the envelope metadata alongside the payload pointer so orchestration and advisory engines can reason over lineage and compatibility uniformly.
