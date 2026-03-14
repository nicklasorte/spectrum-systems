# External Storage Implementation Guide for Engines

Each downstream engine must keep production data off GitHub and operate against external storage.

## Required behaviors
- Accept explicit external input paths (CLI flags, config, or environment variables) instead of bundled inputs.
- Write all outputs, intermediates, and logs to approved local or network storage paths, not the repository.
- Emit an `external_artifact_manifest` entry for every material artifact with checksums and storage location.
- Support deterministic hashing (SHA-256) for all emitted files to enable traceability and reproducibility.
- Treat GitHub as configuration and contract source only; never attempt to read or write production artifacts from/to GitHub.

## Implementation tips
- Require callers to pass separate input/output roots so unit tests can substitute synthetic fixtures without touching production data.
- Fail fast if paths resolve to Git workspaces or HTTP(S) URLs; insist on local or mounted network paths.
- Keep manifests and provenance sidecars alongside artifacts in external storage for auditability.
- Provide dry-run or lint modes that validate manifests and path accessibility without copying data into Git.
