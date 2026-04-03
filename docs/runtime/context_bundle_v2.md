# CTX Governed Context Pipeline (context_bundle_v2)

## Core principle
Context is not memory.

Context is deterministically:
1. selected
2. ranked
3. injected
4. lifecycle-governed

Control/eval/certification remain authoritative.

## Contract: `context_bundle_v2`
`contracts/schemas/context_bundle_v2.schema.json` defines strict bounded context packaging:
- `additionalProperties: false`
- explicit required fields
- bounded arrays
- deterministic ordering requirement (`priority_metadata.deterministic_ordering = true`)
- canonical serialization requirement (`json_sort_keys_compact_utf8`)

Required payload fields include:
- `context_id`, `schema_version`, `target_scope`
- selected references across review/eval/risk/build/handoff/touched-module/intent dimensions
- `priority_metadata`
- `created_at`, `trace_id`, `source_refs`

## Selection model
`build_context_bundle()` in `spectrum_systems/modules/runtime/context_selector.py`:
- consumes governed roadmap/review/eval/failure/build/handoff/PQX/risk inputs
- includes only same-scope and locality-relevant artifacts
- fails closed when required inputs are missing
- excludes stale context by policy
- keeps active-risk-linked artifacts even when stale
- replaces superseded artifacts with the latest valid representative

## Ranking model (deterministic)
Ranking uses only deterministic signal dimensions:
1. scope locality (same batch/slice/program)
2. touched-module overlap
3. risk severity linkage
4. review/eval relevance
5. recency
6. deterministic tiebreaker by artifact reference

No model-based ranking. No randomness.
Same inputs always produce the same ordering.

## Injection model
`build_context_injection_payload()` in `spectrum_systems/modules/runtime/context_injection.py` enforces:
- bounded context size (`max_refs`)
- explicit advisory-only contract
- explicit authority boundary statement
- source refs preserved for traceability
- replayability from governed artifacts only
- no hidden/implicit context

## Lifecycle model
Lifecycle behavior is explicit and deterministic:
- stale context expires by policy window
- active risk references persist until resolved
- superseded artifacts are replaced (latest valid only)
- closed failures are retained but deprioritized
- irrelevant history is not silently retained

## Process flow (updated)
artifacts
  ↓
context selection
  ↓
context ranking
  ↓
context injection
  ↓
Codex/PQX execution
  ↓
new artifacts

Context informs execution. Control remains authority.
