"""RFX judgment extraction — RFX-11.

Converts repeated signal/fix patterns into JDX-compatible judgment
candidates. This module is a non-owning phase-label support helper and
must not issue judgment semantics directly. JDX owns judgment semantics;
the canonical lifecycle role belongs to JSX. Both canonical roles are
recorded in ``docs/architecture/system_registry.md``.

Output:

  * ``rfx_judgment_candidate``

Reason codes:

  * ``rfx_judgment_source_missing``
  * ``rfx_judgment_evidence_insufficient``
  * ``rfx_judgment_candidate_invalid``
  * ``rfx_jdx_handoff_missing``
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class RFXJudgmentExtractionError(ValueError):
    """Raised when judgment extraction fails closed."""


_DEFAULT_MIN_DISTINCT_FAILURES = 2
_DEFAULT_MIN_TOTAL_REFS = 3


def _stable_id(payload: Any, *, prefix: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _coerce_ref_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        if isinstance(v, str) and v.strip() and v.strip() not in seen:
            seen.add(v.strip())
            out.append(v.strip())
    return out


def build_rfx_judgment_candidate(
    *,
    failure_refs: list[str] | None,
    fix_refs: list[str] | None,
    eval_refs: list[str] | None,
    repeated_pattern_summary: str | None,
    proposed_judgment_primitive: str | None,
    jdx_handoff_target: str | None,
    min_distinct_failures: int = _DEFAULT_MIN_DISTINCT_FAILURES,
    min_total_refs: int = _DEFAULT_MIN_TOTAL_REFS,
) -> dict[str, Any]:
    """Build a deterministic, non-owning judgment candidate.

    Fails closed when source refs are missing, evidence sufficiency is not
    met, the candidate structure is invalid, or no JDX handoff target is
    supplied. Does not mutate any active JDX/JSX state.
    """
    failures = _coerce_ref_list(failure_refs)
    fixes = _coerce_ref_list(fix_refs)
    evals = _coerce_ref_list(eval_refs)

    reasons: list[str] = []

    if not failures and not fixes and not evals:
        reasons.append(
            "rfx_judgment_source_missing: candidate requires failure/fix/eval source refs"
        )
    if not failures:
        reasons.append(
            "rfx_judgment_source_missing: candidate requires at least one failure ref"
        )
    if len(failures) < min_distinct_failures:
        reasons.append(
            f"rfx_judgment_evidence_insufficient: {len(failures)} failure ref(s) below "
            f"min_distinct_failures={min_distinct_failures}"
        )
    if (len(failures) + len(fixes) + len(evals)) < min_total_refs:
        reasons.append(
            f"rfx_judgment_evidence_insufficient: total source refs={len(failures) + len(fixes) + len(evals)} "
            f"below min_total_refs={min_total_refs}"
        )
    if not isinstance(repeated_pattern_summary, str) or not repeated_pattern_summary.strip():
        reasons.append(
            "rfx_judgment_candidate_invalid: repeated_pattern_summary absent"
        )
    if not isinstance(proposed_judgment_primitive, str) or not proposed_judgment_primitive.strip():
        reasons.append(
            "rfx_judgment_candidate_invalid: proposed_judgment_primitive absent"
        )
    if not isinstance(jdx_handoff_target, str) or not jdx_handoff_target.strip():
        reasons.append(
            "rfx_jdx_handoff_missing: JDX handoff target reference absent"
        )

    if reasons:
        raise RFXJudgmentExtractionError("; ".join(reasons))

    payload = {
        "failure_refs": sorted(failures),
        "fix_refs": sorted(fixes),
        "eval_refs": sorted(evals),
        "primitive": proposed_judgment_primitive.strip(),  # type: ignore[union-attr]
    }
    candidate_id = _stable_id(payload, prefix="rfx-judgment-candidate")
    return {
        "artifact_type": "rfx_judgment_candidate",
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "source_failure_refs": failures,
        "source_fix_refs": fixes,
        "source_eval_refs": evals,
        "repeated_pattern_summary": repeated_pattern_summary.strip(),  # type: ignore[union-attr]
        "proposed_judgment_primitive": proposed_judgment_primitive.strip(),  # type: ignore[union-attr]
        "evidence_sufficiency": {
            "failure_refs_count": len(failures),
            "fix_refs_count": len(fixes),
            "eval_refs_count": len(evals),
            "min_distinct_failures": min_distinct_failures,
            "min_total_refs": min_total_refs,
        },
        "jdx_handoff_target": jdx_handoff_target.strip(),  # type: ignore[union-attr]
        "ownership_note": (
            "Advisory candidate only; JDX retains the canonical judgment "
            "semantic role and JSX retains the canonical lifecycle role. "
            "RFX is a non-owning phase label."
        ),
    }


__all__ = [
    "RFXJudgmentExtractionError",
    "build_rfx_judgment_candidate",
]
