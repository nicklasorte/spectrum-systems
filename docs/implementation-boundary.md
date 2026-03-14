# Implementation Boundary

## Purpose
Clarify ownership between this architecture repository (spectrum-systems) and executable implementation repositories so system contracts remain stable while implementations evolve.

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

### SYS-001 Comment Resolution Engine
- Architecture source: `spectrum-systems`
- Implementation repo: `comment-resolution-engine`
- Interface spec: `systems/comment-resolution/interface.md`
- Canonical schemas consumed: `schemas/comment-schema.json`, `schemas/issue-schema.json`, `schemas/provenance-schema.json`, `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`
- Rule packs consumed: `rules/comment-resolution/`
- Evaluation assets: `eval/comment-resolution/`
- Required repo declarations for conformance:
  - `system_id: SYS-001`
  - Contract/schema version pins (comment schema, issue schema, provenance schema, matrix contract)
  - Rule pack + prompt version hash; provenance guidance version
  - Evaluation manifest with fixtures + results; external storage policy for matrices and manifests

### SYS-002 Transcript-to-Issue Engine
- Architecture source: `spectrum-systems`
- Implementation repo: `transcript-to-issue-engine`
- Interface spec: `systems/transcript-to-issue/interface.md`
- Canonical schemas consumed: `schemas/issue-schema.json`, `schemas/provenance-schema.json`
- Rule packs consumed: none published; implementation must document local rules
- Evaluation assets: `eval/transcript-to-issue/`
- Required repo declarations for conformance:
  - `system_id: SYS-002`
  - Schema version pins (issue, provenance) and prompt set hash
  - Transcript ingestion policy and redaction controls
  - Evaluation manifest with fixtures + results; external storage policy for transcripts

### SYS-003 Study Artifact Generator
- Architecture source: `spectrum-systems`
- Implementation repo: `study-artifact-generator`
- Interface spec: `systems/study-artifact-generator/interface.md`
- Canonical schemas consumed: `schemas/study-output-schema.json`, `schemas/assumption-schema.json`, `schemas/provenance-schema.json`
- Rule packs consumed: none published; implementation must document local rendering rules
- Evaluation assets: `eval/study-artifacts/`
- Required repo declarations for conformance:
  - `system_id: SYS-003`
  - Schema version pins (study-output, assumption, provenance) and prompt set hash
  - Template/rendering rule versions
  - Evaluation manifest with fixtures + results; external storage policy for simulation inputs/outputs

### SYS-004 Spectrum Study Compiler
- Architecture source: `spectrum-systems`
- Implementation repo: `spectrum-study-compiler`
- Interface spec: `systems/spectrum-study-compiler/interface.md`
- Canonical schemas consumed: `schemas/compiler-manifest.schema.json`, `schemas/artifact-bundle.schema.json`, `schemas/diagnostics.schema.json`, `schemas/study-output-schema.json`, `schemas/provenance-schema.json`
- Rule packs consumed: none published; compiler-specific validation rules must be declared locally
- Evaluation assets: `eval/spectrum-study-compiler/`
- Required repo declarations for conformance:
  - `system_id: SYS-004`
  - Schema version pins (compiler manifest, artifact bundle, diagnostics, study-output, provenance)
  - Prompt/rendering rule set hash; deterministic ordering policy
  - Evaluation manifest with fixtures + results; external storage policy for packaged artifacts

### SYS-005 Spectrum Program Advisor
- Architecture source: `spectrum-systems`
- Implementation repo: `spectrum-program-advisor`
- Interface spec: `systems/spectrum-program-advisor/interface.md`
- Canonical schemas consumed: `contracts/schemas/program_brief.schema.json`, `contracts/schemas/study_readiness_assessment.schema.json`, `contracts/schemas/next_best_action_memo.schema.json`, `contracts/schemas/decision_log.schema.json`, `contracts/schemas/risk_register.schema.json`, `contracts/schemas/assumption_register.schema.json`, `contracts/schemas/milestone_plan.schema.json`
- Rule packs consumed: none published; readiness scoring rules must be declared locally
- Evaluation assets: `eval/spectrum-program-advisor/`
- Required repo declarations for conformance:
  - `system_id: SYS-005`
  - Schema version pins for all readiness artifacts + prompt/rule hash
  - Provenance coverage and external storage policy for readiness bundles
  - Evaluation manifest with fixtures + results; dependency on pipeline run manifests

### SYS-006 Meeting Minutes Engine
- Architecture source: `spectrum-systems`
- Implementation repo: `meeting-minutes-engine`
- Interface spec: `systems/meeting-minutes-engine/interface.md`
- Canonical schemas consumed: `contracts/meeting_minutes_contract.yaml`
- Rule packs consumed: none published; template/anchor rules must be declared locally
- Evaluation assets: `systems/meeting-minutes-engine/evaluation.md`
- Required repo declarations for conformance:
  - `system_id: SYS-006`
  - Contract version pin for meeting minutes + prompt/template hash
  - Transcript handling and redaction policy; provenance guidance version
  - Evaluation manifest with fixtures + results; external storage policy for transcripts/minutes artifacts

### SYS-007 Working Paper Review Engine
- Architecture source: `spectrum-systems`
- Implementation repo: `working-paper-review-engine`
- Interface spec: `systems/working-paper-review-engine/interface.md`
- Canonical schemas consumed: `contracts/examples/reviewer_comment_set.json`, `contracts/examples/comment_resolution_matrix_spreadsheet_contract.json`, `contracts/examples/working_paper_input.json`
- Rule packs consumed: none published; reviewer assignment and normalization rules must be declared locally
- Evaluation assets: `systems/working-paper-review-engine/evaluation.md`
- Required repo declarations for conformance:
  - `system_id: SYS-007`
  - Contract version pins for reviewer comment set, matrix, and working paper input
  - Prompt/rule hash for normalization; anchor extraction policy
  - Evaluation manifest with fixtures + results; external storage policy for PDFs and matrices

### SYS-008 DOCX Comment Injection Engine
- Architecture source: `spectrum-systems`
- Implementation repo: `docx-comment-injection-engine`
- Interface spec: `systems/docx-comment-injection-engine/interface.md`
- Canonical schemas consumed: `contracts/schemas/pdf_anchored_docx_comment_injection_contract.schema.json`, `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`
- Rule packs consumed: none published; anchoring/injection rules must be declared locally
- Evaluation assets: `systems/docx-comment-injection-engine/evaluation.md`
- Required repo declarations for conformance:
  - `system_id: SYS-008`
  - Contract version pins for anchored DOCX injection + matrix contract
  - Prompt/rule hash for anchor validation; manifest recording of line/page references
  - Evaluation manifest with fixtures + results; external storage policy for DOCX/PDF artifacts

### SYS-009 Spectrum Pipeline Engine
- Architecture source: `spectrum-systems`
- Implementation repo: `spectrum-pipeline-engine`
- Interface spec: `systems/spectrum-pipeline-engine/interface.md`
- Canonical schemas consumed: `contracts/meeting_minutes_contract.yaml`, `contracts/schemas/meeting_agenda_contract.schema.json`, `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`, `contracts/schemas/program_brief.schema.json`, `contracts/schemas/study_readiness_assessment.schema.json`, `contracts/schemas/next_best_action_memo.schema.json`, `contracts/schemas/decision_log.schema.json`, `contracts/schemas/risk_register.schema.json`, `contracts/schemas/assumption_register.schema.json`, `contracts/schemas/milestone_plan.schema.json`, `contracts/schemas/external_artifact_manifest.schema.json` (from `contracts/standards-manifest.json`)
- Rule packs consumed: none published; orchestration/agenda/readiness rules must be declared locally but may not redefine contracts
- Evaluation assets: `systems/spectrum-pipeline-engine/evaluation.md`
- Required repo declarations for conformance:
  - `system_id: SYS-009`
  - Pinned contract versions for all consumed artifacts + meeting agenda contract; prompt/rule hash for orchestration
  - Provenance policy for manifests and external artifact references; deterministic replay policy
  - Evaluation manifest with fixtures + results; external storage policy for bundles and manifests

Implementation repositories SHOULD keep these declarations in code or metadata to preserve traceability across releases.
