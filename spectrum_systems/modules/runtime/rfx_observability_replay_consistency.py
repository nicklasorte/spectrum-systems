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

    Accepts the primary ``trace_id``, an explicit ``trace_ids`` list, and:

      * ``execution_path_coverage.trace_ids`` list when coverage is a dict
        carrying that explicit field, OR
      * the dict keys of ``execution_path_coverage`` (multi-trace form
        ``{trace_id: [steps]}`` mirroring the dict form already accepted
        by LOOP-08 and ``_artifact_links_for_trace``), AND
      * the dict keys of ``artifact_linkage`` when it is a dict
        (multi-trace form ``{trace_id: [artifact_refs]}``).

    The coverage list itself is *not* treated as a trace-id source; it
    conventionally enumerates execution-path step labels (AEX, PQX, …),
    not trace identifiers.
    """
    ids: set[str] = set()
    primary = _coerce_str(obs.get("trace_id"))
    if primary is not None:
        ids.add(primary)
    coverage = obs.get("execution_path_coverage")
    if isinstance(coverage, dict):
        # Two mutually-exclusive dict shapes are accepted:
        #   1. metadata form: ``{"trace_ids": ["t1", ...], ...other metadata}``
        #      — only ``trace_ids[*]`` are trace identifiers; sibling keys
        #        (``segments``, etc.) are metadata buckets, not traces.
        #   2. multi-trace form: ``{trace_id: [steps], ...}`` — dict keys
        #      ARE the trace identifiers.
        # Disambiguate by checking whether ``trace_ids`` is present: when
        # it is, treat the dict as the metadata form and ignore other keys.
        if "trace_ids" in coverage:
            for v in coverage.get("trace_ids", []) or []:
                s = _coerce_str(v)
                if s is not None:
                    ids.add(s)
        else:
            for k in coverage.keys():
                s = _coerce_str(k)
                if s is not None:
                    ids.add(s)
    linkage = obs.get("artifact_linkage")
    if isinstance(linkage, dict):
        for k in linkage.keys():
            s = _coerce_str(k)
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
      * a dict keyed by trace_id whose value is a non-empty list OR a
        non-empty dict of artifact refs (mirroring the LOOP-08 invariant
        that accepts both shapes for per-trace buckets).

    A non-empty bucket of either shape is treated as "linkage present";
    only empty / missing buckets count as missing linkage. Returns the
    bucket flattened to a list so callers can use ``len(...)`` as a
    truthy presence check.
    """
    linkage = obs.get("artifact_linkage")
    if isinstance(linkage, dict):
        entries = linkage.get(trace_id)
        if isinstance(entries, list):
            # Drop blank/None entries — ``["", null]`` carries no usable
            # artifact reference and must not satisfy the linkage check.
            return [e for e in entries if not _is_empty_evidence(e)]
        if isinstance(entries, dict) and len(entries) > 0:
            # Non-empty dict bucket — keep only inner values that are
            # themselves non-empty evidence. ``{"lin": []}`` would otherwise
            # be treated as linked even though no actual artifact ref is
            # present, creating a fail-open path under
            # ``replay_results=[{"trace_id": "t1"}]``.
            non_empty = [v for v in entries.values() if not _is_empty_evidence(v)]
            return non_empty
        return []
    if isinstance(linkage, list):
        primary = _coerce_str(obs.get("trace_id"))
        if primary == trace_id:
            # Same blank/None filter applies to the flat-list form so the
            # two shapes agree on what counts as actual linkage evidence.
            return [e for e in linkage if not _is_empty_evidence(e)]
        return []
    return []


def _is_empty_evidence(value: Any) -> bool:
    """Return True for values that carry no actual evidence content."""
    if value is None:
        return True
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    if isinstance(value, str):
        return not value.strip()
    return False


def _replay_trace_id_aliases(record: dict[str, Any]) -> set[str]:
    """Return the full set of trace-id aliases declared on a replay row.

    Returns every non-empty value among ``trace_id`` / ``source_trace_id``
    / ``replay_trace_id`` so the consistency check can accept the row when
    any alias matches an OBS trace — preventing migration-era rows with a
    stale ``trace_id`` plus correct ``source_trace_id`` from being falsely
    flagged as inconsistent.
    """
    ids: set[str] = set()
    for key in ("trace_id", "source_trace_id", "replay_trace_id"):
        s = _coerce_str(record.get(key))
        if s is not None:
            ids.add(s)
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
      * any replay row carries no recognized trace identifier,
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

    # Container-level guard: only ``None`` and ``list`` are accepted.
    # A non-iterable / non-list payload (e.g. ``replay_results=1``) is a
    # fail-closed condition — surface it deterministically rather than
    # crashing the iteration with TypeError.
    if replay_results is not None and not isinstance(replay_results, list):
        reasons.append(
            "rfx_trace_replay_inconsistency: replay_results must be a list "
            f"or None, got {type(replay_results).__name__}"
        )
        replay_iter: list[Any] = []
    else:
        replay_iter = replay_results or []

    # Walk replays once: every row must carry at least one trace-id alias.
    # When multiple aliases are present (migration-era rows), any of them
    # may match an OBS trace — only fail closed if NONE matches.
    rep_trace_ids: set[str] = set()
    untraceable_count = 0
    for index, r in enumerate(replay_iter):
        if not isinstance(r, dict):
            untraceable_count += 1
            reasons.append(
                f"rfx_trace_replay_inconsistency: replay row index={index} "
                f"is not a dict — every replay record must reference a trace"
            )
            continue
        row_aliases = _replay_trace_id_aliases(r)
        if not row_aliases:
            untraceable_count += 1
            reasons.append(
                f"rfx_trace_replay_inconsistency: replay row index={index} "
                f"carries no trace_id/source_trace_id/replay_trace_id — "
                f"every replay record must reference an OBS trace"
            )
            continue
        matched = row_aliases & obs_trace_ids
        if matched:
            rep_trace_ids |= matched
        else:
            reasons.append(
                f"rfx_trace_replay_inconsistency: replay row index={index} "
                f"aliases {sorted(row_aliases)!r} not present in OBS coverage"
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
