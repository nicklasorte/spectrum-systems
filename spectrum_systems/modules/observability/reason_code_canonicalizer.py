"""OBS: Reason-code canonicalization layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ALIAS_PATH = REPO_ROOT / "contracts" / "governance" / "reason_code_aliases.json"

CANONICAL_CATEGORIES = (
    "SCHEMA_VIOLATION",
    "MISSING_ARTIFACT",
    "EVAL_FAILURE",
    "TRACE_GAP",
    "POLICY_MISMATCH",
    "AUTHORITY_SHAPE_VIOLATION",
    "REPLAY_MISMATCH",
    "LINEAGE_GAP",
    "CONTEXT_ADMISSION_FAILURE",
    "SLO_BUDGET_FAILURE",
    "CERTIFICATION_GAP",
    "CONTROL_CHAIN_VIOLATION",
)

_PREFIX_TO_CATEGORY = {
    "OBS_": "MISSING_ARTIFACT",
    "REPLAY_": "REPLAY_MISMATCH",
    "LINEAGE_": "LINEAGE_GAP",
    "CTX_": "CONTEXT_ADMISSION_FAILURE",
    "SLO_": "SLO_BUDGET_FAILURE",
    "CERT_": "CERTIFICATION_GAP",
    "CONTROL_CHAIN_": "CONTROL_CHAIN_VIOLATION",
    "AUTHORITY_": "AUTHORITY_SHAPE_VIOLATION",
    "TIER_": "POLICY_MISMATCH",
    "PROOF_": "CERTIFICATION_GAP",
}

_PREFIX_TO_SUBSYSTEM = {
    "OBS_": "OBS",
    "REPLAY_": "REP",
    "LINEAGE_": "LIN",
    "CTX_": "CTX",
    "SLO_": "SLO",
    "CERT_": "GOV",
    "CONTROL_CHAIN_": "CDE",
    "AUTHORITY_": "GOV",
    "TIER_": "OBS",
}


class ReasonCodeError(ValueError):
    pass


def _load_alias_map(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or DEFAULT_ALIAS_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("artifact_type") != "reason_code_alias_map":
        raise ReasonCodeError("alias file artifact_type mismatch")
    return data


_alias_cache: Optional[Dict[str, Any]] = None


def _alias_table(reload: bool = False) -> Dict[str, Any]:
    global _alias_cache
    if reload or _alias_cache is None:
        _alias_cache = _load_alias_map()
    return _alias_cache


def _infer_subsystem(upper_code: str) -> Optional[str]:
    for prefix, subsystem in _PREFIX_TO_SUBSYSTEM.items():
        if upper_code.startswith(prefix):
            return subsystem
    return None


def canonicalize_reason_code(raw_code: str, *, detail_fields: Optional[Mapping[str, Any]] = None, alias_table: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    if not isinstance(raw_code, str):
        raise ReasonCodeError("raw_code must be a string")
    raw_norm = raw_code.strip()
    table_data = dict(alias_table) if alias_table is not None else _alias_table()
    aliases = {str(k).lower(): str(v).upper() for k, v in (table_data.get("aliases") or {}).items()}
    canonical_set = set(table_data.get("canonical_categories") or CANONICAL_CATEGORIES)
    lifecycle = table_data.get("lifecycle") or {}
    deprecated = set((lifecycle.get("deprecated") or {}).keys())
    forbidden = set((lifecycle.get("forbidden") or {}).keys())

    if not raw_norm:
        return {"canonical_category": "UNKNOWN", "detail_code": "", "source_subsystem": None, "details": dict(detail_fields or {}), "lifecycle_status": "unknown"}

    upper = raw_norm.upper()
    lower = raw_norm.lower()
    lifecycle_status = "active"
    if lower in forbidden:
        lifecycle_status = "forbidden"
    elif lower in deprecated:
        lifecycle_status = "deprecated"

    if upper in canonical_set:
        return {
            "canonical_category": upper,
            "detail_code": lower,
            "source_subsystem": None,
            "details": dict(detail_fields or {}),
            "lifecycle_status": lifecycle_status,
        }

    if lower in aliases:
        canonical = aliases[lower]
        return {
            "canonical_category": canonical if canonical in canonical_set else "UNKNOWN",
            "detail_code": lower,
            "source_subsystem": _infer_subsystem(upper),
            "details": dict(detail_fields or {}),
            "lifecycle_status": lifecycle_status,
        }

    for prefix, category in _PREFIX_TO_CATEGORY.items():
        if upper.startswith(prefix):
            return {
                "canonical_category": category,
                "detail_code": lower,
                "source_subsystem": _PREFIX_TO_SUBSYSTEM.get(prefix),
                "details": dict(detail_fields or {}),
                "lifecycle_status": lifecycle_status,
            }

    return {
        "canonical_category": "UNKNOWN",
        "detail_code": lower,
        "source_subsystem": None,
        "details": dict(detail_fields or {}),
        "lifecycle_status": lifecycle_status,
    }


def assert_canonical_or_alias(raw_code: str) -> None:
    if not isinstance(raw_code, str) or not raw_code.strip():
        raise ReasonCodeError("blocking reason code must be a non-empty string")

    table_data = _alias_table()
    aliases = {str(k).lower() for k in (table_data.get("aliases") or {}).keys()}
    canonical_set = set(table_data.get("canonical_categories") or CANONICAL_CATEGORIES)
    lifecycle = table_data.get("lifecycle") or {}
    forbidden = set((lifecycle.get("forbidden") or {}).keys())
    high_level = {str(c).lower() for c in (table_data.get("high_level_blocking_codes_requiring_canonical_mapping") or [])}

    upper = raw_code.strip().upper()
    lower = raw_code.strip().lower()

    if lower in forbidden:
        raise ReasonCodeError(f"reason code {raw_code!r} is forbidden by lifecycle policy")
    if upper in canonical_set:
        return
    if lower in aliases:
        return
    if lower in high_level:
        raise ReasonCodeError(f"high-level blocking reason {raw_code!r} must map to a canonical category")
    for prefix in _PREFIX_TO_CATEGORY:
        if upper.startswith(prefix):
            return
    raise ReasonCodeError(f"reason code {raw_code!r} is neither canonical nor a known alias")


def categorize_many(codes: Mapping[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for code in codes:
        out[str(code)] = canonicalize_reason_code(str(code))["canonical_category"]
    return out


__all__ = [
    "CANONICAL_CATEGORIES",
    "ReasonCodeError",
    "assert_canonical_or_alias",
    "canonicalize_reason_code",
    "categorize_many",
]
