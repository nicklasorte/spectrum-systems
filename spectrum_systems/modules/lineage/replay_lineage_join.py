"""LIN/REP join contract — promotion-blocking causality verification.

NS-19..21: REP and LIN must cross-reference each other through stable IDs
so that certification can verify replay-lineage coherence. A missing or
broken join between a replay record and the lineage chain blocks
promotion / certification.

This module is a non-owning seam. It does not duplicate REP or LIN; it
verifies that a replay record and its lineage chain are mutually
referenceable using:

  - replay.trace_id == lineage_chain.trace_id
  - replay.original_run_id == lineage_chain.run_id
  - replay.replay_id linked from lineage_summary.replay_record_ids
  - lineage_chain.artifact_id is reachable from replay.target_artifact_id
  - parent-artifact chain hash continuity (when supplied)

The verifier returns canonical reason codes from a small, finite set so
downstream certification can fail closed with a stable canonical category.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional


CANONICAL_JOIN_REASON_CODES = {
    "JOIN_OK",
    "JOIN_REPLAY_MISSING",
    "JOIN_LINEAGE_MISSING",
    "JOIN_TRACE_ID_MISMATCH",
    "JOIN_RUN_ID_MISMATCH",
    "JOIN_REPLAY_NOT_LINKED_FROM_LINEAGE",
    "JOIN_LINEAGE_NOT_REFERENCED_FROM_REPLAY",
    "JOIN_ARTIFACT_HASH_DISCONTINUITY",
    "JOIN_PARENT_CHAIN_BREAK",
}


class ReplayLineageJoinError(ValueError):
    """Raised when replay/lineage join cannot be verified deterministically."""


def _ids_in(iterable: Any) -> List[str]:
    if not isinstance(iterable, list):
        return []
    return [str(x) for x in iterable if isinstance(x, (str, int))]


def verify_replay_lineage_join(
    *,
    replay_record: Optional[Mapping[str, Any]],
    lineage_summary: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Verify mutual reference between a replay record and a lineage summary.

    ``replay_record`` should expose:
      - replay_id, original_run_id, trace_id, target_artifact_id (or
        ``output_artifact_id``), optional ``output_hash``
      - optional ``referenced_lineage_summary_id``

    ``lineage_summary`` should expose:
      - summary_id, trace_id, run_id
      - artifact_ids: list of artifacts covered by lineage
      - replay_record_ids: list of replay records joined to this lineage
      - optional ``output_hash`` for the leaf artifact
      - optional ``parent_chain``: list of (artifact_id, parent_id, parent_hash)

    Returns:
      {"decision": "allow"|"block",
       "reason_code": canonical,
       "blocking_reasons": [str,...]}
    """
    if not isinstance(replay_record, Mapping):
        return {
            "decision": "block",
            "reason_code": "JOIN_REPLAY_MISSING",
            "blocking_reasons": ["replay record missing"],
        }
    if not isinstance(lineage_summary, Mapping):
        return {
            "decision": "block",
            "reason_code": "JOIN_LINEAGE_MISSING",
            "blocking_reasons": ["lineage summary missing"],
        }

    replay_id = str(replay_record.get("replay_id") or "")
    replay_trace_id = str(replay_record.get("trace_id") or "")
    replay_run_id = str(
        replay_record.get("original_run_id") or replay_record.get("run_id") or ""
    )
    replay_target_id = str(
        replay_record.get("target_artifact_id")
        or replay_record.get("output_artifact_id")
        or replay_record.get("artifact_id")
        or ""
    )
    replay_output_hash = str(replay_record.get("output_hash") or "")

    lineage_trace_id = str(lineage_summary.get("trace_id") or "")
    lineage_run_id = str(lineage_summary.get("run_id") or "")
    lineage_replay_ids = _ids_in(lineage_summary.get("replay_record_ids"))
    lineage_artifact_ids = _ids_in(lineage_summary.get("artifact_ids"))
    referenced_lineage_id = str(
        replay_record.get("referenced_lineage_summary_id") or ""
    )
    lineage_summary_id = str(lineage_summary.get("summary_id") or "")
    lineage_output_hash = str(lineage_summary.get("output_hash") or "")
    parent_chain = lineage_summary.get("parent_chain")

    blocking: List[str] = []
    reason_code = "JOIN_OK"

    def _maybe(name: str, why: str) -> None:
        nonlocal reason_code
        blocking.append(why)
        if reason_code == "JOIN_OK":
            reason_code = name

    if replay_trace_id and lineage_trace_id and replay_trace_id != lineage_trace_id:
        _maybe(
            "JOIN_TRACE_ID_MISMATCH",
            f"trace_id mismatch: replay={replay_trace_id!r} lineage={lineage_trace_id!r}",
        )
    if replay_run_id and lineage_run_id and replay_run_id != lineage_run_id:
        _maybe(
            "JOIN_RUN_ID_MISMATCH",
            f"run_id mismatch: replay={replay_run_id!r} lineage={lineage_run_id!r}",
        )

    # lineage must enumerate this replay record (forward link)
    if replay_id and replay_id not in lineage_replay_ids:
        _maybe(
            "JOIN_REPLAY_NOT_LINKED_FROM_LINEAGE",
            f"lineage_summary.replay_record_ids does not include replay {replay_id!r}",
        )
    # replay must reference this lineage summary (backward link)
    if lineage_summary_id and referenced_lineage_id != lineage_summary_id:
        _maybe(
            "JOIN_LINEAGE_NOT_REFERENCED_FROM_REPLAY",
            f"replay.referenced_lineage_summary_id != lineage.summary_id "
            f"({referenced_lineage_id!r} vs {lineage_summary_id!r})",
        )

    # Hash continuity when both sides supply hashes for the leaf artifact.
    if replay_output_hash and lineage_output_hash and replay_output_hash != lineage_output_hash:
        _maybe(
            "JOIN_ARTIFACT_HASH_DISCONTINUITY",
            f"output hash discontinuity: replay={replay_output_hash[:12]}... "
            f"lineage={lineage_output_hash[:12]}...",
        )

    # Replay target must be present in lineage artifact ids when both are provided.
    if replay_target_id and lineage_artifact_ids and replay_target_id not in lineage_artifact_ids:
        _maybe(
            "JOIN_PARENT_CHAIN_BREAK",
            f"replay target artifact {replay_target_id!r} absent from lineage chain",
        )

    # Parent chain integrity (optional). Each entry must reference a previous
    # parent_id; chain must not break in the middle.
    if isinstance(parent_chain, list) and parent_chain:
        seen: set[str] = set()
        for idx, entry in enumerate(parent_chain):
            if not isinstance(entry, Mapping):
                _maybe(
                    "JOIN_PARENT_CHAIN_BREAK",
                    f"parent_chain[{idx}] is not a mapping",
                )
                continue
            aid = str(entry.get("artifact_id") or "")
            pid = str(entry.get("parent_id") or "")
            if not aid:
                _maybe(
                    "JOIN_PARENT_CHAIN_BREAK",
                    f"parent_chain[{idx}] missing artifact_id",
                )
                continue
            if idx > 0 and pid and pid not in seen:
                _maybe(
                    "JOIN_PARENT_CHAIN_BREAK",
                    f"parent_chain[{idx}] parent_id {pid!r} not seen earlier in chain",
                )
            seen.add(aid)

    return {
        "decision": "allow" if not blocking else "block",
        "reason_code": "JOIN_OK" if not blocking else reason_code,
        "blocking_reasons": blocking,
    }


def build_replay_lineage_join_summary(
    *,
    summary_id: str,
    trace_id: str,
    run_id: str,
    replay_records: List[Mapping[str, Any]],
    artifact_ids: List[str],
    output_hash: str = "",
    parent_chain: Optional[List[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Helper that constructs a lineage_summary referenceable from replay
    records. ``replay_records`` are scanned for ``replay_id`` and the
    summary's ``replay_record_ids`` is populated."""
    if not isinstance(summary_id, str) or not summary_id.strip():
        raise ReplayLineageJoinError("summary_id must be a non-empty string")
    return {
        "summary_id": summary_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "replay_record_ids": [
            str(r.get("replay_id") or "") for r in replay_records if isinstance(r, Mapping)
        ],
        "artifact_ids": [str(a) for a in artifact_ids],
        "output_hash": output_hash,
        "parent_chain": list(parent_chain or []),
    }


__all__ = [
    "CANONICAL_JOIN_REASON_CODES",
    "ReplayLineageJoinError",
    "build_replay_lineage_join_summary",
    "verify_replay_lineage_join",
]
