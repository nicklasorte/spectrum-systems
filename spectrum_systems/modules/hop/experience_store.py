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
    trace_diffs/<artifact_id>.json
    index.jsonl
    index.jsonl.lock

The store is fail-closed:

- payloads are validated against the HOP schema before write;
- existing files are NEVER overwritten — a duplicate write triggers a structured
  ``HopStoreError`` and emits a ``duplicate_artifact`` failure hypothesis at the
  caller level (the store itself only refuses);
- the index is append-only: each successful write appends one JSON line under
  an exclusive ``fcntl.flock`` so concurrent processes never interleave bytes;
- artifact files are written via temp-file + ``os.replace`` so partial writes
  never become readable.

Queries stream the index line by line (``iter_index``) — full history is never
loaded into memory.
"""

from __future__ import annotations

import errno
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from spectrum_systems.modules.hop.artifacts import compute_content_hash
from spectrum_systems.modules.hop.schemas import (
    HopSchemaError,
    validate_hop_artifact,
)

try:  # pragma: no cover - posix only path tested in CI
    import fcntl  # type: ignore[import]

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - non-posix fallback
    fcntl = None  # type: ignore[assignment]
    _HAS_FCNTL = False


class HopStoreError(Exception):
    """Raised on store-admission failures."""


_DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0
_LOCK_POLL_INTERVAL_SECONDS = 0.05


_TYPE_TO_DIR: dict[str, str] = {
    "hop_harness_candidate": "candidates",
    "hop_harness_run": "runs",
    "hop_harness_score": "scores",
    "hop_harness_trace": "traces",
    "hop_harness_failure_hypothesis": "failures",
    "hop_harness_frontier": "frontiers",
    "hop_harness_eval_case": "eval_cases",
    "hop_harness_faq_output": "faq_outputs",
    "hop_harness_trace_diff": "trace_diffs",
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
    "hop_harness_trace_diff": (
        "diff_id",
        "baseline_candidate_id",
        "candidate_id",
        "baseline_run_id",
        "candidate_run_id",
    ),
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
    """File-system backed append-only store with concurrency-safe writes.

    BATCH-2 hardens BATCH-1's append-only invariants for multi-process
    evaluators:

    * the index lock (``index.jsonl.lock``) is acquired exclusively for the
      whole admit/write/index sequence so two processes can never interleave
      bytes in ``index.jsonl`` or race the duplicate-artifact check;
    * artifact bytes are written to a same-directory tempfile and then
      atomically promoted via ``os.replace`` so a partial / crashed write is
      never observable as a half-formed JSON file.
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        lock_timeout_seconds: float = _DEFAULT_LOCK_TIMEOUT_SECONDS,
    ):
        self._root = Path(root).resolve()
        self._index_path = self._root / "index.jsonl"
        self._lock_path = self._root / "index.jsonl.lock"
        self._lock_timeout = float(lock_timeout_seconds)
        self._ensure_layout()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def index_path(self) -> Path:
        return self._index_path

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    def _ensure_layout(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        for sub in _TYPE_TO_DIR.values():
            (self._root / sub).mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists():
            self._index_path.touch()
        if not self._lock_path.exists():
            self._lock_path.touch()

    def _path_for(self, artifact_type: str, artifact_id: str) -> Path:
        if artifact_type not in _TYPE_TO_DIR:
            raise HopStoreError(f"hop_store_unsupported_type:{artifact_type}")
        return self._root / _TYPE_TO_DIR[artifact_type] / f"{artifact_id}.json"

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        """Acquire an exclusive flock on the dedicated lock file.

        Times out (fail-closed) after ``self._lock_timeout`` seconds. Falls
        back to a polled ``O_EXCL`` create-and-delete sentinel on platforms
        without ``fcntl`` so the contract still holds (Windows CI).
        """
        deadline = time.monotonic() + self._lock_timeout
        if _HAS_FCNTL:
            handle = self._lock_path.open("a+b")
            try:
                while True:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise HopStoreError(
                                "hop_store_lock_timeout:index.jsonl.lock"
                            )
                        time.sleep(_LOCK_POLL_INTERVAL_SECONDS)
                yield
            finally:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()
        else:  # pragma: no cover - exercised on non-posix only
            sentinel = self._root / "index.jsonl.lock.sentinel"
            while True:
                try:
                    fd = os.open(
                        str(sentinel),
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                        0o644,
                    )
                    os.close(fd)
                    break
                except OSError as exc:
                    if exc.errno != errno.EEXIST:
                        raise
                    if time.monotonic() >= deadline:
                        raise HopStoreError(
                            "hop_store_lock_timeout:index.jsonl.lock"
                        )
                    time.sleep(_LOCK_POLL_INTERVAL_SECONDS)
            try:
                yield
            finally:
                try:
                    sentinel.unlink()
                except FileNotFoundError:
                    pass

    @staticmethod
    def _atomic_write_json(target: Path, payload: Mapping[str, Any]) -> None:
        """Write ``payload`` to ``target`` atomically via tempfile + rename.

        The tempfile is created in the same directory so ``os.replace`` is a
        same-volume rename. ``fsync`` of the file (and parent dir on POSIX)
        ensures the new bytes are durable before the rename publishes them.
        """
        directory = target.parent
        directory.mkdir(parents=True, exist_ok=True)
        tmp_name = f".{target.name}.tmp.{os.getpid()}.{int(time.time_ns())}"
        tmp_path = directory / tmp_name
        try:
            with tmp_path.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:  # pragma: no cover - filesystem without fsync
                    pass
            os.replace(tmp_path, target)
            try:  # pragma: no cover - posix-only durability guarantee
                dir_fd = os.open(str(directory), os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, AttributeError):
                pass
        except Exception:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            raise

    def _atomic_append_index(self, record: Mapping[str, Any]) -> None:
        """Append a single JSON line under the held exclusive lock."""
        line = json.dumps(record, sort_keys=True) + "\n"
        with self._index_path.open("ab") as handle:
            handle.write(line.encode("utf-8"))
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:  # pragma: no cover - filesystem without fsync
                pass

    def write_artifact(self, payload: Mapping[str, Any]) -> Path:
        """Validate and persist a single artifact. Refuses to overwrite.

        The full admit/write/index sequence is performed under an exclusive
        ``flock`` on ``index.jsonl.lock`` so concurrent writers cannot
        interleave bytes in ``index.jsonl`` nor race the duplicate-artifact
        check.
        """
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

        with self._exclusive_lock():
            if target.exists():
                existing = json.loads(target.read_text(encoding="utf-8"))
                if existing == payload:
                    # Idempotent re-write of identical content is a no-op.
                    return target
                raise HopStoreError(
                    f"hop_store_duplicate_artifact:{artifact_type}:{artifact_id}"
                )

            self._atomic_write_json(target, payload)
            index_record = self._build_index_record(payload, target)
            self._atomic_append_index(index_record)

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
