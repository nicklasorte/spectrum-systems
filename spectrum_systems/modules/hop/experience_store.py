from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from .validator import validate_artifact_shape


class HOPStoreError(RuntimeError):
    """Raised for append-only or artifact validation violations."""


class ExperienceStore:
    """Append-only, replay-friendly NDJSON artifact store."""

    def __init__(self, root: Path, schema_root: Path | None = None) -> None:
        self.root = Path(root)
        self.schema_root = schema_root
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root / "hop_experience.ndjson"
        self.log_path.touch(exist_ok=True)

    def append(self, artifact: dict[str, Any], schema_name: str) -> None:
        validate_artifact_shape(artifact, schema_name=schema_name, schema_root=self.schema_root)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"schema": schema_name, "artifact": artifact}, sort_keys=True) + "\n")

    def iter_records(
        self,
        *,
        schema: str | None = None,
        candidate_id: str | None = None,
        trace_id: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        since: str | None = None,
        until: str | None = None,
        artifact_type: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                if schema and row.get("schema") != schema:
                    continue
                artifact = row.get("artifact", {})
                if candidate_id and artifact.get("candidate_id") != candidate_id:
                    continue
                if trace_id and artifact.get("trace", {}).get("trace_id") != trace_id:
                    continue
                if artifact_type and artifact.get("artifact_type") != artifact_type:
                    continue
                created_at = artifact.get("created_at", "")
                if since and created_at < since:
                    continue
                if until and created_at > until:
                    continue
                score = artifact.get("score")
                if min_score is not None and (score is None or float(score) < float(min_score)):
                    continue
                if max_score is not None and (score is None or float(score) > float(max_score)):
                    continue
                yield row

    def get_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        return list(self.iter_records(candidate_id=candidate_id))
