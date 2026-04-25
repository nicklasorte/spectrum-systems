"""Append-only experience store for the Harness Optimization Pipeline.

Layout under ``<root>``::

    candidates/<artifact_id>.json
    runs/<artifact_id>.json
    scores/<artifact_id>.json
    traces/<artifact_id>.json
    failures/<artifact_id>.json
    frontiers/<artifact_id>.json
    eval_cases/<artifact_id>.json
    faq_outputs/<artifact_id>.json
    index.jsonl

The store is fail-closed:

- payloads are validated against the HOP schema before write;
- existing files are NEVER overwritten — a duplicate write triggers a structured
  ``HopStoreError`` and emits a ``duplicate_artifact`` failure hypothesis at the
  caller level (the store itself only refuses);
- the index is append-only: each successful write appends one JSON line.

Queries stream the index line by line (``iter_index``) — full history is never
loaded into memory.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from spectrum_systems.modules.hop.artifacts import compute_content_hash
from spectrum_systems.modules.hop.schemas import (
    HopSchemaError,
    validate_hop_artifact,
)


class HopStoreError(Exception):
    """Raised on store-admission failures."""


_TYPE_TO_DIR: dict[str, str] = {
    "hop_harness_candidate": "candidates",
    "hop_harness_run": "runs",
    "hop_harness_score": "scores",
    "hop_harness_trace": "traces",
    "hop_harness_failure_hypothesis": "failures",
    "hop_harness_frontier": "frontiers",
    "hop_harness_eval_case": "eval_cases",
    "hop_harness_faq_output": "faq_outputs",
}

_INDEXED_FIELDS: dict[str, tuple[str, ...]] = {
    "hop_harness_candidate": ("candidate_id", "harness_type"),
    "hop_harness_run": ("run_id", "candidate_id", "eval_set_id", "status"),
    "hop_harness_score": ("run_id", "candidate_id", "score"),
    "hop_harness_trace": ("run_id", "candidate_id", "eval_case_id", "complete"),
    "hop_harness_failure_hypothesis": (
        "hypothesis_id",
        "candidate_id",
        "run_id",
        "stage",
        "failure_class",
        "severity",
        "blocks_promotion",
    ),
    "hop_harness_frontier": ("frontier_id",),
    "hop_harness_eval_case": ("eval_case_id", "category"),
    "hop_harness_faq_output": ("transcript_id", "candidate_id"),
}


@dataclass(frozen=True)
class IndexRecord:
    timestamp: str
    artifact_type: str
    artifact_id: str
    relative_path: str
    fields: Mapping[str, Any]


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class ExperienceStore:
    """File-system backed append-only store."""

    def __init__(self, root: str | os.PathLike[str]):
        self._root = Path(root).resolve()
        self._index_path = self._root / "index.jsonl"
        self._ensure_layout()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def index_path(self) -> Path:
        return self._index_path

    def _ensure_layout(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        for sub in _TYPE_TO_DIR.values():
            (self._root / sub).mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists():
            self._index_path.touch()

    def _path_for(self, artifact_type: str, artifact_id: str) -> Path:
        if artifact_type not in _TYPE_TO_DIR:
            raise HopStoreError(f"hop_store_unsupported_type:{artifact_type}")
        return self._root / _TYPE_TO_DIR[artifact_type] / f"{artifact_id}.json"

    def write_artifact(self, payload: Mapping[str, Any]) -> Path:
        """Validate and persist a single artifact. Refuses to overwrite."""
        if not isinstance(payload, dict):
            raise HopStoreError("hop_store_invalid_payload:not_object")

        artifact_type = payload.get("artifact_type")
        if not isinstance(artifact_type, str) or artifact_type not in _TYPE_TO_DIR:
            raise HopStoreError(f"hop_store_invalid_payload:artifact_type:{artifact_type}")

        try:
            validate_hop_artifact(payload, artifact_type)
        except HopSchemaError as exc:
            raise HopStoreError(f"hop_store_schema_violation:{exc}") from exc

        recorded_hash = payload.get("content_hash")
        recomputed_hash = compute_content_hash(payload)
        if recorded_hash != recomputed_hash:
            raise HopStoreError(
                f"hop_store_content_hash_mismatch:{artifact_type}:"
                f"recorded={recorded_hash}:recomputed={recomputed_hash}"
            )

        artifact_id = payload["artifact_id"]
        target = self._path_for(artifact_type, artifact_id)

        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing == payload:
                # Idempotent re-write of identical content is a no-op.
                return target
            raise HopStoreError(
                f"hop_store_duplicate_artifact:{artifact_type}:{artifact_id}"
            )

        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        index_record = self._build_index_record(payload, target)
        with self._index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(index_record, sort_keys=True) + "\n")

        return target

    def _build_index_record(self, payload: Mapping[str, Any], target: Path) -> dict[str, Any]:
        artifact_type = payload["artifact_type"]
        fields = {key: payload.get(key) for key in _INDEXED_FIELDS.get(artifact_type, ())}
        return {
            "timestamp": _utcnow_iso(),
            "artifact_type": artifact_type,
            "artifact_id": payload["artifact_id"],
            "relative_path": str(target.relative_to(self._root)),
            "content_hash": payload.get("content_hash"),
            "fields": fields,
        }

    def read_artifact(self, artifact_type: str, artifact_id: str) -> dict[str, Any]:
        target = self._path_for(artifact_type, artifact_id)
        if not target.is_file():
            raise HopStoreError(f"hop_store_missing_artifact:{artifact_type}:{artifact_id}")
        payload = json.loads(target.read_text(encoding="utf-8"))
        try:
            validate_hop_artifact(payload, artifact_type)
        except HopSchemaError as exc:
            raise HopStoreError(f"hop_store_corrupted_artifact:{exc}") from exc
        recorded_hash = payload.get("content_hash")
        recomputed_hash = compute_content_hash(payload)
        if recorded_hash != recomputed_hash:
            raise HopStoreError(
                f"hop_store_corrupted_artifact:hash_mismatch:{artifact_type}:{artifact_id}"
            )
        return payload

    def iter_index(
        self,
        *,
        artifact_type: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream index entries from disk. Never loads the file into memory."""
        if not self._index_path.exists():
            return
        with self._index_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise HopStoreError(f"hop_store_corrupted_index:{exc}") from exc
                if artifact_type is not None and record.get("artifact_type") != artifact_type:
                    continue
                if predicate is not None and not predicate(record):
                    continue
                yield record

    def count(self, *, artifact_type: str | None = None) -> int:
        return sum(1 for _ in self.iter_index(artifact_type=artifact_type))

    def list_candidates(self) -> Iterator[dict[str, Any]]:
        return self.iter_index(artifact_type="hop_harness_candidate")

    def list_runs(self, *, candidate_id: str | None = None) -> Iterator[dict[str, Any]]:
        def _pred(rec: dict[str, Any]) -> bool:
            if candidate_id is None:
                return True
            return rec.get("fields", {}).get("candidate_id") == candidate_id

        return self.iter_index(artifact_type="hop_harness_run", predicate=_pred)

    def list_scores(
        self,
        *,
        candidate_id: str | None = None,
        min_score: float | None = None,
    ) -> Iterator[dict[str, Any]]:
        def _pred(rec: dict[str, Any]) -> bool:
            fields = rec.get("fields", {})
            if candidate_id is not None and fields.get("candidate_id") != candidate_id:
                return False
            if min_score is not None:
                score = fields.get("score")
                if score is None or score < min_score:
                    return False
            return True

        return self.iter_index(artifact_type="hop_harness_score", predicate=_pred)

    def list_failures(
        self,
        *,
        candidate_id: str | None = None,
        run_id: str | None = None,
        severity: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        def _pred(rec: dict[str, Any]) -> bool:
            fields = rec.get("fields", {})
            if candidate_id is not None and fields.get("candidate_id") != candidate_id:
                return False
            if run_id is not None and fields.get("run_id") != run_id:
                return False
            if severity is not None and fields.get("severity") != severity:
                return False
            return True

        return self.iter_index(artifact_type="hop_harness_failure_hypothesis", predicate=_pred)

    def list_traces(
        self,
        *,
        run_id: str | None = None,
        candidate_id: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        def _pred(rec: dict[str, Any]) -> bool:
            fields = rec.get("fields", {})
            if run_id is not None and fields.get("run_id") != run_id:
                return False
            if candidate_id is not None and fields.get("candidate_id") != candidate_id:
                return False
            return True

        return self.iter_index(artifact_type="hop_harness_trace", predicate=_pred)
