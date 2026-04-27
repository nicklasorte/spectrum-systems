"""OBS: Reason-code lifecycle audit (NT-10..12).

Extends the existing reason-code canonicalizer with lifecycle-aware
classification:

  * ``active``     — alias maps cleanly; safe to emit.
  * ``deprecated`` — alias maps but emits a warning; new code should not use it.
  * ``merged``     — alias rewritten into another canonical detail code.
  * ``forbidden``  — alias must NOT be emitted; presence in output blocks.

It also provides an audit that reports:

  * unmapped blocking reason codes
  * unused aliases
  * aliases pointing to missing canonical category
  * deprecated aliases still emitted by code
  * forbidden aliases emitted anywhere

The lifecycle table lives at ``contracts/governance/reason_code_aliases.json``
in the ``alias_lifecycle`` block.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from spectrum_systems.modules.observability.reason_code_canonicalizer import (
    CANONICAL_CATEGORIES,
    DEFAULT_ALIAS_PATH,
    ReasonCodeError,
    canonicalize_reason_code,
)


LIFECYCLE_STATES = ("active", "deprecated", "merged", "forbidden")


CANONICAL_REASON_LIFECYCLE_REASON_CODES = (
    "REASON_CODE_LIFECYCLE_ACTIVE",
    "REASON_CODE_LIFECYCLE_DEPRECATED",
    "REASON_CODE_LIFECYCLE_FORBIDDEN",
    "REASON_CODE_LIFECYCLE_UNMAPPED_BLOCKING",
    "REASON_CODE_LIFECYCLE_UNUSED_ALIAS",
    "REASON_CODE_LIFECYCLE_DUPLICATE_ALIAS",
    "REASON_CODE_LIFECYCLE_MISSING_CANONICAL_CATEGORY",
)


class ReasonCodeLifecycleError(ReasonCodeError):
    """Raised when a forbidden lifecycle code is emitted."""


def _load_alias_table(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or DEFAULT_ALIAS_PATH
    if not p.exists():
        raise ReasonCodeError(f"reason code alias file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("artifact_type") != "reason_code_alias_map":
        raise ReasonCodeError("alias file artifact_type mismatch")
    return data


def classify_reason_code_lifecycle(
    raw_code: str,
    *,
    alias_table: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify a reason code by lifecycle state.

    Returns
    -------
    {"detail_code": str (lowercased input),
     "canonical_category": str (or "UNKNOWN"),
     "lifecycle_state": "active" | "deprecated" | "merged" | "forbidden" | "unknown",
     "merged_into": str | None,
     "warnings": [str, ...]}
    """
    table = dict(alias_table) if alias_table is not None else _load_alias_table()
    lifecycle = table.get("alias_lifecycle") or {}
    canonical_set = set(table.get("canonical_categories") or CANONICAL_CATEGORIES)
    canon_result = canonicalize_reason_code(raw_code, alias_table=table)
    detail = canon_result["detail_code"]
    canonical_category = canon_result["canonical_category"]

    forbidden = {str(c).lower() for c in (lifecycle.get("forbidden") or [])}
    deprecated = {str(c).lower() for c in (lifecycle.get("deprecated") or [])}
    merged = {
        str(k).lower(): str(v).lower() for k, v in (lifecycle.get("merged") or {}).items()
    }

    warnings: List[str] = []
    state = "active"
    merged_into: Optional[str] = None

    if detail in forbidden:
        state = "forbidden"
        warnings.append(f"reason code {raw_code!r} is forbidden by lifecycle policy")
    elif detail in merged:
        state = "merged"
        merged_into = merged[detail]
        warnings.append(
            f"reason code {raw_code!r} is merged into {merged_into!r}"
        )
    elif detail in deprecated:
        state = "deprecated"
        warnings.append(
            f"reason code {raw_code!r} is deprecated; new code must not emit it"
        )

    if canonical_category not in canonical_set and canonical_category != "UNKNOWN":
        warnings.append(
            f"alias {raw_code!r} points to non-canonical category {canonical_category!r}"
        )

    return {
        "detail_code": detail,
        "canonical_category": canonical_category,
        "lifecycle_state": state if canonical_category != "UNKNOWN" or state == "forbidden" else "unknown",
        "merged_into": merged_into,
        "warnings": warnings,
    }


def assert_emittable_reason_code(raw_code: str) -> Dict[str, Any]:
    """Fail-closed guardrail for code that emits reason codes.

    Behavior:
      * forbidden → raise ReasonCodeLifecycleError
      * unknown high-level (e.g., "blocked") → raise ReasonCodeError
      * deprecated → return classification with warnings (does not raise)
      * active → return classification with empty warnings

    Returns the classification dict.
    """
    result = classify_reason_code_lifecycle(raw_code)
    if result["lifecycle_state"] == "forbidden":
        raise ReasonCodeLifecycleError(
            f"reason code {raw_code!r} is forbidden — must not be emitted"
        )
    if result["canonical_category"] == "UNKNOWN":
        # Mirror assert_canonical_or_alias: high-level blocking codes must
        # be canonical / aliased before they ship.
        from spectrum_systems.modules.observability.reason_code_canonicalizer import (
            assert_canonical_or_alias,
        )

        assert_canonical_or_alias(raw_code)
    return result


def audit_reason_code_coverage(
    *,
    emitted_codes: Iterable[str],
    alias_table: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Audit a set of emitted reason codes against the alias map.

    Reports:
      * unmapped_blocking_codes: emitted high-level codes (blocked, freeze)
        that lack a canonical mapping
      * unused_aliases: aliases declared but not emitted
      * deprecated_emitted: aliases that are emitted but marked deprecated
      * forbidden_emitted: aliases that are emitted but marked forbidden
      * aliases_pointing_to_missing_canonical: aliases mapping to category
        not present in canonical_categories list
    """
    table = dict(alias_table) if alias_table is not None else _load_alias_table()
    aliases = {str(k).lower(): str(v).upper() for k, v in (table.get("aliases") or {}).items()}
    canonical_set = set(table.get("canonical_categories") or CANONICAL_CATEGORIES)
    high_level = {
        str(c).lower()
        for c in (table.get("high_level_blocking_codes_requiring_canonical_mapping") or [])
    }
    lifecycle = table.get("alias_lifecycle") or {}
    forbidden = {str(c).lower() for c in (lifecycle.get("forbidden") or [])}
    deprecated = {str(c).lower() for c in (lifecycle.get("deprecated") or [])}

    emitted_norm = [str(c).lower() for c in emitted_codes if isinstance(c, str)]
    emitted_set = set(emitted_norm)

    unmapped_blocking = sorted(
        c for c in emitted_set if c in high_level and c not in aliases
    )
    deprecated_emitted = sorted(c for c in emitted_set if c in deprecated)
    forbidden_emitted = sorted(c for c in emitted_set if c in forbidden)
    unused_aliases = sorted(set(aliases.keys()) - emitted_set)
    aliases_to_missing = sorted(
        a for a, cat in aliases.items() if cat not in canonical_set
    )

    # Duplicate aliases: identical canonical and same prefix indicates
    # likely duplicate semantic. Conservative: flag aliases whose lowercased
    # detail-code differs only by suffix and maps to the same canonical.
    dup_groups: Dict[str, List[str]] = {}
    for alias, canon in aliases.items():
        parts = alias.split("_")
        if len(parts) <= 1:
            key = f"{parts[0]}|{canon}"
        else:
            key = f"{parts[0]}_{parts[1]}|{canon}"
        dup_groups.setdefault(key, []).append(alias)
    duplicate_aliases = [
        sorted(group)
        for group in dup_groups.values()
        if len(group) > 1
    ]
    duplicate_aliases.sort()

    blocking: List[str] = []
    if unmapped_blocking:
        blocking.append(
            f"unmapped blocking codes emitted: {', '.join(unmapped_blocking)}"
        )
    if forbidden_emitted:
        blocking.append(
            f"forbidden codes emitted: {', '.join(forbidden_emitted)}"
        )
    if aliases_to_missing:
        blocking.append(
            f"aliases pointing to non-canonical category: {', '.join(aliases_to_missing)}"
        )

    decision = "block" if blocking else "allow"
    reason_code = "REASON_CODE_LIFECYCLE_ACTIVE"
    if forbidden_emitted:
        reason_code = "REASON_CODE_LIFECYCLE_FORBIDDEN"
    elif unmapped_blocking:
        reason_code = "REASON_CODE_LIFECYCLE_UNMAPPED_BLOCKING"
    elif aliases_to_missing:
        reason_code = "REASON_CODE_LIFECYCLE_MISSING_CANONICAL_CATEGORY"

    return {
        "artifact_type": "reason_code_coverage_audit",
        "schema_version": "1.0.0",
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "unmapped_blocking": unmapped_blocking,
        "deprecated_emitted": deprecated_emitted,
        "forbidden_emitted": forbidden_emitted,
        "unused_aliases": unused_aliases,
        "aliases_pointing_to_missing_canonical": aliases_to_missing,
        "duplicate_aliases": duplicate_aliases,
    }


__all__ = [
    "CANONICAL_REASON_LIFECYCLE_REASON_CODES",
    "LIFECYCLE_STATES",
    "ReasonCodeLifecycleError",
    "assert_emittable_reason_code",
    "audit_reason_code_coverage",
    "classify_reason_code_lifecycle",
]
