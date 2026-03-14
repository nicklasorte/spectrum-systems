# Spectrum Pipeline Engine — Design (SYS-009)

## Purpose
Provide the orchestration layer that binds upstream engines into governed agendas and readiness bundles, preventing drift between contracts and ensuring deterministic sequencing.

## Bottleneck Addressed
BN-006: Orchestration gaps between upstream engines cause contract drift, inconsistent sequencing, and missing readiness signals, delaying decision quality and auditability.

## Inputs
- Canonical artifacts: meeting_minutes (+ validation), meeting_agenda_contract, comment_resolution_matrix_spreadsheet_contract, reviewer_comment_set.
- Readiness artifacts: program_brief, study_readiness_assessment, next_best_action_memo, decision_log, risk_register, assumption_register, milestone_plan.
- External references: external_artifact_manifest for non-repo assets, upstream study manifests, provenance records.
- Configuration: contract version pins, prompt/rule pack versions, model hash, deterministic mode, approval gates.

## Processing Pipeline
1. **Intake & Validation**: Validate all inputs against manifest-declared contract versions; fail fast on version drift or missing provenance.
2. **Graph Assembly**: Build dependency graph across minutes, comment matrices, agenda seeds, readiness artifacts, and external manifests.
3. **Agenda Construction**: Generate/update agenda items with traceability to minutes, comment dispositions, and unresolved items; enforce meeting_agenda_contract.
4. **Readiness Normalization**: Normalize risks, decisions, assumptions, milestones, and program context into a coherent readiness state; ensure linkage back to sources.
5. **Decision Products**: Populate program_brief, study_readiness_assessment, next_best_action_memo, and decision_log using deterministic prompts/rules.
6. **Consistency & Determinism Checks**: Verify cross-artifact consistency (IDs, references, version alignment) and reproducibility (byte-stable outputs given same inputs).
7. **Manifest Publication**: Emit pipeline run manifest capturing inputs, checksums, versions, prompts/rules, model hash, decisions taken, and failure boundaries triggered.

## Failure Boundaries
- Missing or version-mismatched inputs → block and emit failure code `INPUT_VERSION_MISMATCH`.
- Cross-artifact inconsistency (e.g., agenda item lacks minutes span) → block with `CONSISTENCY_CHECK_FAILED`.
- Non-deterministic outputs detected across replays → block with `DETERMINISM_BROKEN`.
- Downstream contract emission blocked until failure is cleared; partial outputs must not be published.
- Local prohibitions: no schema redefinition, no silent field additions, no local scoring heuristics that diverge from governance, and no writing governed artifacts outside manifest-controlled storage paths.

## Outputs
- Agenda package (JSON + optional DOCX) aligned to meeting_agenda_contract with explicit traceability to minutes and comment matrices.
- Readiness bundle containing advisor-aligned artifacts (program_brief, study_readiness_assessment, next_best_action_memo, decision_log, risk_register, assumption_register, milestone_plan).
- Pipeline run manifest with provenance and replay parameters.

## Evaluation Plan
- Contract conformance tests for every consumed/produced artifact.
- Determinism replay suite: same inputs/configuration must yield byte-stable JSON outputs.
- Cross-artifact consistency checks: agenda ↔ minutes; readiness artifacts ↔ risks/assumptions/decisions/milestones.
- Failure-boundary harness: inject missing/old versions to confirm correct blocking.

## Open Risks
- Upstream repo drift without automated contract pinning could erode determinism.
- Agenda generation heuristics must remain transparent; human review gates are required for carry-over logic.
- External artifact manifests may reference storage unavailable in CI; mocks/stubs required for evaluation.
