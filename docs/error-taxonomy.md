# Error Taxonomy

This taxonomy defines machine-usable error categories across automation systems so evaluation harnesses, rule packs, and implementation repositories can classify failures consistently.

## Contract
- Every surfaced failure MUST map to one of the codes below.
- User-facing errors SHOULD follow the provided message patterns for determinism.
- Implementations SHOULD emit structured error objects with `code`, `category`, `message`, `context`, and `recommended_action`.

## Categories and Codes

| Code | Category | Meaning | Expected Message Pattern | Recommended Handling |
| --- | --- | --- | --- | --- |
| EXTRACTION_ERROR | Data Capture | Input could not be parsed or mapped (missing entity, incorrect mapping, partial extraction). | `[EXTRACTION_ERROR] <short description>; context=<input id>` | Halt pipeline; prompt for corrected input or apply fallback extraction rule. |
| SCHEMA_ERROR | Contract Validation | Required field missing, type mismatch, or enum violation against authoritative schemas. | `[SCHEMA_ERROR] <field> invalid: <reason>` | Fail fast; return schema guidance; block downstream generation. |
| GENERATION_ERROR | Content Synthesis | Model- or rule-generated text incomplete, low-confidence, or contradicts constraints. | `[GENERATION_ERROR] <artifact> generation failed: <reason>` | Mark artifact invalid; route to human review; retry with constrained prompt or rule set. |
| PROVENANCE_ERROR | Traceability | Provenance fields missing, inconsistent lineage, or unresolved derivation chain. | `[PROVENANCE_ERROR] <artifact> missing <field>` | Require provenance completion before publication; request source/revision mapping. |
| VALIDATION_ERROR | Quality Gates | Post-generation validation failed (tests, cross-checks, revision mismatch). | `[VALIDATION_ERROR] <check> failed for <artifact>` | Stop release; surface failed checks; request remediation or new inputs. |

## Usage Guidance
- Align implementation repository error classes or enums directly to these codes.
- Propagate the taxonomy into CLI and API responses so downstream evaluators and rule packs can reason about failure stages.
- Include revision identifiers in messages for SYS-001 to keep PDF lineage visible during debugging.
