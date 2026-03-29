# Identity Requirements Contract

## Required fields
All runtime-generated artifacts must include both:

- `run_id`: deterministic identifier for the execution run context that produced the artifact.
- `trace_id`: deterministic identifier for the trace context that links artifacts across the run lifecycle.

## Propagation rules
1. Artifact builders must inject missing IDs using `ensure_required_ids(...)` before any schema validation, artifact ID generation, or persistence.
2. Validation entry points must call `validate_required_ids(...)` and fail closed if either ID is absent.
3. Test helpers must delegate to runtime identity enforcement logic so tests and runtime share one source of truth.

## Fail-closed behavior
- Missing `run_id` or `trace_id` is a hard error at runtime.
- No artifact may be emitted, persisted, or considered valid without both IDs.
- Identity enforcement must not mutate caller-owned payloads in-place.
