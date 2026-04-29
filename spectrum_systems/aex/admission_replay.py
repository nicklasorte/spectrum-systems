"""AEX deterministic admission replay.

REP owns replay authority. AEX participates by exposing a deterministic
replay path for its admission outcomes. Given a fixture (a stored
``codex_build_request`` payload), AEX must produce the same admission
output every time. This module computes deterministic input/output
hashes, runs the admission engine, and emits an
``admission_replay_record`` (validated against
``schemas/aex/aex_admission_replay_record.schema.json``).

This module produces a replay observation; it does not own replay
authority and does not write to the canonical replay store.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from spectrum_systems.aex.engine import admit_codex_request
from spectrum_systems.aex.models import AdmissionResult


REPO_ROOT = Path(__file__).resolve().parents[2]
REPLAY_SCHEMA_PATH = REPO_ROOT / "schemas" / "aex" / "aex_admission_replay_record.schema.json"
DEFAULT_REPLAY_COMMAND = "python scripts/replay_aex_admission.py --fixture {fixture_path}"


class AEXReplayError(ValueError):
    """Raised when an AEX replay fails fail-closed."""


def _utc(now: datetime | None = None) -> str:
    return (now or datetime.now(tz=timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash16(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _canonical_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_fixture(fixture_path: Path) -> Mapping[str, Any]:
    if not fixture_path.is_file():
        raise AEXReplayError(f"replay fixture not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def replay_admission(fixture: Mapping[str, Any]) -> AdmissionResult:
    """Re-run AEX admission on a fixture. Pure function over the engine."""
    return admit_codex_request(fixture)


def _result_signature(result: AdmissionResult) -> dict[str, Any]:
    """Strip non-deterministic fields (e.g. server-generated timestamps in
    rejection records) to expose only fields that must be stable across
    replays.
    """
    nr = result.normalized_execution_request
    bar = result.build_admission_record
    rej = result.admission_rejection_record

    def _strip(rec: Mapping[str, Any] | None, drop_keys: tuple[str, ...]) -> dict[str, Any] | None:
        if rec is None:
            return None
        return {k: v for k, v in rec.items() if k not in drop_keys}

    drop = ("authenticity",)
    rej_drop = ("created_at",)
    return {
        "normalized_execution_request": _strip(nr, drop),
        "build_admission_record": _strip(bar, drop),
        "admission_rejection_record": _strip(rej, rej_drop),
    }


def build_admission_replay_record(
    *,
    fixture_path: Path,
    fixture: Mapping[str, Any],
    result: AdmissionResult,
    replay_command: str | None = None,
    produced_by: str = "AEXAdmissionReplay",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a schema-valid admission_replay_record."""
    request_id = str(fixture.get("request_id") or "unknown")
    trace_id = str(fixture.get("trace_id") or "unknown")
    run_id = f"run-{_hash16([request_id, trace_id, 'replay'])}"

    input_hash = "sha256:" + _canonical_hash(dict(fixture))
    output_signature = _result_signature(result)
    output_hash = "sha256:" + _canonical_hash(output_signature)

    replay_command = replay_command or DEFAULT_REPLAY_COMMAND.format(fixture_path=str(fixture_path))
    record = {
        "artifact_type": "admission_replay_record",
        "schema_version": "1.0.0",
        "replay_id": f"arr-{_hash16([request_id, trace_id, 'replay_id'])}",
        "request_id": request_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "fixture_path": str(fixture_path),
        "replay_command": replay_command,
        "input_hash": input_hash,
        "output_hash": output_hash,
        "replay_status": "pass",
        "deterministic": True,
        "produced_by": produced_by,
        "producer_authority": "AEX",
        "replay_owner_ref": "REP",
        "created_at": created_at or _utc(),
    }
    schema = json.loads(REPLAY_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(record)
    return record


def replay_and_verify(fixture_path: Path, replay_command: str | None = None) -> dict[str, Any]:
    """Replay the admission twice and verify deterministic input/output hashes.

    Fails closed (raises) if the two runs disagree.
    """
    fixture = load_fixture(fixture_path)
    first = replay_admission(fixture)
    second = replay_admission(fixture)

    sig_first = _canonical_hash(_result_signature(first))
    sig_second = _canonical_hash(_result_signature(second))
    if sig_first != sig_second:
        raise AEXReplayError(
            f"AEX replay non-deterministic for fixture {fixture_path}: "
            f"signatures {sig_first[:8]}…/{sig_second[:8]}… differ"
        )

    return build_admission_replay_record(
        fixture_path=fixture_path,
        fixture=fixture,
        result=first,
        replay_command=replay_command,
    )


__all__ = [
    "AEXReplayError",
    "DEFAULT_REPLAY_COMMAND",
    "build_admission_replay_record",
    "load_fixture",
    "replay_admission",
    "replay_and_verify",
]
