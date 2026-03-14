# Spectrum Pipeline Engine — Interface (SYS-009)

## Purpose
Sequence upstream contract-governed artifacts into agenda and decision-readiness outputs without mutating canonical payloads.

## Inputs
- `meeting_minutes` (JSON + DOCX + validation report) aligned to `contracts/meeting_minutes_contract.yaml`.
- `meeting_agenda_contract` (optional seed for recurrence and carry-forward items).
- `comment_resolution_matrix_spreadsheet_contract` plus `reviewer_comment_set` from working-paper-review-engine and comment-resolution-engine.
- `external_artifact_manifest` describing upstream study artifacts stored outside GitHub.
- Readiness artifacts: `program_brief`, `study_readiness_assessment`, `next_best_action_memo`, `decision_log`, `risk_register`, `assumption_register`, `milestone_plan` (when present).
- Run configuration: target contract versions, rule pack versions, prompt set, model hash, execution policy (determinism/approval gates).

## Contracts and Schemas
- Must consume and emit contract versions declared in `contracts/standards-manifest.json`.
- Pipeline run manifest must record: input artifact checksums, contract versions, prompt/rule versions, model hash, timestamps, operator, and failure boundary taken.
- No contract key renaming or schema extension is permitted; upstream artifacts must be validated before orchestration.

## Sequencing and Orchestration Responsibilities
- Enforce ordering: validated minutes and comment matrices feed agenda generation; agendas plus readiness artifacts feed advisor-ready bundles.
- Maintain cross-artifact linkage: agenda items must point to minutes spans or comment IDs; readiness outputs must point to manifest entries for risks/assumptions/decisions/milestones.
- Record deterministic replay parameters (contract pins, prompt/rule versions, seeds, model hash) in every run manifest.
- Detect and halt on upstream drift; do not publish partial bundles when any upstream dependency fails validation.

## Outputs
- Agenda packages (JSON + optional DOCX) aligned to `meeting_agenda_contract` with linkage back to minutes and comment matrices.
- Readiness bundle containing `program_brief`, `study_readiness_assessment`, `next_best_action_memo`, `decision_log`, `risk_register`, `assumption_register`, `milestone_plan`, and cross-artifact consistency checks.
- Pipeline run manifest documenting sequencing decisions, dependency graph, validation outcomes, and deterministic replay parameters.

## Validation Rules
- Fail if any input contract version deviates from the manifest or is missing required provenance.
- Enforce deterministic ordering: identical inputs and configuration must yield byte-stable JSON outputs aside from manifest metadata.
- Validate cross-artifact consistency (e.g., agenda items backed by minutes spans; readiness outputs reference current risks/assumptions/decisions).
- Reject partial orchestration: incomplete upstream sets must block downstream publication and surface explicit failure codes.

## Prohibited Local Behaviors
- Must not redefine schemas, rename contract fields, or embed local-only fields into governed artifacts.
- Must not generate or mutate upstream artifacts in place; only orchestrate validated copies into downstream bundles.
- Must not bypass manifest recording (inputs, versions, prompts/rules, seeds, model hash) or emit readiness scores/rules that diverge from spectrum-systems governance.

## Human Review Points
- Review agenda carry-over logic and mapping of comment dispositions to agenda items.
- Confirm readiness scoring and dependency linkage across risks, decisions, assumptions, and milestones.
- Approve run manifest (inputs, versions, validation outcomes) before publishing bundles to downstream consumers.
