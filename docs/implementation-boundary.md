# Implementation Boundary

## Purpose
Clarify ownership between this architecture repository (spectrum-systems) and executable implementation repositories so system contracts remain stable while implementations evolve.

## Production-Code Boundary Rule

`spectrum-systems` is a documentation-first governance repository. Per `CLAUDE.md` and `DECISIONS.md` (Decision 1 and Decision 2), this repository **must not contain production implementation code**. Production pipelines, runtime executables, and deployable services belong in dedicated downstream implementation repositories.

This boundary is enforced in two ways:
1. **Manually:** via this document, `CLAUDE.md`, and the governance conformance checklist (`docs/governance-conformance-checklist.md`).
2. **Mechanically (planned):** via artifact boundary CI extension (action A-3 from the 2026-03-16 governance deep review). Until A-3 is implemented, the boundary is enforced through manual review.

### Evaluation and example code

Evaluation harnesses (`eval/`), evaluation rubrics (`evals/`), and example artifacts (`examples/`, `contracts/examples/`) may reside in this repository. These are not production services — they are test fixtures, reference implementations, and illustrative artifacts used to validate governance standards.

Evaluation code that grows into a deployable service must be relocated to a dedicated implementation repository before it reaches Pilot status.

### spectrum_systems/ — current status

The `spectrum_systems/` Python package (including `spectrum_systems/study_runner/` and `run_study.py`) is present in this repository as an **evaluation scaffold**. It was originally introduced to support contract loading and study-runner prototype work.

**Status as of 2026-03-16:** Pending relocation to a dedicated implementation repository.

This package has been flagged as a boundary violation in the following reviews:
- RC-1 (`2026-03-15-ecosystem-constitution-audit`)
- A-1 (`2026-03-15-governance-architecture-audit`)
- GA-008 (`2026-03-14-governance-architecture-review`)
- F-3 (`2026-03-16-governance-constitution-deep-review`)

Until relocation is completed, `spectrum_systems/` remains here with explicit evaluation-scaffold status. It must not be extended with production pipeline logic. The boundary CI extension (A-3) will flag this directory once implemented.

See `DECISIONS.md` Decision 5 for the formal boundary resolution decision.

## Architecture Repository (spectrum-systems) Owns
- System specifications and architecture decisions (e.g., `systems/comment-resolution/interface.md`).
- Authoritative schemas and provenance guidance (`schemas/*.json`, `docs/provenance-implementation-guidance.md`).
- Error taxonomy and message patterns (`docs/error-taxonomy.md`).
- Prompt standards and evaluation definitions (`prompts/`, `eval/`).
- Shared rule packs and profiles under `rules/`.

## Implementation Repositories Own
- Executable code, pipelines, connectors, and runtime configuration.
- Local fallbacks and heuristics that operate when external rule packs are absent.
- Integration with storage, access control, and deployment concerns.

## Declarations Required in Implementation Repos
Implementation repositories MUST explicitly declare:
- `system_id` implemented (e.g., `SYS-001` Comment Resolution Engine).
- Spec, schema, provenance guidance, and error taxonomy versions targeted.
- Rule profile/prompt set/version in use (or explicit statement that local defaults are active).
- Evaluation harness results (version, date, fixture set) and external storage policy.

## System Mappings

Each mapping uses the same template so implementation engineers can import the right specs, schemas, and evaluation harnesses consistently.

### SYS-001 Comment Resolution Engine
- **System ID**: `SYS-001`
- **Implementation repository**: `comment-resolution-engine`
- **Architecture source**: `spectrum-systems`
- **Interface spec location**: `systems/comment-resolution/interface.md`
- **Canonical schemas consumed**: `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`; `schemas/comment-schema.json`; `schemas/issue-schema.json`; `schemas/assumption-schema.json`; `schemas/provenance-schema.json`
- **Canonical schemas produced**: `schemas/comment-schema.json`; `schemas/issue-schema.json`; `schemas/assumption-schema.json` (when referenced); `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json` (normalized exports); `schemas/provenance-schema.json` (run manifests)
- **Rule packs consumed**: `rules/comment-resolution/`
- **Evaluation harness location**: `eval/comment-resolution/`
- **Required conformance declarations for implementation repos**:
  - `system_id: SYS-001`
  - Version pins for interface spec, spreadsheet contract, comment/issue/assumption/provenance schemas
  - Prompt and rule version hash plus provenance guidance version
  - Evaluation manifest covering fixture set, results, and external storage policy for matrices/manifests

### SYS-002 Transcript to Issue Extractor
- **System ID**: `SYS-002`
- **Implementation repository**: `transcript-to-issue-engine`
- **Architecture source**: `spectrum-systems`
- **Interface spec location**: `systems/transcript-to-issue/interface.md`
- **Canonical schemas consumed**: `schemas/issue-schema.json`; `schemas/provenance-schema.json`; optional `schemas/assumption-schema.json` for linked assumptions
- **Canonical schemas produced**: `schemas/issue-schema.json`; `schemas/provenance-schema.json` (with transcript references)
- **Rule packs consumed**: none published; pin prompt set in `prompts/transcript-to-issue.md`
- **Evaluation harness location**: `eval/transcript-to-issue/`
- **Required conformance declarations for implementation repos**:
  - `system_id: SYS-002`
  - Version pins for issue/provenance (and assumption, when used) schemas
  - Prompt set hash, transcript ingestion policy, and redaction controls
  - Evaluation manifest with fixtures/results and storage policy for transcripts and manifests

### SYS-003 Study Artifact Generator
- **System ID**: `SYS-003`
- **Implementation repository**: `study-artifact-generator`
- **Architecture source**: `spectrum-systems`
- **Interface spec location**: `systems/study-artifact-generator/interface.md`
- **Canonical schemas consumed**: `schemas/study-output-schema.json`; `schemas/assumption-schema.json`; `schemas/provenance-schema.json`
- **Canonical schemas produced**: `schemas/study-output-schema.json`; `schemas/provenance-schema.json`; assumption references aligned to `schemas/assumption-schema.json`
- **Rule packs consumed**: none published; pin templates/rules in `prompts/report-drafting.md`
- **Evaluation harness location**: `eval/study-artifacts/`
- **Required conformance declarations for implementation repos**:
  - `system_id: SYS-003`
  - Version pins for study-output, assumption, and provenance schemas
  - Template/prompt/rule version identifiers and deterministic formatting policy
  - Evaluation manifest with fixtures/results and storage policy for simulation inputs/outputs

### SYS-004 Comment Adjudication Engine (assets under `systems/spectrum-study-compiler/`)
- **System ID**: `SYS-004`
- **Implementation repository**: `spectrum-study-compiler`
- **Architecture source**: `spectrum-systems`
- **Interface spec location**: `systems/spectrum-study-compiler/interface.md`
- **Canonical schemas consumed**: `schemas/compiler-manifest.schema.json`; `schemas/artifact-bundle.schema.json`; `schemas/diagnostics.schema.json`; `schemas/study-output-schema.json`; `schemas/provenance-schema.json`
- **Canonical schemas produced**: `schemas/artifact-bundle.schema.json`; `schemas/compiler-manifest.schema.json`; `schemas/diagnostics.schema.json`; `schemas/provenance-schema.json`
- **Rule packs consumed**: compiler pass/validation rule definitions versioned with the manifest (no published rule pack)
- **Evaluation harness location**: `eval/spectrum-study-compiler/`
- **Required conformance declarations for implementation repos**:
  - `system_id: SYS-004`
  - Version pins for compiler-manifest, artifact-bundle, diagnostics, study-output, and provenance schemas
  - Declared compiler pass set/order and rule set hash with deterministic ordering policy
  - Evaluation manifest with fixtures/results and external storage policy for packaged artifacts and manifests

### SYS-005 Spectrum Program Advisor
- **System ID**: `SYS-005`
- **Implementation repository**: `spectrum-program-advisor`
- **Architecture source**: `spectrum-systems`
- **Interface spec location**: `systems/spectrum-program-advisor/interface.md`
- **Canonical schemas consumed**: `contracts/schemas/working_paper_input.schema.json`; `contracts/schemas/comment_resolution_matrix.schema.json`; `contracts/meeting_minutes_contract.yaml`; `contracts/schemas/provenance_record.schema.json`; readiness input artifacts (`contracts/schemas/program_brief.schema.json`, `contracts/schemas/study_readiness_assessment.schema.json`, `contracts/schemas/next_best_action_memo.schema.json`, `contracts/schemas/decision_log.schema.json`, `contracts/schemas/risk_register.schema.json`, `contracts/schemas/assumption_register.schema.json`, `contracts/schemas/milestone_plan.schema.json`)
- **Canonical schemas produced**: `contracts/schemas/program_brief.schema.json`; `contracts/schemas/study_readiness_assessment.schema.json`; `contracts/schemas/next_best_action_memo.schema.json`; `contracts/schemas/decision_log.schema.json`; `contracts/schemas/risk_register.schema.json`; `contracts/schemas/assumption_register.schema.json`; `contracts/schemas/milestone_plan.schema.json`; `contracts/schemas/provenance_record.schema.json`
- **Rule packs consumed**: none published; readiness scoring/normalization rules and prompts in `systems/spectrum-program-advisor/prompts.md`
- **Evaluation harness location**: `systems/spectrum-program-advisor/evaluation.md`
- **Required conformance declarations for implementation repos**:
  - `system_id: SYS-005`
  - Version pins for all consumed inputs and produced readiness artifacts plus prompt/rule hash
  - Provenance coverage expectations and external storage policy for readiness bundles
  - Evaluation manifest with fixtures/results and dependency on pipeline run manifests

### SYS-006 Meeting Minutes Engine
- **System ID**: `SYS-006`
- **Implementation repository**: `meeting-minutes-engine`
- **Architecture source**: `spectrum-systems`
- **Interface spec location**: `systems/meeting-minutes-engine/interface.md`
- **Canonical schemas consumed**: `contracts/meeting_minutes_contract.yaml`; `contracts/schemas/provenance_record.schema.json` for manifest references
- **Canonical schemas produced**: `contracts/meeting_minutes_contract.yaml`; `contracts/schemas/provenance_record.schema.json` (run manifests/validation reports)
- **Rule packs consumed**: none published; template and prompt set pinned in `systems/meeting-minutes-engine/prompts.md`
- **Evaluation harness location**: `systems/meeting-minutes-engine/evaluation.md`
- **Required conformance declarations for implementation repos**:
  - `system_id: SYS-006`
  - Contract version pin for meeting minutes, template identifier, and prompt/rule hash
  - Transcript handling and redaction policy plus provenance guidance version
  - Evaluation manifest with fixtures/results and storage policy for transcripts and minutes artifacts

Implementation repositories SHOULD keep these declarations in code or metadata to preserve traceability across releases.
