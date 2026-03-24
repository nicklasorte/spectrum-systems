# HS-18 Glossary Injection + Domain Canonicalization

HS-18 adds a governed glossary layer to HS-06/HS-07 context composition.
The runtime now injects canonical glossary definitions into `context_items` as
`glossary_definition` items.

## Glossary entry contract

Canonical glossary records use:
- `contracts/schemas/glossary_entry.schema.json`
- `contracts/examples/glossary_entry.json`

Required fields:
- `term_id`
- `canonical_term`
- `definition`
- `domain_scope`
- `version`
- `status` (`approved` or `deprecated`)
- `provenance_refs`
- deterministic identity/timestamp fields (`glossary_entry_id`, `created_at`)

The contract is strict (`additionalProperties: false`).

## Injection rules

1. Terms are declared via `context_bundle.glossary_terms`.
2. Registry entries are provided to composition via `glossary_registry_entries`.
3. Selection is deterministic and exact-only:
   - explicit references (`term_id`) first
   - bounded exact text fallback for string requests
4. Selected entries are injected into:
   - `context_bundle.glossary_definitions`
   - `context_items[]` as `item_type = glossary_definition`
5. `glossary_canonicalization` captures selected entry IDs and unresolved terms.

## Canonicalization rules

- **No fuzzy matching** in this slice.
- Match mode is fixed to `exact`.
- Deprecated entries are blocked unless `allow_deprecated=true`.
- Duplicate active definitions for `term_id + domain_scope` are rejected.
- Ambiguous active definitions for same canonical term/domain are rejected.

## Fail-closed behavior

Composition fails closed when:
- glossary entry schema is invalid
- duplicate active definitions exist for the same term/domain
- ambiguous active definitions exist
- required term has no canonical definition (when fail-on-missing is enabled)
- deprecated entry is selected without explicit allowance

## Runtime + trace linkage

Runtime trace linkage includes:
- `agent_execution_trace.context_bundle_id`
- `context_source_summary.glossary_entry_refs`
- `context_source_summary.glossary_definition_item_refs`

Trace stores glossary IDs and context item IDs, not duplicated full glossary payloads.

## Out of scope

- ontology/knowledge graph systems
- semantic/fuzzy matching
- retrieval redesign
- routing changes
