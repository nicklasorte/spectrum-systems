# Prompt Registry (HS-01)

HS-01 introduces a governed, artifact-first prompt registry for deterministic runtime prompt selection.

## Prompt artifact shape

Contract: `contracts/schemas/prompt_registry_entry.schema.json`

Required fields:
- `artifact_type` (`prompt_registry_entry`)
- `schema_version` (`1.0.0`)
- `prompt_id`
- `prompt_version` (immutable semantic version)
- `created_at`
- `status` (`draft` | `approved` | `deprecated`)
- `owner`
- `risk_class`
- `prompt_text`
- `prompt_purpose`
- `linked_eval_set_ids`
- `runtime_metadata`
  - `selection_key` (`<prompt_id>@<prompt_version>`)
  - `immutability_hash` (`sha256:<64-hex>` over `prompt_text`)

Immutability rule: prompt versions are immutable artifacts. If prompt text changes, publish a new `prompt_version`.

## Alias map shape

Contract: `contracts/schemas/prompt_alias_map.schema.json`

Required fields:
- `artifact_type` (`prompt_alias_map`)
- `schema_version` (`1.0.0`)
- `created_at`
- `alias_scope` (`ag_runtime`)
- `aliases[]` entries with:
  - `prompt_id`
  - `alias` (`dev` | `staging` | `prod`)
  - `prompt_version`
  - `allow_deprecated` (bool)

A runtime alias resolves to exactly one immutable prompt version per `prompt_id`.

## Resolution rules

Resolver input: `(prompt_id, alias, registry_entries, alias_map)`

Resolver behavior:
1. Validate all artifacts against governed schemas.
2. Verify `selection_key` and `immutability_hash` semantics for each entry.
3. Enforce uniqueness of immutable entries (`prompt_id`, `prompt_version`).
4. Resolve exactly one alias binding for `(prompt_id, alias)`.
5. Resolve exactly one matching prompt entry.
6. Enforce status policy:
   - `draft` is never runtime-selectable.
   - `deprecated` is selectable only when alias binding sets `allow_deprecated=true`.
   - `approved` is selectable.

No fallback-to-latest behavior exists.

## Runtime integration (AG runtime seam)

`run_agent_golden_path` now resolves prompt selection before bounded step execution.
The resolved prompt linkage is emitted into `agent_execution_trace.prompt_resolution`:
- `prompt_id`
- `prompt_version`
- `requested_alias`
- `resolution_source`
- `status`

This enables deterministic eval attribution and replay auditability.

## Fail-closed behavior

Runtime fails closed when:
- prompt registry entry file is missing or malformed
- alias map file is missing or malformed
- schema validation fails
- `selection_key` or hash semantics fail
- alias resolution is missing or ambiguous
- alias maps to missing immutable entry
- selected prompt status is invalid for runtime policy

## Rollback and attribution posture

Because runtime traces record exact prompt ID/version + alias, downstream systems can:
- attribute eval/failure outcomes to governed prompt versions
- replay with the same prompt selection semantics
- perform deterministic rollback by updating alias maps to known approved versions
