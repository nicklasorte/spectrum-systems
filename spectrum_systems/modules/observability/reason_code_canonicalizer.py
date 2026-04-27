"""OBS: Reason-code canonicalization layer.

NS-04..06: A small, deterministic mapping layer that takes a raw failure
reason code from any subsystem (eval, replay, lineage, context, control,
certification, observability, SLO) and returns:

  * a canonical category from a finite set
  * the original detail code (preserved)
  * source subsystem hint (best-effort)

The mapping table is canonical at
``contracts/governance/reason_code_aliases.json``. Unknown codes are NOT
silently dropped; they are returned with category ``UNKNOWN`` so callers can
fail closed.

Guardrail: ``assert_canonical_or_alias(code)`` raises ``ReasonCodeError`` for
high-level blocking strings (e.g., ``"blocked"``, ``"freeze"``) that are not
mapped to a canonical category. New blocking reason codes must be either
canonical or mapped to an alias before they ship.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ALIAS_PATH = (
    REPO_ROOT / "contracts" / "governance" / "reason_code_aliases.json"
)


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

# Subsystem hint prefixes -> canonical category default. Used only when
# alias lookup misses; we never overwrite an explicit alias.
_PREFIX_TO_CATEGORY = {
    "OBS_": "MISSING_ARTIFACT",
    "REPLAY_": "REPLAY_MISMATCH",
    "LINEAGE_": "LINEAGE_GAP",
    "CTX_": "CONTEXT_ADMISSION_FAILURE",
    "SLO_": "SLO_BUDGET_FAILURE",
    "CERT_": "CERTIFICATION_GAP",
    "CONTROL_CHAIN_": "CONTROL_CHAIN_VIOLATION",
    "AUTHORITY_": "AUTHORITY_SHAPE_VIOLATION",
}

# Subsystem hints from the same prefix. Best-effort.
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
    """Raised when a reason code cannot be mapped to a canonical category."""


def _load_alias_map(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or DEFAULT_ALIAS_PATH
    if not p.exists():
        raise ReasonCodeError(f"reason code alias file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReasonCodeError(f"reason code alias file invalid JSON: {exc}") from exc
    if data.get("artifact_type") != "reason_code_alias_map":
        raise ReasonCodeError("alias file artifact_type mismatch")
    return data


_alias_cache: Optional[Dict[str, Any]] = None


def _alias_table(reload: bool = False) -> Dict[str, Any]:
    global _alias_cache
    if reload or _alias_cache is None:
        _alias_cache = _load_alias_map()
    return _alias_cache


def canonicalize_reason_code(
    raw_code: str,
    *,
    detail_fields: Optional[Mapping[str, Any]] = None,
    alias_table: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Map a raw reason code to a canonical category.

    Returns:
      {"canonical_category": str (one of CANONICAL_CATEGORIES) or "UNKNOWN",
       "detail_code": str (preserved input, normalized to lowercase),
       "source_subsystem": str | None,
       "details": dict (preserved detail_fields)}
    """
    if not isinstance(raw_code, str):
        raise ReasonCodeError("raw_code must be a string")
    raw_norm = raw_code.strip()
    if not raw_norm:
        return {
            "canonical_category": "UNKNOWN",
            "detail_code": "",
            "source_subsystem": None,
            "details": dict(detail_fields or {}),
        }

    table_data = dict(alias_table) if alias_table is not None else _alias_table()
    aliases = {
        str(k).lower(): str(v).upper()
        for k, v in (table_data.get("aliases") or {}).items()
    }
    canonical_set = set(table_data.get("canonical_categories") or CANONICAL_CATEGORIES)

    upper = raw_norm.upper()
    lower = raw_norm.lower()

    # 1. Already canonical
    if upper in canonical_set:
        return {
            "canonical_category": upper,
            "detail_code": lower,
            "source_subsystem": None,
            "details": dict(detail_fields or {}),
        }

    # 2. Alias hit
    if lower in aliases:
        canonical = aliases[lower]
        return {
            "canonical_category": canonical if canonical in canonical_set else "UNKNOWN",
            "detail_code": lower,
            "source_subsystem": _infer_subsystem(upper),
            "details": dict(detail_fields or {}),
        }

    # 3. Subsystem prefix heuristic — only for clearly subsystem-prefixed codes
    for prefix, category in _PREFIX_TO_CATEGORY.items():
        if upper.startswith(prefix):
            return {
                "canonical_category": category,
                "detail_code": lower,
                "source_subsystem": _PREFIX_TO_SUBSYSTEM.get(prefix),
                "details": dict(detail_fields or {}),
            }

    # 4. Unknown
    return {
        "canonical_category": "UNKNOWN",
        "detail_code": lower,
        "source_subsystem": None,
        "details": dict(detail_fields or {}),
    }


def _infer_subsystem(upper_code: str) -> Optional[str]:
    for prefix, subsystem in _PREFIX_TO_SUBSYSTEM.items():
        if upper_code.startswith(prefix):
            return subsystem
    return None


def assert_canonical_or_alias(raw_code: str) -> None:
    """Guardrail used at policy boundaries.

    Raises ``ReasonCodeError`` when a high-level blocking string (e.g.,
    ``"blocked"``, ``"freeze"``, ``"fail"``) is used as a reason code without
    a canonical mapping. Canonical categories and known aliases pass.

    Empty / whitespace strings are NOT acceptable as blocking reason codes.
    """
    if not isinstance(raw_code, str) or not raw_code.strip():
        raise ReasonCodeError("blocking reason code must be a non-empty string")

    table_data = _alias_table()
    aliases = {str(k).lower() for k in (table_data.get("aliases") or {}).keys()}
    canonical_set = set(table_data.get("canonical_categories") or CANONICAL_CATEGORIES)
    high_level = {
        str(c).lower()
        for c in (table_data.get("high_level_blocking_codes_requiring_canonical_mapping") or [])
    }

    upper = raw_code.strip().upper()
    lower = raw_code.strip().lower()
    if upper in canonical_set:
        return
    if lower in aliases:
        return
    if lower in high_level:
        raise ReasonCodeError(
            f"high-level blocking reason {raw_code!r} must map to a canonical category"
        )
    # Subsystem-prefixed codes are admitted only if they match a known prefix.
    for prefix in _PREFIX_TO_CATEGORY:
        if upper.startswith(prefix):
            return
    raise ReasonCodeError(
        f"reason code {raw_code!r} is neither canonical nor a known alias"
    )


def categorize_many(
    codes: Mapping[str, Any],
) -> Dict[str, str]:
    """Convenience: map ``code → canonical_category`` for the supplied codes."""
    out: Dict[str, str] = {}
    for code in codes:
        result = canonicalize_reason_code(str(code))
        out[str(code)] = result["canonical_category"]
    return out


__all__ = [
    "CANONICAL_CATEGORIES",
    "ReasonCodeError",
    "assert_canonical_or_alias",
    "canonicalize_reason_code",
    "categorize_many",
]
