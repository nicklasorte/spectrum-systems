"""RFX OBS + REP consistency guard — Part 5 of the RFX reliability layer.

Cross-validates that observability traces and replay records line up.
Reliability-grade reproducibility requires:

  * Every replay record references a trace that OBS recorded.
  * Every OBS-recorded trace maps to a known artifact set.
  * Missing mapping in either direction → block.

Reason codes:

  * ``rfx_trace_replay_inconsistency`` — replay refers to a trace OBS does not
    cover, or vice versa
  * ``rfx_missing_trace_linkage``      — a trace has no artifact linkage at all

This guard is a non-owning phase-label support helper. Canonical authority
for OBS and REP is recorded in ``docs/architecture/system_registry.md``.
"""

from __future__ import annotations

from typing import Any


class RFXObservabilityReplayConsistencyError(ValueError):
    """Raised when LOOP-07/08 OBS+REP cross-check fails closed."""


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _trace_ids_from_obs(obs: dict[str, Any]) -> set[str]:
    """Collect declared trace ids from an OBS record.

    Accepts the primary ``trace_id``, an explicit ``trace_ids`` list, and a
    nested ``execution_path_coverage.trace_ids`` list (when coverage is a
    dict). The coverage list itself is *not* treated as a trace-id source;
    it conventionally enumerates execution-path step labels (AEX, PQX, …),
    not trace identifiers.
    """
    ids: set[str] = set()
    primary = _coerce_str(obs.get("trace_id"))
    if primary is not None:
        ids.add(primary)
    coverage = obs.get("execution_path_coverage")
    if isinstance(coverage, dict):
        for v in coverage.get("trace_ids", []) or []:
            s = _coerce_str(v)
            if s is not None:
                ids.add(s)
    for v in obs.get("trace_ids", []) or []:
        s = _coerce_str(v)
        if s is not None:
            ids.add(s)
    return ids


def _artifact_links_for_trace(
    obs: dict[str, Any], trace_id: str
) -> list[Any]:
    """Return the artifact-linkage entries OBS records for ``trace_id``.

    Accepts either:
      * a flat list (treated as belonging to the primary trace_id), or
      * a dict keyed by trace_id mapping to a list of artifact refs.
    """
    linkage = obs.get("artifact_linkage")
    if isinstance(linkage, dict):
        entries = linkage.get(trace_id)
        if isinstance(entries, list):
            return list(entries)
        return []
    if isinstance(linkage, list):
        primary = _coerce_str(obs.get("trace_id"))
        if primary == trace_id:
            return list(linkage)
        return []
    return []


def _trace_ids_from_replays(replay_results: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for r in replay_results or []:
        if not isinstance(r, dict):
            continue
        for key in ("trace_id", "source_trace_id", "replay_trace_id"):
            s = _coerce_str(r.get(key))
            if s is not None:
                ids.add(s)
                break
    return ids


def assert_rfx_observability_replay_consistency(
    *,
    obs: dict[str, Any] | None,
    replay_results: list[dict[str, Any]] | None,
) -> None:
    """Assert OBS-trace ↔ REP cross-consistency.

    Fails closed with a deterministic reason code when:
      * OBS is missing,
      * any trace recorded in OBS lacks artifact linkage,
      * any replay refers to a trace not present in OBS,
      * any OBS trace has no corresponding replay (drift indicator).
    """
    reasons: list[str] = []

    if not isinstance(obs, dict) or not obs:
        raise RFXObservabilityReplayConsistencyError(
            "rfx_missing_trace_linkage: OBS telemetry record absent — "
            "OBS+REP consistency cannot be evaluated"
        )

    obs_trace_ids = _trace_ids_from_obs(obs)
    if not obs_trace_ids:
        reasons.append(
            "rfx_missing_trace_linkage: OBS record carries no trace_id — "
            "replay cannot be cross-checked"
        )

    # Linkage: every OBS trace must map to at least one artifact ref.
    for tid in sorted(obs_trace_ids):
        links = _artifact_links_for_trace(obs, tid)
        if not links:
            reasons.append(
                f"rfx_missing_trace_linkage: OBS trace_id={tid!r} has no "
                f"artifact linkage entries"
            )

    rep_trace_ids = _trace_ids_from_replays(replay_results or [])

    # Replays must have matching OBS trace coverage.
    for tid in sorted(rep_trace_ids):
        if tid not in obs_trace_ids:
            reasons.append(
                f"rfx_trace_replay_inconsistency: replay references trace_id="
                f"{tid!r} not present in OBS coverage"
            )

    # OBS traces must have at least one replay record (no orphan traces).
    for tid in sorted(obs_trace_ids):
        if tid not in rep_trace_ids:
            reasons.append(
                f"rfx_trace_replay_inconsistency: OBS trace_id={tid!r} has "
                f"no replay record — replay/observability coverage drift"
            )

    if reasons:
        raise RFXObservabilityReplayConsistencyError("; ".join(reasons))


__all__ = [
    "RFXObservabilityReplayConsistencyError",
    "assert_rfx_observability_replay_consistency",
]
