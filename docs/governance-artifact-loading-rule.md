# Governance Artifact Loading Rule

Governance artifacts must always be loaded from local filesystem paths that are part of the `spectrum-systems` control plane. Engines and tools should mount or vendor the required governance tree and resolve artifacts directly from disk.

## Scope
- schemas
- contracts
- registry files
- standards manifests

## Prohibited access patterns
Do **not** fetch governance artifacts over the network via:
- HTTP endpoints
- GitHub APIs
- `curl`
- `requests`
- `raw.githubusercontent.com` or similar CDN URLs

## Why this rule exists
1. **Reproducibility**: local artifacts keep runs pinned to the exact contract and schema versions used during development and review.
2. **CI reliability**: offline or rate-limited CI environments still validate against the authoritative artifacts.
3. **Sandbox compatibility**: airgapped and restricted environments can run engines without additional permissions.
4. **Supply chain safety**: local copies prevent unreviewed remote updates from altering governed contracts at runtime.
5. **Deterministic builds**: no network variability is introduced into validation, packaging, or evaluation steps.

**Rule**: No engine may fetch governance artifacts over the network. Always load them from the local governance checkout and fail fast with a clear message when the expected local paths are missing.
