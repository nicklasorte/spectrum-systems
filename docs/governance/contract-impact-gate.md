# Contract Impact Gate

Schema changes are governed changes.

Before PQX execution proceeds for a slice that changes governed contracts, a `contract_impact_artifact` must be provided or generated. The analyzer classifies compatibility as `compatible`, `caution`, `breaking`, or `indeterminate`.

Execution is fail-closed:
- `breaking` or `indeterminate` blocks PQX.
- `blocking=true` blocks PQX.
- `safe_to_execute` must be `true` to proceed.

This gate complements tests. It does not replace contract tests, runtime tests, or end-to-end validation.

This gate also complements (does not replace) the execution-path gate:
- **G13 contract impact gate** protects contract/schema compatibility.
- **G14 execution change impact gate** protects runtime/control/review/certification path safety.

Where relevant, PQX requires both gates to pass before execution.
