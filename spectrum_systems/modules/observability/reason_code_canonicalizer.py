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
from typing import Any, Dict, Iterable, List, Mapping, Optional


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

# NT-12: lifecycle states for aliases. ``active`` is the default when the
# alias appears in the alias map without an explicit lifecycle entry.
ALIAS_LIFECYCLE_STATES = ("active", "deprecated", "merged", "forbidden")

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
    "TRUST_FRESHNESS_": "CERTIFICATION_GAP",
    "PROOF_SIZE_": "CERTIFICATION_GAP",
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
    "TRUST_FRESHNESS_": "OBS",
    "PROOF_SIZE_": "GOV",
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


def _lifecycle_for(alias_lower: str, table_data: Mapping[str, Any]) -> str:
    """Return the lifecycle state for an alias key.

    The lifecycle map has the shape::

        {
          "alias_lifecycle": {
            "deprecated": {alias: {...metadata...}, ...},
            "merged": {alias: {...}, ...},
            "forbidden": {alias: {...}, ...}
          }
        }

    Aliases not listed default to ``active``.
    """
    lifecycle = table_data.get("alias_lifecycle") or {}
    if not isinstance(lifecycle, Mapping):
        return "active"
    for state in ("forbidden", "deprecated", "merged"):
        bucket = lifecycle.get(state) or {}
        if isinstance(bucket, Mapping) and alias_lower in {k.lower() for k in bucket}:
            return state
    return "active"


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
       "lifecycle": "active" | "deprecated" | "merged" | "forbidden",
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
            "lifecycle": "active",
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
            "lifecycle": "active",
            "details": dict(detail_fields or {}),
        }

    # 2. Alias hit
    if lower in aliases:
        canonical = aliases[lower]
        lifecycle = _lifecycle_for(lower, table_data)
        return {
            "canonical_category": canonical if canonical in canonical_set else "UNKNOWN",
            "detail_code": lower,
            "source_subsystem": _infer_subsystem(upper),
            "lifecycle": lifecycle,
            "details": dict(detail_fields or {}),
        }

    # 2b. Lifecycle-only entry (forbidden/deprecated/merged tracked but not
    # resolved through the active alias map). Surface the lifecycle so the
    # boundary guard can refuse, but still expose the canonical category
    # via prefix heuristic when available.
    lifecycle_only = _lifecycle_for(lower, table_data)
    if lifecycle_only != "active":
        category = "UNKNOWN"
        for prefix, cat in _PREFIX_TO_CATEGORY.items():
            if upper.startswith(prefix):
                category = cat
                break
        return {
            "canonical_category": category,
            "detail_code": lower,
            "source_subsystem": _infer_subsystem(upper),
            "lifecycle": lifecycle_only,
            "details": dict(detail_fields or {}),
        }

    # 3. Subsystem prefix heuristic — only for clearly subsystem-prefixed codes
    for prefix, category in _PREFIX_TO_CATEGORY.items():
        if upper.startswith(prefix):
            return {
                "canonical_category": category,
                "detail_code": lower,
                "source_subsystem": _PREFIX_TO_SUBSYSTEM.get(prefix),
                "lifecycle": "active",
                "details": dict(detail_fields or {}),
            }

    # 4. Unknown
    return {
        "canonical_category": "UNKNOWN",
        "detail_code": lower,
        "source_subsystem": None,
        "lifecycle": "active",
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
    a canonical mapping. Canonical categories and known active aliases pass.

    NT-12: forbidden aliases always raise; deprecated aliases pass but the
    caller can detect the lifecycle through ``canonicalize_reason_code``.

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

    # NT-12: forbidden aliases never pass — they may be present in the alias
    # map for tracking, but emitting one is a hard fault.
    forbidden_bucket = (table_data.get("alias_lifecycle") or {}).get("forbidden") or {}
    if isinstance(forbidden_bucket, Mapping) and lower in {
        str(k).lower() for k in forbidden_bucket
    }:
        raise ReasonCodeError(
            f"reason code {raw_code!r} is forbidden by lifecycle policy"
        )

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


def audit_reason_code_coverage(
    *,
    emitted_codes: Iterable[str],
    expected_blocking_codes: Optional[Iterable[str]] = None,
    alias_table: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """NT-10: Audit reason-code coverage across the alias map.

    Inputs
    ------
    emitted_codes:
        The set of detail codes the codebase actually emits (collected
        from runtime/tests).
    expected_blocking_codes:
        Optional set of detail codes that ARE expected to block; used to
        verify each one maps to a known canonical category.

    Returns
    -------
    {
      "unmapped_blocking_codes": [...],         # blocking, no canonical
      "unused_aliases": [...],                  # in alias map, not emitted
      "duplicate_meaning_aliases": [...],       # two aliases → same canon AND same prefix root
      "aliases_with_missing_category": [...],   # alias maps to non-canonical
      "deprecated_emitted": [...],              # deprecated aliases still emitted
      "forbidden_emitted": [...],               # forbidden aliases emitted (hard error)
      "summary": str,
    }
    """
    table_data = (
        dict(alias_table) if alias_table is not None else _alias_table()
    )
    aliases_map: Dict[str, str] = {
        str(k).lower(): str(v).upper()
        for k, v in (table_data.get("aliases") or {}).items()
    }
    canonical_set = set(
        table_data.get("canonical_categories") or CANONICAL_CATEGORIES
    )
    lifecycle = table_data.get("alias_lifecycle") or {}
    deprecated_bucket = {
        str(k).lower() for k in (lifecycle.get("deprecated") or {})
    }
    forbidden_bucket = {
        str(k).lower() for k in (lifecycle.get("forbidden") or {})
    }

    emitted_lower = {str(c).strip().lower() for c in emitted_codes if c}
    expected_blocking = {
        str(c).strip().lower() for c in (expected_blocking_codes or []) if c
    }

    unmapped_blocking: List[str] = []
    for code in sorted(expected_blocking):
        if not code:
            continue
        canon_result = canonicalize_reason_code(
            code, alias_table=table_data
        )
        if canon_result["canonical_category"] == "UNKNOWN":
            unmapped_blocking.append(code)

    aliases_with_missing_category: List[str] = [
        code for code, cat in aliases_map.items() if cat not in canonical_set
    ]

    # Duplicate meaning detection: two aliases share the same canonical
    # category AND the same trailing token (the part after the prefix
    # underscore). This is intentionally conservative.
    by_signature: Dict[tuple, List[str]] = {}
    for code, cat in aliases_map.items():
        last_token = code.split("_")[-1]
        by_signature.setdefault((cat, last_token), []).append(code)
    duplicate_meaning_aliases: List[List[str]] = [
        sorted(group) for group in by_signature.values() if len(group) > 1
    ]

    unused_aliases = sorted(
        code
        for code in aliases_map
        if code not in emitted_lower
        and code not in deprecated_bucket
        and code not in forbidden_bucket
    )

    deprecated_emitted = sorted(emitted_lower & deprecated_bucket)
    forbidden_emitted = sorted(emitted_lower & forbidden_bucket)

    summary = (
        f"reason-code coverage: emitted={len(emitted_lower)} "
        f"aliases={len(aliases_map)} unmapped_blocking={len(unmapped_blocking)} "
        f"deprecated_emitted={len(deprecated_emitted)} "
        f"forbidden_emitted={len(forbidden_emitted)} "
        f"unused={len(unused_aliases)} duplicate_meaning_groups="
        f"{len(duplicate_meaning_aliases)}"
    )

    return {
        "artifact_type": "reason_code_coverage_audit",
        "schema_version": "1.0.0",
        "unmapped_blocking_codes": unmapped_blocking,
        "unused_aliases": unused_aliases,
        "duplicate_meaning_aliases": duplicate_meaning_aliases,
        "aliases_with_missing_category": aliases_with_missing_category,
        "deprecated_emitted": deprecated_emitted,
        "forbidden_emitted": forbidden_emitted,
        "summary": summary,
    }


__all__ = [
    "ALIAS_LIFECYCLE_STATES",
    "CANONICAL_CATEGORIES",
    "ReasonCodeError",
    "assert_canonical_or_alias",
    "audit_reason_code_coverage",
    "canonicalize_reason_code",
    "categorize_many",
]
