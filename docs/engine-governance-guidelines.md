# Engine Governance Guidelines

## Schema Loading
- Load governance artifacts (schemas, contracts, registry files, standards manifests) from a provided local schema root rather than downloading them during runtime.
- Example pattern: `load_schema("run_manifest", schema_root)` where `schema_root` points to the locally mounted `spectrum-systems` governance tree.
- Prefer shared local utilities for schema resolution and validation; do not shell out to network tools or HTTP clients for governance artifacts.
- Fail fast with a clear error when the schema root is missing or incomplete so orchestration can surface the issue immediately.
- Keep the schema root version pinned to the governance version declared in the engine’s metadata to preserve reproducibility.
