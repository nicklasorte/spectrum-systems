# spectrum-systems

Design and planning lab notebook for spectrum automation systems. Implementation code lives in separate repositories; this repo holds architecture, schemas, prompts, workflows, and evaluation plans. This is the governance/control-plane repo for SSOS GitHub operations across the czar organization.

## Start Here (fast path)
1. `docs/vision.md` — the why.
2. `docs/bottleneck-map.md` — the problems worth solving.
3. `SYSTEMS.md` and `docs/system-map.md` — what systems exist and where to find their docs.
4. `docs/system-philosophy.md` and `docs/system-interface-spec.md` — how systems must behave.
5. `docs/system-lifecycle.md` and `docs/system-status-registry.md` — lifecycle and current maturity.
6. `docs/data-provenance-standard.md` and `docs/reproducibility-standard.md` — lineage and rerun expectations.
7. `contracts/` and `schemas/` — authoritative artifact contracts and schema registry, plus `prompts/` for prompt standards.

## GitHub Operating Layer
- `.github/ISSUE_TEMPLATE/` — deterministic issue intake aligned to SSOS contracts.
- `.github/workflows/` — GitHub Project automation for SSOS boards.
- `scripts/setup-labels.sh` — reusable label bootstrapper for SSOS repos.
- `docs/github-operations.md` — governance guide and manual UI setup requirements.

## Navigation
- `systems/` — per-system overview/interface/design/evaluation/prompts (see `systems/README.md`).
- `schemas/` — authoritative data contracts; see `schemas/README.md` for inventory.
- `contracts/` — canonical artifact contracts, examples, and standards manifest (`CONTRACTS.md` for guidance).
- `prompts/` — prompt registry aligned to schemas and systems.
- `eval/` — evaluation harness scaffolds and `eval/test-matrix.md`.
- `docs/` — architecture standards, lifecycle, governance, and bottleneck analysis.
- `workflows/` — stepwise automation blueprints.
- `examples/` — illustrative artifacts.
- `issues/` — backlog and research questions.
- Comment resolution matrix spreadsheet contract (authoritative headers/order for the czar org): `docs/comment-resolution-matrix-spreadsheet-contract.md` with schema in `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`.
- PDF-anchored DOCX comment injection contract (authoritative PDF line-anchor insertion rules and audit requirements): schema in `contracts/schemas/pdf_anchored_docx_comment_injection_contract.schema.json` with fixtures in `contracts/examples/`.
- Meeting agenda contract (canonical next-meeting agenda generator from minutes + resolution matrix + optional comments/context): `contracts/docs/meeting-agenda-contract.md` with schema in `contracts/schemas/meeting_agenda_contract.schema.json` and examples in `contracts/examples/`.

## Repository Philosophy
- Schema-led, deterministic systems with explicit human review gates.
- Prompts and rules are versioned; evaluation must precede implementation changes.
- Provenance and reproducibility metadata are mandatory for material artifacts.
- Implementation code belongs in downstream repos; this repo stays documentation-first.

## Current Systems
- SYS-001 Comment Resolution Engine — `systems/comment-resolution/`
- SYS-002 Transcript-to-Issue Engine — `systems/transcript-to-issue/`
- SYS-003 Study Artifact Generator — `systems/study-artifact-generator/`
- SYS-004 Spectrum Study Compiler — `systems/spectrum-study-compiler/`
- SYS-005 Spectrum Program Advisor — `systems/spectrum-program-advisor/`
See `SYSTEMS.md` and `docs/system-status-registry.md` for details.

## Governance & Standards
- Contribution and decision history: `CONTRIBUTING.md`, `CHANGELOG.md`, `DECISIONS.md`.
- Terminology: `GLOSSARY.md`, `docs/terminology.md`.
- Validation expectations: `VALIDATION.md`, `docs/system-failure-modes.md`.
- Maintenance: `docs/repo-maintenance-checklist.md`, `docs/doc-governance.md`.
- Comment resolution matrix authority: this repo governs the spreadsheet contract consumed by `working-paper-review-engine` and `comment-resolution-engine`; column names and order live in `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json` and must not be redefined elsewhere.
- PDF-anchored DOCX comment injection authority: PDF page + line anchors with excerpt verification are required for Word comment insertion; engines must follow `contracts/schemas/pdf_anchored_docx_comment_injection_contract.schema.json` and emit the required audit report when generating commented DOCX outputs.
