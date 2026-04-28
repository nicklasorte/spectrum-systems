"""RFX trend → roadmap recommendation generator — RFX-08.

Converts trend/hotspot artifacts into prioritized roadmap recommendations.
This module is a non-owning phase-label support helper. It does **not**
mutate the canonical roadmap, claim roadmap authority, or bypass roadmap
governance. Canonical roadmap authority is recorded in
``docs/architecture/system_registry.md`` and the surfaces referenced by
``scripts/check_roadmap_authority.py``.

Output:

  * ``rfx_roadmap_recommendation`` — advisory, non-owning roadmap candidate.

Reason codes:

  * ``rfx_roadmap_source_missing``
  * ``rfx_roadmap_recommendation_invalid``
  * ``rfx_roadmap_dependency_missing``
  * ``rfx_roadmap_authority_unsafe``
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class RFXRoadmapGeneratorError(ValueError):
    """Raised when a roadmap recommendation fails closed."""


# Authority-shape phrases the roadmap recommendation must not contain.
# These mirror the spirit of ``scripts/check_roadmap_authority.py`` so an
# RFX-emitted recommendation cannot accidentally slip authority-claiming
# language into governed surfaces.
_AUTHORITY_UNSAFE_PATTERNS = [
    re.compile(r"\bprimary roadmap\b", re.IGNORECASE),
    re.compile(r"\bsole active roadmap\b", re.IGNORECASE),
    re.compile(r"\bactive roadmap is\b", re.IGNORECASE),
    re.compile(r"\bsingle authoritative roadmap\b", re.IGNORECASE),
    re.compile(r"\bclaim(s|ing)? roadmap authority\b", re.IGNORECASE),
    re.compile(r"\bsupersede[s]? canonical roadmap\b", re.IGNORECASE),
    re.compile(r"\bbypass(es|ing)? roadmap governance\b", re.IGNORECASE),
]


def _stable_id(payload: Any, *, prefix: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _check_authority_safe(text: str, reasons: list[str]) -> None:
    if not isinstance(text, str):
        return
    for pattern in _AUTHORITY_UNSAFE_PATTERNS:
        if pattern.search(text):
            reasons.append(
                f"rfx_roadmap_authority_unsafe: recommendation text matches forbidden pattern {pattern.pattern!r}"
            )
            return


def build_rfx_roadmap_recommendation(
    *,
    source_trend_refs: list[str] | None,
    source_hotspot_refs: list[str] | None,
    reason_codes: list[str] | None,
    recommended_build_slice: str | None,
    affected_systems: list[str] | None,
    required_owners: list[str] | None,
    dependencies: list[str] | None,
    acceptance_criteria: list[str] | None,
    red_team_requirement: str | None,
    fix_follow_up_requirement: str | None,
    revalidation_requirement: str | None,
    rationale: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic, non-owning roadmap recommendation.

    Fails closed when source refs are missing, dependencies are absent, the
    red-team / fix / revalidation triad is incomplete, or the recommendation
    text uses authority-claiming language.
    """
    reasons: list[str] = []

    if not source_trend_refs and not source_hotspot_refs:
        reasons.append(
            "rfx_roadmap_source_missing: recommendation requires at least one trend or hotspot ref"
        )
    if not isinstance(recommended_build_slice, str) or not recommended_build_slice.strip():
        reasons.append(
            "rfx_roadmap_recommendation_invalid: recommended_build_slice absent"
        )
    if not isinstance(reason_codes, list) or not any(isinstance(c, str) and c.strip() for c in reason_codes):
        reasons.append(
            "rfx_roadmap_recommendation_invalid: reason_codes absent"
        )
    if not isinstance(affected_systems, list) or not any(isinstance(s, str) and s.strip() for s in affected_systems):
        reasons.append(
            "rfx_roadmap_recommendation_invalid: affected_systems absent"
        )
    if not isinstance(required_owners, list) or not any(isinstance(o, str) and o.strip() for o in required_owners):
        reasons.append(
            "rfx_roadmap_recommendation_invalid: required_owners absent"
        )
    if not isinstance(acceptance_criteria, list) or not any(isinstance(a, str) and a.strip() for a in acceptance_criteria):
        reasons.append(
            "rfx_roadmap_recommendation_invalid: acceptance_criteria absent"
        )
    if not isinstance(dependencies, list):
        reasons.append(
            "rfx_roadmap_dependency_missing: dependencies list absent"
        )
    elif not any(isinstance(d, str) and d.strip() for d in dependencies):
        # Empty dependency list is allowed only when explicitly declared; we
        # require an explicit "no_external_dependencies" sentinel so a quiet
        # empty list cannot slip past as "no deps".
        reasons.append(
            "rfx_roadmap_dependency_missing: dependencies list contains no entries — "
            "use ['no_external_dependencies'] to declare an empty dependency set explicitly"
        )

    for label, value in [
        ("red_team_requirement", red_team_requirement),
        ("fix_follow_up_requirement", fix_follow_up_requirement),
        ("revalidation_requirement", revalidation_requirement),
    ]:
        if not isinstance(value, str) or not value.strip():
            reasons.append(
                f"rfx_roadmap_recommendation_invalid: {label} absent"
            )

    for chunk in [
        recommended_build_slice or "",
        rationale or "",
        " ".join(reason_codes or []),
        " ".join(acceptance_criteria or []),
        " ".join(affected_systems or []),
        red_team_requirement or "",
        fix_follow_up_requirement or "",
        revalidation_requirement or "",
    ]:
        _check_authority_safe(chunk, reasons)

    if reasons:
        raise RFXRoadmapGeneratorError("; ".join(reasons))

    payload = {
        "source_trend_refs": sorted({s.strip() for s in (source_trend_refs or []) if isinstance(s, str)}),
        "source_hotspot_refs": sorted({s.strip() for s in (source_hotspot_refs or []) if isinstance(s, str)}),
        "reason_codes": sorted({c.strip() for c in (reason_codes or []) if isinstance(c, str)}),
        "recommended_build_slice": recommended_build_slice.strip(),  # type: ignore[union-attr]
    }
    rec_id = _stable_id(payload, prefix="rfx-roadmap-rec")

    return {
        "artifact_type": "rfx_roadmap_recommendation",
        "schema_version": "1.0.0",
        "recommendation_id": rec_id,
        "source_trend_refs": payload["source_trend_refs"],
        "source_hotspot_refs": payload["source_hotspot_refs"],
        "reason_codes": payload["reason_codes"],
        "recommended_build_slice": payload["recommended_build_slice"],
        "affected_systems": [s.strip() for s in (affected_systems or []) if isinstance(s, str) and s.strip()],
        "required_owners": [o.strip() for o in (required_owners or []) if isinstance(o, str) and o.strip()],
        "dependencies": [d.strip() for d in (dependencies or []) if isinstance(d, str) and d.strip()],
        "acceptance_criteria": [a.strip() for a in (acceptance_criteria or []) if isinstance(a, str) and a.strip()],
        "red_team_requirement": red_team_requirement.strip(),  # type: ignore[union-attr]
        "fix_follow_up_requirement": fix_follow_up_requirement.strip(),  # type: ignore[union-attr]
        "revalidation_requirement": revalidation_requirement.strip(),  # type: ignore[union-attr]
        "rationale": rationale.strip() if isinstance(rationale, str) else None,
        "ownership_note": (
            "Advisory recommendation only; canonical roadmap authority is unchanged. "
            "Advancement still requires the canonical roadmap governance flow."
        ),
    }


__all__ = [
    "RFXRoadmapGeneratorError",
    "build_rfx_roadmap_recommendation",
]
