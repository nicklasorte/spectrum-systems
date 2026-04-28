"""RFX institutional-memory layer — RFX-15.

Indexes failures, fixes, evals, trends, judgments, policies, calibration
records, and roadmap recommendations for retrieval and future learning.
The module is a non-owning phase-label support helper. Authority for the
underlying artifact types remains with the canonical owners recorded in
``docs/architecture/system_registry.md``; the index references them by
deterministic id.

Output:

  * ``rfx_memory_index_record``
  * ``rfx_memory_lookup_result``

Reason codes:

  * ``rfx_memory_source_missing``
  * ``rfx_memory_index_invalid``
  * ``rfx_memory_lookup_ambiguous``
  * ``rfx_memory_lineage_missing``
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class RFXMemoryIndexError(ValueError):
    """Raised when memory indexing or lookup fails closed."""


_SUPPORTED_ARTIFACT_TYPES: frozenset[str] = frozenset(
    {
        "failure_classification",
        "rfx_failure_derived_eval_case",
        "rfx_eval_handoff_record",
        "rfx_fix_integrity_proof_record",
        "rfx_trend_report",
        "rfx_hotspot_record",
        "rfx_judgment_candidate",
        "rfx_policy_candidate_handoff",
        "rfx_calibration_record",
        "rfx_roadmap_recommendation",
        "rfx_chaos_campaign_record",
        "rfx_cross_run_consistency_record",
        "rfx_error_budget_governance_record",
    }
)


def _stable_id(payload: Any, *, prefix: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _coerce_id(record: dict[str, Any]) -> str | None:
    for k in (
        "case_id",
        "report_id",
        "hotspot_id",
        "candidate_id",
        "handoff_id",
        "calibration_id",
        "recommendation_id",
        "campaign_id",
        "failure_id",
        "fix_id",
        "id",
    ):
        v = record.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _coerce_lineage_refs(record: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for k in (
        "source_failure_refs",
        "source_fix_refs",
        "source_eval_refs",
        "source_trend_refs",
        "source_hotspot_refs",
        "source_judgment_refs",
        "lineage_refs",
        "case_ids",
    ):
        v = record.get(k)
        if isinstance(v, list):
            for r in v:
                if isinstance(r, str) and r.strip():
                    out.append(r.strip())
        elif isinstance(v, str) and v.strip():
            out.append(v.strip())
    return sorted(set(out))


def _collect_reason_codes(record: dict[str, Any]) -> list[str]:
    codes: set[str] = set()
    for k in ("reason_code", "reason_codes", "reason_codes_emitted", "expected_reason_codes"):
        v = record.get(k)
        if isinstance(v, str) and v.strip():
            codes.add(v.strip())
        elif isinstance(v, list):
            for c in v:
                if isinstance(c, str) and c.strip():
                    codes.add(c.strip())
        elif isinstance(v, dict):
            for c in v.keys():
                if isinstance(c, str) and c.strip():
                    codes.add(c.strip())
    return sorted(codes)


def build_rfx_memory_index_record(
    *,
    artifacts: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build an indexable, non-owning ``rfx_memory_index_record``.

    Fails closed when:

      * artifacts list is absent
      * an artifact lacks ``artifact_type``
      * an artifact's type is not in the supported set
      * an artifact has no derivable id
      * an artifact has no lineage references (source refs)
    """
    if not isinstance(artifacts, list) or not artifacts:
        raise RFXMemoryIndexError(
            "rfx_memory_source_missing: artifacts list absent or empty"
        )

    entries: list[dict[str, Any]] = []
    by_type: dict[str, list[str]] = {}
    by_reason: dict[str, list[str]] = {}

    for idx, art in enumerate(artifacts):
        if not isinstance(art, dict):
            raise RFXMemoryIndexError(
                f"rfx_memory_index_invalid: artifacts[{idx}] not a mapping"
            )
        atype = art.get("artifact_type")
        if not isinstance(atype, str) or not atype.strip():
            raise RFXMemoryIndexError(
                f"rfx_memory_index_invalid: artifacts[{idx}] missing artifact_type"
            )
        if atype not in _SUPPORTED_ARTIFACT_TYPES:
            raise RFXMemoryIndexError(
                f"rfx_memory_index_invalid: artifacts[{idx}] artifact_type={atype!r} "
                f"not in supported set"
            )
        aid = _coerce_id(art)
        if aid is None:
            raise RFXMemoryIndexError(
                f"rfx_memory_index_invalid: artifacts[{idx}] has no derivable id"
            )
        lineage = _coerce_lineage_refs(art)
        if not lineage and atype != "rfx_chaos_campaign_record":
            # Chaos campaign aggregates case-level results that already carry
            # their own provenance; any other artifact must declare lineage.
            raise RFXMemoryIndexError(
                f"rfx_memory_lineage_missing: artifacts[{idx}] of type {atype!r} "
                f"has no source/lineage refs"
            )
        reasons = _collect_reason_codes(art)

        entry = {
            "entry_id": _stable_id({"id": aid, "type": atype}, prefix="rfx-mem"),
            "artifact_type": atype,
            "artifact_id": aid,
            "lineage_refs": lineage,
            "reason_codes": reasons,
        }
        entries.append(entry)
        by_type.setdefault(atype, []).append(aid)
        for r in reasons:
            by_reason.setdefault(r, []).append(aid)

    return {
        "artifact_type": "rfx_memory_index_record",
        "schema_version": "1.0.0",
        "entry_count": len(entries),
        "entries": entries,
        "by_artifact_type": {k: sorted(v) for k, v in sorted(by_type.items())},
        "by_reason_code": {k: sorted(v) for k, v in sorted(by_reason.items())},
    }


def lookup_rfx_memory(
    *,
    index: dict[str, Any] | None,
    reason_code: str | None = None,
    artifact_type: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic lookup result against an index record.

    Either ``reason_code`` or ``artifact_type`` is required. When both are
    supplied, the intersection is returned. Ambiguous queries (no filter
    given) raise ``rfx_memory_lookup_ambiguous``.
    """
    if not isinstance(index, dict) or index.get("artifact_type") != "rfx_memory_index_record":
        raise RFXMemoryIndexError(
            "rfx_memory_index_invalid: index argument is not an rfx_memory_index_record"
        )
    if not reason_code and not artifact_type:
        raise RFXMemoryIndexError(
            "rfx_memory_lookup_ambiguous: at least one of reason_code or artifact_type required"
        )
    by_reason = index.get("by_reason_code", {}) if isinstance(index.get("by_reason_code"), dict) else {}
    by_type = index.get("by_artifact_type", {}) if isinstance(index.get("by_artifact_type"), dict) else {}
    matched_ids: set[str]
    if reason_code and artifact_type:
        matched_ids = set(by_reason.get(reason_code, [])) & set(by_type.get(artifact_type, []))
    elif reason_code:
        matched_ids = set(by_reason.get(reason_code, []))
    else:
        matched_ids = set(by_type.get(artifact_type, []))  # type: ignore[arg-type]

    return {
        "artifact_type": "rfx_memory_lookup_result",
        "schema_version": "1.0.0",
        "reason_code_filter": reason_code,
        "artifact_type_filter": artifact_type,
        "match_count": len(matched_ids),
        "matched_artifact_ids": sorted(matched_ids),
    }


__all__ = [
    "RFXMemoryIndexError",
    "build_rfx_memory_index_record",
    "lookup_rfx_memory",
]
