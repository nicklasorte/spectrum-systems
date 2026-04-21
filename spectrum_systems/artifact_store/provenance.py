"""PROV-DM compliant artifact lineage and provenance tracking."""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path


class ProvenanceRecord:
    """Immutable provenance record for an artifact."""

    def __init__(
        self,
        artifact_id: str,
        artifact_type: str,
        trace_id: str,
        created_by: str,
        upstream_artifacts: List[str],
    ):
        self.artifact_id = artifact_id
        self.artifact_type = artifact_type
        self.trace_id = trace_id
        self.created_by = created_by
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.upstream_artifacts = upstream_artifacts
        self.content_hash: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "trace_id": self.trace_id,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "upstream_artifacts": self.upstream_artifacts,
            "content_hash": self.content_hash,
        }


class ArtifactStore:
    """Artifact storage with fail-closed provenance validation."""

    # Artifact types that are allowed to have no upstream artifacts (entry points).
    _ENTRY_POINT_TYPES = {"transcript_artifact"}

    def __init__(self, base_path: str = "runs/artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._provenance_log: Dict[str, List[Dict]] = {}

    def store_artifact(self, artifact: Dict, provenance: ProvenanceRecord) -> str:
        """Store artifact with provenance validation. Fail-closed."""
        errors = []
        if not provenance.trace_id:
            errors.append("Missing trace_id")
        if not provenance.artifact_id:
            errors.append("Missing artifact_id")
        if (
            provenance.artifact_type not in self._ENTRY_POINT_TYPES
            and not provenance.upstream_artifacts
        ):
            errors.append(
                f"Missing upstream_artifacts for non-entry-point type"
                f" '{provenance.artifact_type}'"
            )
        if errors:
            raise ValueError(f"Provenance validation failed: {'; '.join(errors)}")

        content_hash = hashlib.sha256(
            json.dumps(artifact, sort_keys=True).encode()
        ).hexdigest()
        provenance.content_hash = content_hash

        trace_dir = self.base_path / provenance.trace_id
        trace_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = trace_dir / f"{provenance.artifact_id}.json"
        with open(artifact_path, "w") as fh:
            json.dump(artifact, fh, indent=2)

        log = self._provenance_log.setdefault(provenance.trace_id, [])
        log.append(provenance.to_dict())

        prov_path = trace_dir / "PROVENANCE.json"
        with open(prov_path, "w") as fh:
            json.dump(log, fh, indent=2)

        return str(artifact_path)

    def get_artifact_lineage(self, artifact_id: str, trace_id: str) -> Dict:
        """Retrieve provenance record for an artifact within a trace."""
        records = self._provenance_log.get(trace_id)
        if records is None:
            raise ValueError(f"No provenance log for trace '{trace_id}'")
        for record in records:
            if record["artifact_id"] == artifact_id:
                return record
        raise ValueError(f"Artifact '{artifact_id}' not found in trace '{trace_id}'")

    def verify_lineage_completeness(self, trace_id: str) -> Dict:
        """Audit lineage: all artifacts have upstream references."""
        records = self._provenance_log.get(trace_id, [])
        orphans = [
            r["artifact_id"]
            for r in records
            if r["artifact_type"] not in self._ENTRY_POINT_TYPES
            and not r.get("upstream_artifacts")
        ]
        missing_hashes = [r["artifact_id"] for r in records if not r.get("content_hash")]
        return {
            "trace_id": trace_id,
            "total_artifacts": len(records),
            "orphans": orphans,
            "missing_hashes": missing_hashes,
            "complete": len(orphans) == 0,
            "all_hashes_present": len(missing_hashes) == 0,
        }
