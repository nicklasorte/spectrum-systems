# G17 Manifest Completeness Gate

## Purpose
The manifest completeness gate enforces strict structural integrity for `contracts/standards-manifest.json` before PQX slice execution and before pull-request validation flows.

This gate is fail-closed: if a contract entry is incomplete, null-valued, or contains undefined keys, execution is blocked.

## Required contract fields
Each entry under `contracts` must contain exactly these keys:

- `artifact_type` (string)
- `artifact_class` (string, non-null)
- `schema_path` (string)
- `example_path` (string)
- `intended_consumers` (non-empty list)

`artifact_class` must be one of:

- `control`
- `evaluation`
- `governance`
- `execution`
- `monitoring`

## Strictness and fail-closed behavior
Validation fails when any of the following are true:

- A required key is missing.
- A required key value is null.
- A required key value has the wrong type.
- `artifact_class` is outside the allowed enum.
- `intended_consumers` is empty.
- Any extra undefined key exists in a contract entry.

When any failure is detected:

- `scripts/validate_manifest.py` exits with status `1`.
- `run_pqx_slice` returns blocked status with `block_type=MANIFEST_COMPLETENESS_BLOCKED`.

## Failure examples
Example invalid entries:

```json
{
  "artifact_type": "pqx_slice_execution_record",
  "schema_path": "contracts/schemas/pqx_slice_execution_record.schema.json",
  "example_path": "contracts/examples/pqx_slice_execution_record.json",
  "intended_consumers": ["spectrum-systems"]
}
```

Reason: missing required `artifact_class`.

```json
{
  "artifact_type": "pqx_slice_execution_record",
  "artifact_class": "coordination",
  "schema_path": "contracts/schemas/pqx_slice_execution_record.schema.json",
  "example_path": "contracts/examples/pqx_slice_execution_record.json",
  "intended_consumers": ["spectrum-systems"],
  "status": "stable"
}
```

Reasons: invalid `artifact_class` enum value and extra key `status`.

## CI failure prevention impact
By rejecting malformed manifest contract definitions at the earliest boundary:

- PRs with incomplete contract metadata are blocked before merge.
- PQX execution cannot proceed with structurally ambiguous standards state.
- Downstream CI validators receive only structurally complete manifest entries, reducing late pipeline failures and contract drift ambiguity.
