"""
Artifact Store — spectrum_systems/modules/runtime/artifact_store.py

In-memory, schema-validated artifact store for the transcript-to-study pipeline.
All writes are fail-closed: missing required fields or schema violations raise
ArtifactStoreError before any state is mutated.

Architecture constraints:
- No artifact may be written without passing schema validation.
- No artifact may be written without trace_id, schema_ref, and provenance.
- Content hash is computed deterministically from artifact content (SHA-256).
- Store is append-only within a session; no overwrites.
- Artifacts are deep-copied at write and read time to enforce immutability.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

_SCHEMA_DIR = Path(__file__).parent.parent.parent.parent / "contracts" / "schemas" / "transcript_pipeline"

_REQUIRED_TOP_LEVEL = {"artifact_id", "schema_ref", "content_hash", "trace", "provenance"}
_REQUIRED_TRACE = {"trace_id", "span_id"}
_REQUIRED_PROVENANCE = {"produced_by", "input_artifact_ids"}


class ArtifactStoreError(RuntimeError):
    """Raised on any artifact store violation. Always fail-closed."""

    def __init__(self, message: str, reason_code: str, artifact_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.artifact_id = artifact_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "reason_code": self.reason_code,
            "artifact_id": self.artifact_id,
        }


def _load_schema(schema_ref: str) -> Dict[str, Any]:
    """Load a pipeline schema by its schema_ref string (e.g., 'transcript_pipeline/transcript_artifact')."""
    parts = schema_ref.split("/")
    if len(parts) != 2 or parts[0] != "transcript_pipeline":
        raise ArtifactStoreError(
            f"schema_ref must be 'transcript_pipeline/<name>', got: {schema_ref!r}",
            reason_code="INVALID_SCHEMA_REF",
        )
    schema_file = _SCHEMA_DIR / f"{parts[1]}.schema.json"
    if not schema_file.exists():
        raise ArtifactStoreError(
            f"Schema file not found for schema_ref={schema_ref!r}: {schema_file}",
            reason_code="SCHEMA_NOT_FOUND",
        )
    return json.loads(schema_file.read_text(encoding="utf-8"))


def compute_content_hash(artifact: Dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash of artifact content fields.

    Excludes 'content_hash' itself to avoid circular dependency.
    Returns the hash as 'sha256:<hex>' string.
    """
    hashable = {k: v for k, v in artifact.items() if k != "content_hash"}
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _enforce_required_envelope(artifact: Dict[str, Any]) -> None:
    missing = _REQUIRED_TOP_LEVEL - set(artifact.keys())
    if missing:
        raise ArtifactStoreError(
            f"Artifact missing required envelope fields: {sorted(missing)}",
            reason_code="MISSING_ENVELOPE_FIELDS",
            artifact_id=artifact.get("artifact_id"),
        )

    trace = artifact.get("trace")
    if not isinstance(trace, dict):
        raise ArtifactStoreError(
            "Artifact 'trace' must be an object",
            reason_code="INVALID_TRACE",
            artifact_id=artifact.get("artifact_id"),
        )
    missing_trace = _REQUIRED_TRACE - set(trace.keys())
    if missing_trace:
        raise ArtifactStoreError(
            f"Artifact trace missing required fields: {sorted(missing_trace)}",
            reason_code="MISSING_TRACE_FIELDS",
            artifact_id=artifact.get("artifact_id"),
        )

    provenance = artifact.get("provenance")
    if not isinstance(provenance, dict):
        raise ArtifactStoreError(
            "Artifact 'provenance' must be an object",
            reason_code="INVALID_PROVENANCE",
            artifact_id=artifact.get("artifact_id"),
        )
    missing_prov = _REQUIRED_PROVENANCE - set(provenance.keys())
    if missing_prov:
        raise ArtifactStoreError(
            f"Artifact provenance missing required fields: {sorted(missing_prov)}",
            reason_code="MISSING_PROVENANCE_FIELDS",
            artifact_id=artifact.get("artifact_id"),
        )


def _validate_schema(artifact: Dict[str, Any], schema: Dict[str, Any]) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(e.message for e in errors[:5])
        raise ArtifactStoreError(
            f"Schema validation failed: {details}",
            reason_code="SCHEMA_VALIDATION_FAILED",
            artifact_id=artifact.get("artifact_id"),
        )


class ArtifactStore:
    """In-memory, schema-enforced artifact store.

    All writes validate schema, trace, and provenance before accepting the artifact.
    Fail-closed: any violation raises ArtifactStoreError; no partial writes occur.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._type_index: Dict[str, List[str]] = {}

    def register_artifact(self, artifact: Dict[str, Any]) -> str:
        """Validate and store an artifact. Returns artifact_id on success.

        Raises ArtifactStoreError on any validation failure.
        """
        if not isinstance(artifact, dict):
            raise ArtifactStoreError(
                "Artifact must be a dict",
                reason_code="INVALID_ARTIFACT_TYPE",
            )

        _enforce_required_envelope(artifact)

        artifact_id: str = artifact["artifact_id"]
        schema_ref: str = artifact["schema_ref"]

        if artifact_id in self._store:
            raise ArtifactStoreError(
                f"Artifact already registered: {artifact_id}",
                reason_code="DUPLICATE_ARTIFACT_ID",
                artifact_id=artifact_id,
            )

        schema = _load_schema(schema_ref)
        _validate_schema(artifact, schema)

        expected_hash = compute_content_hash(artifact)
        provided_hash = artifact.get("content_hash", "")
        if provided_hash != expected_hash:
            raise ArtifactStoreError(
                f"content_hash mismatch: provided={provided_hash!r}, expected={expected_hash!r}",
                reason_code="CONTENT_HASH_MISMATCH",
                artifact_id=artifact_id,
            )

        artifact_type: str = artifact.get("artifact_type", "unknown")
        self._store[artifact_id] = copy.deepcopy(artifact)
        self._type_index.setdefault(artifact_type, []).append(artifact_id)

        return artifact_id

    def retrieve_artifact(self, artifact_id: str) -> Dict[str, Any]:
        """Retrieve a stored artifact by ID. Raises ArtifactStoreError if not found.

        Returns a deep copy to prevent mutation of the stored artifact.
        """
        if artifact_id not in self._store:
            raise ArtifactStoreError(
                f"Artifact not found: {artifact_id}",
                reason_code="ARTIFACT_NOT_FOUND",
                artifact_id=artifact_id,
            )
        return copy.deepcopy(self._store[artifact_id])

    def list_artifacts_by_type(self, artifact_type: str) -> List[Dict[str, Any]]:
        """Return all stored artifacts of a given type."""
        ids = self._type_index.get(artifact_type, [])
        return [self._store[aid] for aid in ids]

    def artifact_exists(self, artifact_id: str) -> bool:
        return artifact_id in self._store

    def artifact_count(self) -> int:
        return len(self._store)


__all__ = [
    "ArtifactStore",
    "ArtifactStoreError",
    "compute_content_hash",
]
