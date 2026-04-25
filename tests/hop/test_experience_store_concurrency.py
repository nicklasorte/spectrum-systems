"""Experience store concurrency tests — file locking + atomic writes.

These tests exercise the BATCH-2 hardening: the store's exclusive
``index.jsonl.lock`` flock + tempfile/``os.replace`` atomic writes.

Subprocess-based fan-out is used (not threads) because Python's GIL
masks the real concurrency we want to validate. Each worker imports
the store fresh and writes a unique candidate; the post-condition is
that ``index.jsonl`` contains exactly ``N`` well-formed lines and
every candidate file is readable + hash-consistent.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from spectrum_systems.modules.hop.experience_store import (
    ExperienceStore,
    HopStoreError,
)
from tests.hop.conftest import make_baseline_candidate


REPO_ROOT = Path(__file__).resolve().parents[2]


def _writer_program(store_root: str, suffix: str) -> str:
    return textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {str(REPO_ROOT)!r})
        from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
        from spectrum_systems.modules.hop.experience_store import ExperienceStore

        store = ExperienceStore({store_root!r})
        payload = {{
            "artifact_type": "hop_harness_candidate",
            "schema_ref": "hop/harness_candidate.schema.json",
            "schema_version": "1.0.0",
            "trace": make_trace(primary="t"),
            "candidate_id": "concurrent_{suffix}",
            "harness_type": "transcript_to_faq",
            "code_module": "spectrum_systems.modules.hop.baseline_harness",
            "code_entrypoint": "run",
            "code_source": "def run(t): return {{'a': '{suffix}'}}\\n",
            "declared_methods": ["run"],
            "parent_candidate_id": None,
            "tags": ["concurrent"],
            "created_at": "2026-04-25T00:00:00.000000Z",
        }}
        finalize_artifact(payload, id_prefix="hop_candidate_")
        store.write_artifact(payload)
        print("ok", payload["artifact_id"])
        """
    )


def test_parallel_writes_serialize_under_lock(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    ExperienceStore(store_root)
    procs: list[subprocess.Popen[str]] = []
    n = 8
    for i in range(n):
        procs.append(
            subprocess.Popen(
                [sys.executable, "-c", _writer_program(str(store_root), f"w{i:02d}")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    for p in procs:
        out, err = p.communicate(timeout=30)
        assert p.returncode == 0, err
        assert out.startswith("ok ")

    store = ExperienceStore(store_root)
    candidates = list(store.list_candidates())
    assert len(candidates) == n
    # No interleaved bytes: every line is valid JSON.
    raw_lines = store.index_path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == n
    for line in raw_lines:
        json.loads(line)


def test_atomic_write_leaves_no_temp_files_on_success(tmp_path: Path) -> None:
    store = ExperienceStore(tmp_path / "store")
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    leftover = list((store.root / "candidates").glob(".*.tmp.*"))
    assert leftover == []


def test_lock_file_is_created_on_init(tmp_path: Path) -> None:
    store = ExperienceStore(tmp_path / "store")
    assert store.lock_path.exists()


def test_lock_timeout_fails_closed(tmp_path: Path) -> None:
    """A held lock causes secondary writers to fail-closed.

    We hold the flock manually in the parent process, then attempt a
    write with a near-zero timeout. The expected behavior is a
    ``HopStoreError`` whose message includes ``lock_timeout``.
    """
    store_root = tmp_path / "store"
    store = ExperienceStore(store_root, lock_timeout_seconds=0.2)
    candidate = make_baseline_candidate()

    try:
        import fcntl
    except ImportError:
        pytest.skip("fcntl unavailable on this platform")

    with store.lock_path.open("a+b") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        try:
            with pytest.raises(HopStoreError, match="lock_timeout"):
                store.write_artifact(candidate)
        finally:
            fcntl.flock(held.fileno(), fcntl.LOCK_UN)


def test_index_iteration_skips_lock_file(tmp_path: Path) -> None:
    store = ExperienceStore(tmp_path / "store")
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    # iter_index reads only index.jsonl, so the lock file should not affect it.
    records = list(store.iter_index())
    assert len(records) == 1


def test_concurrent_duplicate_writes_are_idempotent(tmp_path: Path) -> None:
    store = ExperienceStore(tmp_path / "store")
    candidate = make_baseline_candidate()
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    f"""
                    import sys, json
                    sys.path.insert(0, {str(REPO_ROOT)!r})
                    from spectrum_systems.modules.hop.experience_store import ExperienceStore
                    payload = json.loads(open({str(candidate_path)!r}).read())
                    ExperienceStore({str(tmp_path / 'store')!r}).write_artifact(payload)
                    print("ok")
                    """
                ),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    for p in procs:
        out, err = p.communicate(timeout=30)
        assert p.returncode == 0, err
    candidates = list(store.list_candidates())
    assert len(candidates) == 1
