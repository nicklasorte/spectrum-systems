"""REP: Replay support primitives — hashing, mismatch classification, coverage.

NX-07: This module extends the existing fail-closed replay engine with the
small support primitives needed to make replay verification a control input:

  - canonical input/output hashing
  - mismatch classification with reason codes
  - replay coverage summary across multiple records
  - human-readable debug message describing what changed

It does NOT execute replays; it operates on already-built replay records
or on raw input/output payloads. The canonical replay engine remains
``spectrum_systems.modules.runtime.replay_engine``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Mapping, Tuple


class ReplaySupportError(ValueError):
    """Raised when replay support primitives cannot be deterministically applied."""


CANONICAL_REASON_CODES = {
    "REPLAY_HASH_MATCH",
    "REPLAY_HASH_MISMATCH_INPUT",
    "REPLAY_HASH_MISMATCH_OUTPUT",
    "REPLAY_HASH_MISMATCH_BOTH",
    "REPLAY_MISSING_ORIGINAL_RECORD",
    "REPLAY_MISSING_INPUT_HASH",
    "REPLAY_MISSING_OUTPUT_HASH",
    "REPLAY_NON_REPLAYABLE_ARTIFACT",
    "REPLAY_INPUT_HASH_NOT_DETERMINISTIC",
}


def canonical_hash(payload: Any) -> str:
    """Return a deterministic SHA-256 of ``payload``.

    Lists, dicts, and primitive values are JSON-canonicalized with sorted keys
    before hashing. Strings are hashed as UTF-8. ``None`` is allowed and yields
    a stable ``"null"`` hash. Bytes are hashed directly.
    """
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(bytes(payload)).hexdigest()
    if isinstance(payload, str):
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_replay_record(
    *,
    replay_id: str,
    original_run_id: str,
    trace_id: str,
    input_payload: Any,
    output_payload: Any,
    artifact_type: str,
    replay_path: str = "support_replay",
) -> Dict[str, Any]:
    """Build a minimal replay record (fail-closed).

    The record is intentionally schema-light; downstream code can layer the
    canonical replay_result schema over it. Required fields are validated.
    """
    if not isinstance(replay_id, str) or not replay_id.strip():
        raise ReplaySupportError("replay_id must be a non-empty string")
    if not isinstance(original_run_id, str) or not original_run_id.strip():
        raise ReplaySupportError("original_run_id must be a non-empty string")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ReplaySupportError("trace_id must be a non-empty string")
    if not isinstance(artifact_type, str) or not artifact_type.strip():
        raise ReplaySupportError("artifact_type must be a non-empty string")

    return {
        "replay_id": replay_id,
        "original_run_id": original_run_id,
        "trace_id": trace_id,
        "artifact_type": artifact_type,
        "input_hash": canonical_hash(input_payload),
        "output_hash": canonical_hash(output_payload),
        "replay_path": replay_path,
    }


def classify_replay_mismatch(
    *,
    original: Mapping[str, Any] | None,
    replayed: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Classify a replay mismatch and return a control-shaped result.

    Returns
    -------
    {"reason_code": str, "consistency_status": "match"|"mismatch"|"indeterminate",
     "decision": "allow"|"freeze"|"block",
     "input_hash_match": bool|None,
     "output_hash_match": bool|None,
     "blocking_reasons": [str,...],
     "debug_message": str}
    """
    if original is None or not isinstance(original, Mapping):
        return {
            "reason_code": "REPLAY_MISSING_ORIGINAL_RECORD",
            "consistency_status": "indeterminate",
            "decision": "block",
            "input_hash_match": None,
            "output_hash_match": None,
            "blocking_reasons": ["original replay record missing"],
            "debug_message": "Replay comparison cannot proceed: the original execution record is missing.",
        }
    if replayed is None or not isinstance(replayed, Mapping):
        return {
            "reason_code": "REPLAY_MISSING_ORIGINAL_RECORD",
            "consistency_status": "indeterminate",
            "decision": "block",
            "input_hash_match": None,
            "output_hash_match": None,
            "blocking_reasons": ["replayed record missing"],
            "debug_message": "Replay comparison cannot proceed: the replayed record is missing.",
        }

    original_in = original.get("input_hash")
    replayed_in = replayed.get("input_hash")
    if not isinstance(original_in, str) or not original_in:
        return {
            "reason_code": "REPLAY_MISSING_INPUT_HASH",
            "consistency_status": "indeterminate",
            "decision": "block",
            "input_hash_match": None,
            "output_hash_match": None,
            "blocking_reasons": ["original record missing input_hash"],
            "debug_message": "Original replay record is missing an input_hash; replay cannot be verified.",
        }
    if not isinstance(replayed_in, str) or not replayed_in:
        return {
            "reason_code": "REPLAY_MISSING_INPUT_HASH",
            "consistency_status": "indeterminate",
            "decision": "block",
            "input_hash_match": None,
            "output_hash_match": None,
            "blocking_reasons": ["replayed record missing input_hash"],
            "debug_message": "Replayed record is missing an input_hash; replay cannot be verified.",
        }

    original_out = original.get("output_hash")
    replayed_out = replayed.get("output_hash")
    if not isinstance(original_out, str) or not original_out:
        return {
            "reason_code": "REPLAY_MISSING_OUTPUT_HASH",
            "consistency_status": "indeterminate",
            "decision": "block",
            "input_hash_match": original_in == replayed_in,
            "output_hash_match": None,
            "blocking_reasons": ["original record missing output_hash"],
            "debug_message": "Original replay record is missing an output_hash; replay cannot be verified.",
        }
    if not isinstance(replayed_out, str) or not replayed_out:
        return {
            "reason_code": "REPLAY_MISSING_OUTPUT_HASH",
            "consistency_status": "indeterminate",
            "decision": "block",
            "input_hash_match": original_in == replayed_in,
            "output_hash_match": None,
            "blocking_reasons": ["replayed record missing output_hash"],
            "debug_message": "Replayed record is missing an output_hash; replay cannot be verified.",
        }

    input_match = original_in == replayed_in
    output_match = original_out == replayed_out

    if input_match and output_match:
        return {
            "reason_code": "REPLAY_HASH_MATCH",
            "consistency_status": "match",
            "decision": "allow",
            "input_hash_match": True,
            "output_hash_match": True,
            "blocking_reasons": [],
            "debug_message": "Replay matched original input and output hashes.",
        }

    blocking: List[str] = []
    if not input_match:
        blocking.append(
            f"input hash drift: original={original_in[:12]}... replayed={replayed_in[:12]}..."
        )
    if not output_match:
        blocking.append(
            f"output hash drift: original={original_out[:12]}... replayed={replayed_out[:12]}..."
        )

    if not input_match and not output_match:
        reason = "REPLAY_HASH_MISMATCH_BOTH"
        debug = (
            "Both input and output hashes differ between original and replay; "
            "the executor non-determinism likely propagated through the slice."
        )
    elif not input_match:
        reason = "REPLAY_HASH_MISMATCH_INPUT"
        debug = (
            "The replay used a different input hash than the original; check "
            "context bundle / prompt admission for non-determinism."
        )
    else:
        reason = "REPLAY_HASH_MISMATCH_OUTPUT"
        debug = (
            "Inputs matched but the output hash diverged; the slice is not "
            "deterministic — block promotion until root cause is found."
        )

    return {
        "reason_code": reason,
        "consistency_status": "mismatch",
        "decision": "block",
        "input_hash_match": input_match,
        "output_hash_match": output_match,
        "blocking_reasons": blocking,
        "debug_message": debug,
    }


def build_replay_coverage_summary(
    records: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate replay records into a coverage summary.

    Returns
    -------
    {"total": int, "match": int, "mismatch": int, "indeterminate": int,
     "match_rate": float, "reason_codes": {code: count, ...},
     "status": "healthy"|"degraded"|"blocked"}
    """
    total = 0
    match = 0
    mismatch = 0
    indeterminate = 0
    reason_counts: Dict[str, int] = {}

    for record in records:
        total += 1
        if not isinstance(record, Mapping):
            indeterminate += 1
            reason_counts["REPLAY_NON_REPLAYABLE_ARTIFACT"] = (
                reason_counts.get("REPLAY_NON_REPLAYABLE_ARTIFACT", 0) + 1
            )
            continue
        status = str(record.get("consistency_status") or "").lower()
        reason_code = str(record.get("reason_code") or "")
        if reason_code:
            reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1
        if status == "match":
            match += 1
        elif status == "mismatch":
            mismatch += 1
        else:
            indeterminate += 1

    if total == 0:
        return {
            "total": 0,
            "match": 0,
            "mismatch": 0,
            "indeterminate": 0,
            "match_rate": 0.0,
            "reason_codes": {},
            "status": "blocked",
            "debug_message": "No replay records present — replay coverage is zero.",
        }

    match_rate = match / total
    if mismatch > 0:
        status = "blocked"
        debug = f"{mismatch}/{total} replay records mismatched; promotion blocked."
    elif indeterminate > 0:
        status = "degraded"
        debug = f"{indeterminate}/{total} replay records indeterminate; investigate."
    else:
        status = "healthy"
        debug = f"{match}/{total} replay records matched."

    return {
        "total": total,
        "match": match,
        "mismatch": mismatch,
        "indeterminate": indeterminate,
        "match_rate": match_rate,
        "reason_codes": reason_counts,
        "status": status,
        "debug_message": debug,
    }


def is_artifact_replayable(artifact: Mapping[str, Any]) -> Tuple[bool, str]:
    """Return ``(replayable, reason)`` for an artifact dict.

    Replayability requires:
      - ``artifact_type`` non-empty
      - either ``input_hash`` and ``output_hash`` already present, or
        ``trace_id`` + ``run_id`` from which a hash could be re-derived.
    """
    if not isinstance(artifact, Mapping):
        return False, "REPLAY_NON_REPLAYABLE_ARTIFACT: artifact is not a mapping"
    artifact_type = artifact.get("artifact_type")
    if not isinstance(artifact_type, str) or not artifact_type.strip():
        return False, "REPLAY_NON_REPLAYABLE_ARTIFACT: missing artifact_type"
    has_hashes = isinstance(artifact.get("input_hash"), str) and isinstance(
        artifact.get("output_hash"), str
    )
    has_lineage = bool(artifact.get("trace_id")) and bool(artifact.get("run_id"))
    if not has_hashes and not has_lineage:
        return False, (
            "REPLAY_NON_REPLAYABLE_ARTIFACT: artifact has neither input/output hashes "
            "nor trace_id+run_id lineage — it cannot be deterministically replayed"
        )
    return True, "REPLAY_HASH_MATCH" if has_hashes else "REPLAY_HASH_MATCH"


__all__ = [
    "CANONICAL_REASON_CODES",
    "ReplaySupportError",
    "build_replay_coverage_summary",
    "build_replay_record",
    "canonical_hash",
    "classify_replay_mismatch",
    "is_artifact_replayable",
]
