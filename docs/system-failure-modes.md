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
- **Spectrum Program Advisor (SYS-005)**  
  - Missing or stale input artifacts: Description: advisor recommendations reflect outdated milestone/risk/decision bundles; Likely cause: manifests not refreshed after upstream review cycles or ingestion gaps; Detection: freshness checks comparing manifest timestamps and required artifact counts against current schema versions; Mitigation: block runs when manifests lag, require referenced artifacts in run manifests, and rehydrate inputs from authoritative storage before advising.  
  - Dependency graph inconsistencies between milestones, risks, and decisions: Description: the advisor surfaces paths that violate prerequisite or mitigation links; Likely cause: partial updates to one register without propagating to the others; Detection: graph validation that ensures bidirectional references and consistent IDs across the three registers; Mitigation: enforce atomic updates via contract-aware editors and run consistency checks before emitting recommendations.  
  - Inconsistent field normalization across inputs: Description: normalized fields (owners, statuses, domains) diverge across inputs, skewing prioritization; Likely cause: mixed-controlled vocabularies or missing normalization during ingest; Detection: normalization audits comparing categorical fields to allowed enums per contract; Mitigation: centralized normalization layer with reject-on-unknown enforcement and repair rules applied before scoring.  
  - Contract version mismatches across upstream systems: Description: advisor stitches artifacts from incompatible schema versions; Likely cause: upstream systems emitting newer/older contract revisions without coordinated rollout; Detection: contract version diff check in the run manifest and schema validation pinned to expected versions; Mitigation: require compatible version sets per run, add upgrade/downgrade adapters, and fail fast on mismatches.  
- **Meeting Minutes Engine (SYS-006)**  
  - Transcripts lacking timestamps or speaker attribution: Description: minutes lose ordering and speaker intent; Likely cause: upstream recorder/export missing structured metadata; Detection: transcript intake validation that asserts presence of timestamps and speaker labels per segment; Mitigation: reject transcripts missing required fields and request re-export, or fall back to manual speaker tagging workflow.  
  - Template mismatch between contract schema and DOCX renderer: Description: minutes render with misaligned tables/fields or missing sections; Likely cause: renderer template drift from meeting_minutes contract revisions; Detection: schema-to-template compatibility check plus golden-render regression comparisons; Mitigation: version templates alongside contracts, block render when mismatched, and regenerate templates on contract updates.  
  - Downstream systems adding fields that violate the meeting_minutes contract: Description: augmented fields leak into canonical minutes and break consumers; Likely cause: downstream enrichment tools writing back non-contract fields; Detection: contract validation on final minutes artifact with strict additionalProperties=false behavior; Mitigation: enforce read-only contract artifacts, gate merges through schema validation, and strip unrecognized fields before publish.  
  - Malformed transcript segments causing minutes generation errors: Description: bad segmentation (overlaps, empty text, out-of-order) causes renderer failures or dropped content; Likely cause: transcription pipeline errors or manual edits without validation; Detection: structural checks for monotonic timestamps, non-empty content, and segment continuity; Mitigation: auto-repair simple ordering issues, flag irreparable segments for human review, and rerun transcription where needed.  

## Change Control Expectations
- Log failures by type and system.
- When a new failure mode is discovered, add a regression case in `eval/` and update this document.
- Treat repeated non-determinism as a blocking issue until resolved.
