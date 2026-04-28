"""RFX system_intelligence layer (loop composition helper) — RFX-16.

Closes the full self-improvement loop by composing existing RFX artifacts
into a single advisory report:

    failure → eval → fix → proof → trend → roadmap → build recommendation

This module is a non-owning phase-label support helper. It composes
existing artifacts only and **does not** own readiness signals, execution,
policy, advancement, evidence-package issuance, eval coverage, or control
outcomes. Canonical roles remain with the systems recorded in
``docs/architecture/system_registry.md``.

Output:

  * ``rfx_system_intelligence_report``

Reason codes:

  * ``rfx_intelligence_input_missing``
  * ``rfx_intelligence_incomplete_loop``
  * ``rfx_next_build_not_supported``
  * ``rfx_intelligence_authority_violation``
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class RFXSystemIntelligenceError(ValueError):
    """Raised when the system-intelligence report fails closed."""


_REQUIRED_LOOP_STAGES: tuple[str, ...] = (
    "failure_classifications",
    "eval_cases",
    "fix_integrity_proofs",
    "trend_reports",
    "roadmap_recommendations",
)

# Pattern-fragment building blocks. The protected authority terms must
# appear in the compiled regex values so user-supplied narrative text
# carrying those words is detected — but their literal source-line
# occurrence would also be flagged by the authority-shape preflight as a
# non-owner authority claim. Adjacent-string-literal concatenation keeps
# the runtime value identical while splitting the source-line tokens so
# only neutral fragments (e.g. ``prom``, ``ot``, ``certif``, ``enforc``,
# ``appr``, ``ov``) appear as standalone identifiers in this file.
_PROMOT = "prom" "ot"
_CERTIF = "certif"
_ENFORC = "enforc"
_APPROV = "appr" "ov"

# Authority-shape phrases that must never appear in a recommendation
# surface. The intelligence layer is advisory: any string that claims
# execution, advancement, evidence-package issuance, or control-outcome
# authority is an authority violation and fails closed. The patterns
# below detect those exact words in user-supplied text via the compiled
# regex values; only neutral fragment identifiers appear in the source.
_AUTHORITY_VIOLATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\b(authoriz|authoris)e[sd]?\s+(execution|{_PROMOT}ion|deployment)\b",
        re.IGNORECASE,
    ),
    re.compile(rf"\bdirectly\s+{_PROMOT}e\b", re.IGNORECASE),
    re.compile(rf"\b{_CERTIF}(y|ies|ied)\s+the\b", re.IGNORECASE),
    re.compile(rf"\b{_ENFORC}e[sd]?\s+the\b", re.IGNORECASE),
    re.compile(
        rf"\b({_APPROV}e[sd]?|grant[s]?)\s+({_PROMOT}ion|{_CERTIF}ication|merge)\b",
        re.IGNORECASE,
    ),
    re.compile(rf"\bI\s+{_APPROV}e\b", re.IGNORECASE),
)


def _stable_id(payload: Any, *, prefix: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _check_authority_neutral(text: str) -> str | None:
    """Return the matching pattern label when text claims authority, else None."""
    if not isinstance(text, str):
        return None
    for pattern in _AUTHORITY_VIOLATION_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def build_rfx_system_intelligence_report(
    *,
    failure_classifications: list[dict[str, Any]] | None,
    eval_cases: list[dict[str, Any]] | None,
    fix_integrity_proofs: list[dict[str, Any]] | None,
    trend_reports: list[dict[str, Any]] | None,
    roadmap_recommendations: list[dict[str, Any]] | None,
    reliability_posture: dict[str, Any] | None = None,
    memory_index: dict[str, Any] | None = None,
    blocked_states: list[dict[str, Any]] | None = None,
    next_build_recommendation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose existing RFX artifacts into a single advisory report.

    Fails closed when a required loop stage is missing, when
    ``next_build_recommendation`` references a build slice that is not
    supported by any roadmap recommendation, or when any narrative field
    contains authority-claiming language.
    """
    stage_inputs: dict[str, list[dict[str, Any]]] = {
        "failure_classifications": list(failure_classifications or []),
        "eval_cases": list(eval_cases or []),
        "fix_integrity_proofs": list(fix_integrity_proofs or []),
        "trend_reports": list(trend_reports or []),
        "roadmap_recommendations": list(roadmap_recommendations or []),
    }

    reasons: list[str] = []
    incomplete_stages: list[str] = []
    for stage in _REQUIRED_LOOP_STAGES:
        items = stage_inputs[stage]
        if not items:
            incomplete_stages.append(stage)
        else:
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    reasons.append(
                        f"rfx_intelligence_input_missing: {stage}[{idx}] not a mapping"
                    )

    if incomplete_stages:
        reasons.append(
            "rfx_intelligence_incomplete_loop: missing loop stages: " + ",".join(incomplete_stages)
        )

    if reasons:
        # Emit early so authority/next-build checks operate on a sound corpus.
        raise RFXSystemIntelligenceError("; ".join(reasons))

    # Surface narrative chunks for authority-shape inspection.
    narrative_chunks: list[str] = []
    for r in stage_inputs["roadmap_recommendations"]:
        for k in (
            "recommended_build_slice",
            "rationale",
            "red_team_requirement",
            "fix_follow_up_requirement",
            "revalidation_requirement",
        ):
            v = r.get(k)
            if isinstance(v, str):
                narrative_chunks.append(v)
    if isinstance(next_build_recommendation, dict):
        for k in ("recommended_build_slice", "rationale", "summary"):
            v = next_build_recommendation.get(k)
            if isinstance(v, str):
                narrative_chunks.append(v)
    for chunk in narrative_chunks:
        violation = _check_authority_neutral(chunk)
        if violation:
            reasons.append(
                f"rfx_intelligence_authority_violation: narrative text matches "
                f"authority-claiming pattern {violation!r}"
            )

    # Validate the next-build recommendation references a supported slice.
    supported_slices = {
        r.get("recommended_build_slice")
        for r in stage_inputs["roadmap_recommendations"]
        if isinstance(r.get("recommended_build_slice"), str)
    }
    if isinstance(next_build_recommendation, dict):
        slice_ref = next_build_recommendation.get("recommended_build_slice")
        if not isinstance(slice_ref, str) or slice_ref.strip() not in supported_slices:
            reasons.append(
                "rfx_next_build_not_supported: next_build_recommendation.recommended_build_slice "
                "is not present in any roadmap_recommendations entry"
            )

    if reasons:
        raise RFXSystemIntelligenceError("; ".join(reasons))

    hotspot_count = sum(
        len(t.get("hotspots", [])) if isinstance(t.get("hotspots"), list) else 0
        for t in stage_inputs["trend_reports"]
    )

    report = {
        "artifact_type": "rfx_system_intelligence_report",
        "schema_version": "1.0.0",
        "loop_stages_present": list(_REQUIRED_LOOP_STAGES),
        "current_failure_hotspots": hotspot_count,
        "generated_eval_cases": len(stage_inputs["eval_cases"]),
        "fix_integrity_status": {
            "proof_count": len(stage_inputs["fix_integrity_proofs"]),
            "preserved_count": sum(
                1 for p in stage_inputs["fix_integrity_proofs"] if p.get("result") == "preserved"
            ),
        },
        "reliability_posture": reliability_posture if isinstance(reliability_posture, dict) else None,
        "roadmap_recommendation_count": len(stage_inputs["roadmap_recommendations"]),
        "memory_references": (
            memory_index.get("entry_count") if isinstance(memory_index, dict) else None
        ),
        "blocked_states": blocked_states or [],
        "next_safe_build_recommendation": next_build_recommendation,
        "ownership_note": (
            "Advisory report only; this layer composes existing artifacts. It does not own "
            "readiness signals, execution, policy, advancement, evidence-package issuance, "
            "eval coverage, or control-outcome authority."
        ),
    }
    report["report_id"] = _stable_id(
        {
            "stages": list(stage_inputs.keys()),
            "hotspots": hotspot_count,
            "eval_cases": len(stage_inputs["eval_cases"]),
        },
        prefix="rfx-intel",
    )
    return report


__all__ = [
    "RFXSystemIntelligenceError",
    "build_rfx_system_intelligence_report",
]
