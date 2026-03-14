# DOCX Comment Injection Engine (SYS-008)

Purpose: apply PDF/DOCX-anchored comments and dispositions into governed DOCX deliverables while preserving provenance and contract fidelity.

- **Bottleneck**: BN-001 — manual insertion of comments/dispositions into DOCX outputs is slow and error-prone, breaking contract alignment.
- **Inputs**: `comment_resolution_matrix_spreadsheet_contract`, `pdf_anchored_docx_comment_injection_contract`, DOCX source templates, working paper revisions, provenance records, optional annotated PDFs.
- **Outputs**: annotated DOCX matching the anchored comment contract, updated `comment_resolution_matrix_spreadsheet_contract` with injection status, run manifest with provenance and deterministic parameters.
- **Upstream Dependencies**: working-paper-review-engine, comment-resolution-engine.
- **Downstream Consumers**: spectrum-pipeline-engine, publication workflows, meeting agenda builders.
- **Related Assets**: `contracts/examples/pdf_anchored_docx_comment_injection_contract.json`, `CONTRACTS.md`, `workflows/docx-comment-injection-engine.md`.
- **Lifecycle Status**: Design drafted; implementation repo must declare pins to this spec before building automation.

Outputs must never alter canonical headers or field names and must preserve anchor fidelity to the source PDF/DOCX locations.
