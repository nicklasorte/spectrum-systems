# Trace State Isolation Invariant

Validation and chaos tooling must isolate trace state and must never clear or mutate shared global trace state.

## Invariant
- Runtime validation and chaos checks must not mutate unrelated traces in the default global trace store.
- Any isolated or test-only execution must use an injected trace store.
- Process-global trace resets are forbidden in runtime validation paths; only targeted test setup/teardown may clear stores.

## Store usage guidance
- **Default store (`store=None`)**
  - Use for normal runtime execution paths where trace state is intentionally process-global.
  - Use when modules are participating in the same runtime trace context.
- **Injected store (`store=create_trace_store()`)**
  - Use for chaos runs, validation harnesses, and bounded isolation tests.
  - Thread `store` through downstream helpers (`start_span`, `record_event`, `end_span`, `attach_artifact`, `get_trace`, and context validation helpers) to prevent hidden fallback to the global store.

## Anti-patterns to avoid
- Starting a trace in an injected store and then calling downstream trace helpers without passing `store`.
- Clearing the global trace store from validation/chaos execution code paths.
- Assuming isolated traces should appear in `get_all_trace_ids()` without passing the injected store.
