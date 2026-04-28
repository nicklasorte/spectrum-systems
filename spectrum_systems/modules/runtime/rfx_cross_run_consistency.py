"""RFX cross-run consistency detector — RFX-10.

Detects inconsistent outcomes for equivalent inputs across runs. The module
is a non-owning phase-label support helper. Closure decisions, certification
results, and policy lifecycle ownership remain with their canonical owners
recorded in ``docs/architecture/system_registry.md``.

Output:

  * ``rfx_cross_run_consistency_record``

Reason codes:

  * ``rfx_cross_run_inconsistency``
  * ``rfx_decision_volatility``
  * ``rfx_policy_version_unexplained``
  * ``rfx_replay_cross_run_mismatch``
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class RFXCrossRunConsistencyError(ValueError):
    """Raised when a cross-run consistency check fails closed."""


# Material keys participate in the input-equivalence fingerprint. Anything
# not on this list is considered non-material metadata (timestamps, tags,
# trace ids, run-local annotations) and cannot mask a true inconsistency.
_MATERIAL_INPUT_KEYS: frozenset[str] = frozenset(
    {
        "evidence",
        "inputs",
        "evl",
        "tpa",
        "cde",
        "sel",
        "lin",
        "rep",
        "obs",
        "slo",
        "pra",
        "pol",
        "policy_id",
        "policy_version",
        "schema_version",
    }
)


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, tuple):
        return [_canonical(v) for v in value]
    return value


def _input_fingerprint(run: dict[str, Any]) -> str:
    """Deterministic fingerprint over only the material input keys."""
    inputs = run.get("inputs")
    if isinstance(inputs, dict):
        material = {k: v for k, v in inputs.items() if k in _MATERIAL_INPUT_KEYS}
    else:
        material = {k: v for k, v in run.items() if k in _MATERIAL_INPUT_KEYS}
    canonical = json.dumps(_canonical(material), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _coerce_str(record: dict[str, Any] | None, *keys: str) -> str | None:
    if not isinstance(record, dict):
        return None
    for k in keys:
        v = record.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def assert_rfx_cross_run_consistency(
    *,
    runs: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Assert cross-run consistency for runs sharing equivalent inputs.

    A "run" is a mapping with at least:

      * ``run_id``: stable identifier
      * ``inputs``: material inputs (or top-level material keys)
      * Optional ``cde``, ``gov``, ``replay``, ``policy_version`` records

    Two runs with the same input fingerprint must agree on:

      * CDE readiness
      * GOV certification result
      * Replay match flag
      * Policy version (or differences must be carried through ``policy_version``)

    Returns an ``rfx_cross_run_consistency_record`` artifact when consistent.
    Raises :class:`RFXCrossRunConsistencyError` aggregating all reasons
    otherwise.
    """
    if not isinstance(runs, list) or len(runs) < 2:
        raise RFXCrossRunConsistencyError(
            "rfx_cross_run_inconsistency: at least two runs are required for a cross-run check"
        )

    by_fingerprint: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        if not isinstance(r, dict):
            continue
        fp = _input_fingerprint(r)
        by_fingerprint.setdefault(fp, []).append(r)

    reasons: list[str] = []
    cluster_summaries: list[dict[str, Any]] = []

    for fp, cluster in by_fingerprint.items():
        if len(cluster) < 2:
            continue

        cde_states = {_coerce_str(r.get("cde"), "status") for r in cluster}
        cde_states.discard(None)
        gov_states = {_coerce_str(r.get("gov"), "status", "certification_result") for r in cluster}
        gov_states.discard(None)
        replay_states = set()
        for r in cluster:
            rep = r.get("replay") if isinstance(r.get("replay"), dict) else r.get("rep")
            if isinstance(rep, dict):
                m = rep.get("match")
                if isinstance(m, bool):
                    replay_states.add(m)
        policy_versions = {_coerce_str(r, "policy_version") for r in cluster}
        policy_versions.discard(None)

        run_ids = [r.get("run_id") for r in cluster]

        if len(cde_states) > 1:
            reasons.append(
                f"rfx_decision_volatility: equivalent inputs produced differing CDE statuses {sorted(s for s in cde_states if s)} "
                f"across runs {run_ids}"
            )
        if len(gov_states) > 1:
            reasons.append(
                f"rfx_cross_run_inconsistency: equivalent inputs produced differing GOV results {sorted(s for s in gov_states if s)} "
                f"across runs {run_ids}"
            )
        if len(replay_states) > 1:
            reasons.append(
                f"rfx_replay_cross_run_mismatch: replay match flag differs across equivalent runs {run_ids}"
            )
        # Policy version must explain any non-replay/non-decision difference.
        # When fingerprints already include policy_version, divergence here is
        # only possible when other material keys collide across mismatched
        # policy versions. We emit a separate reason so downstream callers
        # can surface unexplained policy drift even if other axes agree.
        if len(policy_versions) > 1 and (len(cde_states) <= 1 and len(gov_states) <= 1):
            reasons.append(
                f"rfx_policy_version_unexplained: equivalent runs report multiple policy versions "
                f"{sorted(v for v in policy_versions if v)} but no decision/certification difference "
                f"that justifies the version split"
            )

        cluster_summaries.append(
            {
                "fingerprint": fp,
                "run_ids": run_ids,
                "cde_states": sorted(s for s in cde_states if s),
                "gov_states": sorted(s for s in gov_states if s),
                "replay_states": sorted(replay_states),
                "policy_versions": sorted(v for v in policy_versions if v),
            }
        )

    if reasons:
        raise RFXCrossRunConsistencyError("; ".join(reasons))

    return {
        "artifact_type": "rfx_cross_run_consistency_record",
        "schema_version": "1.0.0",
        "run_count": len(runs),
        "cluster_count": len([c for c in by_fingerprint.values() if len(c) >= 2]),
        "clusters": cluster_summaries,
        "result": "consistent",
    }


__all__ = [
    "RFXCrossRunConsistencyError",
    "assert_rfx_cross_run_consistency",
]
