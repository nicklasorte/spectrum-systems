# DOCX Comment Injection Engine

## Purpose
Inject anchored comments and dispositions into DOCX deliverables while preserving contract fidelity and provenance.

## Steps
1. Validate incoming `comment_resolution_matrix_spreadsheet_contract` and anchored payload versions.
2. Resolve anchors against target PDF/DOCX revision; flag ambiguities.
3. Insert comments/dispositions deterministically into DOCX.
4. Update matrix with injection status and provenance.
5. Emit annotated DOCX and run manifest; block on validation or determinism failures.

## References
- Interface: `systems/docx-comment-injection-engine/interface.md`
- Design: `systems/docx-comment-injection-engine/design.md`
- Contracts: `contracts/standards-manifest.json`, `contracts/examples/pdf_anchored_docx_comment_injection_contract.json`
- Prompts: `systems/docx-comment-injection-engine/prompts.md`
- Evaluation: `systems/docx-comment-injection-engine/evaluation.md`
