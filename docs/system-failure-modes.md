# System Failure Modes

Common failure patterns to watch across systems, plus mitigation and detection expectations.

## Cross-System Failure Modes
- **Schema drift**: Inputs/outputs no longer match the referenced schema.  
  - Mitigation: Pin schema versions in run manifests; add schema validation as a blocking step.
- **Missing provenance**: Artifacts lack lineage or review status.  
  - Mitigation: Require `provenance` fields, enforce via evaluation harnesses, and fail fast on missing metadata.
- **Revision mismatch**: Referenced source revisions are absent.  
  - Mitigation: Validate required PDFs/revisions before processing; block on gaps.
- **Non-deterministic prompts**: Outputs change run-to-run.  
  - Mitigation: Fix seeds/temperature, version prompts/rules, and capture manifests.
- **Over-clustering/under-clustering** (comment/issue domains): Unique issues merged or duplicated.  
  - Mitigation: Rules for merge thresholds; human review for contested clusters.
- **Traceability loss in transformations**: Downstream artifacts drop parent IDs.  
  - Mitigation: Require `derived_from` and source references in every derived artifact.

## System-Specific Notes
- **Comment Resolution (SYS-001)**  
  - Risks: Incorrect section mapping; missing revision lineage; speculative dispositions.  
  - Detection: Eval fixtures for revision validation and section anchors; enforce confidence thresholds.
- **Transcript-to-Issue (SYS-002)**  
  - Risks: Missed action items; incorrect owner/priority; ambiguous provenance.  
  - Detection: Labeled transcript cases; checks for speaker/timestamp presence.
- **Study Artifact Generator (SYS-003)**  
  - Risks: Scenario/metric mismatch; missing assumptions linkage; narrative drift from data.  
  - Detection: Regression fixtures comparing rendered tables/figures against source data and assumptions.
- **Spectrum Study Compiler (SYS-004)**  
  - Risks: Incomplete ingestion; inconsistent intermediate formats; packaging artifacts without validation.  
  - Detection: Compiler passes that verify schema conformance and manifest completeness before emitting outputs.

## Change Control Expectations
- Log failures by type and system.
- When a new failure mode is discovered, add a regression case in `eval/` and update this document.
- Treat repeated non-determinism as a blocking issue until resolved.
