# External Artifact Manifest Contract

The `external_artifact_manifest` contract records where production artifacts live outside GitHub and captures checksum, lineage, and storage requirements. It enforces the GitHub control-plane / external data-plane boundary defined in `docs/data-boundary-governance.md`.

## Purpose
- Keep operational artifacts (reports, working papers, transcripts, evidence bundles, logs) off GitHub while preserving traceability.
- Provide deterministic SHA-256 checksums and revision tracking for artifacts stored on local or network paths.
- Standardize how engines declare inputs/outputs and their storage locations.

## Required fields
- `artifact_type` — always `external_artifact_manifest`.
- `artifact_id` — stable identifier for this manifest (e.g., `XAM-STUDY-042-OUTPUT-001`).
- `artifact_version` — semantic version of the manifest record.
- `schema_version`, `standards_version` — schema and standards release numbers.
- `record_id`, `run_id` — provenance identifiers for the creation event.
- `created_at`, `created_by` — timestamp and actor producing the manifest.
- `source_repo`, `source_repo_version` — repo and commit/tag that generated the artifact.
- `study_id` — study or program identifier the artifact belongs to.
- `source_engine` — engine or workflow that produced the artifact.
- `revision` — revision number or tag for the artifact content.
- `logical_role` — role of the artifact (e.g., `input`, `intermediate`, `output`, `report`, `evidence`, `supporting`).
- `storage_kind` — storage class (e.g., `local`, `nfs`, `smb`); GitHub is never allowed here.
- `local_path` — absolute path to the artifact on local or mounted storage.
- `sha256` — checksum of the artifact contents.
- `parent_artifact_id` — link to the upstream artifact or manifest this derives from (nullable).
- `status` — lifecycle status (`draft`, `active`, `superseded`, `quarantined`).
- `tags` — labels for quick grouping/search.

## Usage rules
- Paths must be absolute local or network locations; do not record GitHub URLs or repository-relative paths.
- Engines must emit a manifest entry for every material artifact produced or consumed.
- Manifests stay with artifacts in external storage; Git commits only reference them, not the artifacts themselves.
- Synthetic fixtures in `examples/`, `contracts/examples/`, or test fixtures may use the manifest for demonstration but must remain redacted/tiny.
