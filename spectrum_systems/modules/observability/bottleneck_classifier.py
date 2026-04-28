"""OC-04..06: Bottleneck classifier (non-owning support seam).

Reads observed failure findings and maps them to one canonical category:

    eval | replay | lineage | context_admission | registry | slo |
    certification | authority_shape | dashboard | unknown

Each category points to the existing 3-letter system that owns the seam
in ``docs/architecture/system_registry.md`` — no new authorities are
added. The classifier emits:

  * ``category``
  * ``owning_system`` (from canonical registry)
  * ``reason_code`` (canonical)
  * ``evidence_artifact_ref`` (the artifact that surfaced the finding)
  * ``confidence`` (low / medium / high)
  * ``next_safe_action`` (block / freeze / warn / investigate / ...)

Precedence is fixed and deterministic so identical inputs always
yield the same classification, even when the input findings touch
multiple seams. Ambiguity is reported (not silently picked) and the
``next_safe_action`` defaults to ``block`` so fail-closed behaviour
is preserved.

Module is non-owning. Canonical authority unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


# Fixed precedence: registry & authority_shape come first because they
# are upstream of every other seam. Eval, replay, lineage are next
# because they gate certification. Then context_admission, slo, then
# certification (which depends on the previous seams), then dashboard
# (a projection layer), and finally unknown.
CATEGORY_PRECEDENCE: Tuple[str, ...] = (
    "registry",
    "authority_shape",
    "eval",
    "replay",
    "lineage",
    "context_admission",
    "slo",
    "certification",
    "dashboard",
    "unknown",
)


CATEGORY_TO_OWNER: Dict[str, str] = {
    "eval": "EVL",
    "replay": "REP",
    "lineage": "LIN",
    "context_admission": "CTX",
    "registry": "MAP",
    "slo": "SLO",
    "certification": "GOV",
    "authority_shape": "GOV",
    "dashboard": "MAP",
    "unknown": "MAP",
}


CANONICAL_REASON_CODES = frozenset(
    {
        "BOTTLENECK_EVAL_FAILED",
        "BOTTLENECK_EVAL_COVERAGE_GAP",
        "BOTTLENECK_REPLAY_DIVERGENCE",
        "BOTTLENECK_LINEAGE_GAP",
        "BOTTLENECK_CONTEXT_ADMISSION_BLOCKED",
        "BOTTLENECK_REGISTRY_DRIFT",
        "BOTTLENECK_REGISTRY_VIOLATION",
        "BOTTLENECK_SLO_BURN",
        "BOTTLENECK_CERTIFICATION_NOT_READY",
        "BOTTLENECK_CERTIFICATION_FROZEN",
        "BOTTLENECK_AUTHORITY_SHAPE_LEAK",
        "BOTTLENECK_DASHBOARD_DRIFT",
        "BOTTLENECK_AMBIGUOUS",
        "BOTTLENECK_UNKNOWN",
    }
)


# Keywords mapped to a canonical category. Order does not matter here —
# the precedence above is what disambiguates collisions.
KEYWORD_HINTS: Dict[str, str] = {
    "eval": "eval",
    "evaluation": "eval",
    "evl": "eval",
    "replay": "replay",
    "rep_": "replay",
    "lineage": "lineage",
    "lin_": "lineage",
    "context": "context_admission",
    "context_admission": "context_admission",
    "ctx_": "context_admission",
    "registry": "registry",
    "system_registry": "registry",
    "three_letter": "registry",
    "slo": "slo",
    "burn_rate": "slo",
    "error_budget": "slo",
    "certification": "certification",
    "gov_": "certification",
    "authority_shape": "authority_shape",
    "authority_leak": "authority_shape",
    "ags_001": "authority_shape",
    "dashboard": "dashboard",
    "public_proof": "dashboard",
    "dashboard_drift": "dashboard",
}


CATEGORY_DEFAULT_REASON_CODE: Dict[str, str] = {
    "eval": "BOTTLENECK_EVAL_FAILED",
    "replay": "BOTTLENECK_REPLAY_DIVERGENCE",
    "lineage": "BOTTLENECK_LINEAGE_GAP",
    "context_admission": "BOTTLENECK_CONTEXT_ADMISSION_BLOCKED",
    "registry": "BOTTLENECK_REGISTRY_DRIFT",
    "slo": "BOTTLENECK_SLO_BURN",
    "certification": "BOTTLENECK_CERTIFICATION_NOT_READY",
    "authority_shape": "BOTTLENECK_AUTHORITY_SHAPE_LEAK",
    "dashboard": "BOTTLENECK_DASHBOARD_DRIFT",
    "unknown": "BOTTLENECK_UNKNOWN",
}


CATEGORY_DEFAULT_ACTION: Dict[str, str] = {
    "eval": "block",
    "replay": "block",
    "lineage": "block",
    "context_admission": "block",
    "registry": "block",
    "slo": "freeze",
    "certification": "block",
    "authority_shape": "block",
    "dashboard": "warn",
    "unknown": "investigate",
}


class BottleneckClassifierError(ValueError):
    """Raised when the classifier cannot be deterministically built."""


def _category_from_finding(finding: Mapping[str, Any]) -> Optional[str]:
    explicit = finding.get("category")
    if isinstance(explicit, str) and explicit.strip():
        if explicit in CATEGORY_TO_OWNER:
            return explicit
    text_fields: List[str] = []
    for key in ("reason_code", "kind", "owner_hint", "source", "summary"):
        v = finding.get(key)
        if isinstance(v, str):
            text_fields.append(v.lower())
    blob = " ".join(text_fields)
    for keyword, category in KEYWORD_HINTS.items():
        if keyword in blob:
            return category
    return None


def _evidence_ref(finding: Mapping[str, Any]) -> Optional[str]:
    for key in ("evidence_ref", "artifact_ref", "artifact_id", "id"):
        v = finding.get(key)
        if isinstance(v, str) and v.strip():
            return v
    return None


def classify_bottleneck(
    *,
    classification_id: str,
    findings: Sequence[Mapping[str, Any]],
    audit_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Deterministically classify the current blocker.

    ``findings`` is a list of dict-like observations. Empty findings
    yield an ``unknown`` classification with the safe action
    ``investigate`` so the operator does not get a false ``allow``.
    """
    if not isinstance(classification_id, str) or not classification_id.strip():
        raise BottleneckClassifierError(
            "classification_id must be a non-empty string"
        )

    matched_categories: Dict[str, List[Mapping[str, Any]]] = {}
    for f in findings:
        if not isinstance(f, Mapping):
            continue
        cat = _category_from_finding(f)
        if cat is None:
            continue
        matched_categories.setdefault(cat, []).append(f)

    # apply precedence
    chosen_category: Optional[str] = None
    for cat in CATEGORY_PRECEDENCE:
        if cat in matched_categories:
            chosen_category = cat
            break

    ambiguous = len(matched_categories) > 1
    ambiguity_candidates: List[Dict[str, str]] = []
    if ambiguous:
        for cat in CATEGORY_PRECEDENCE:
            if cat in matched_categories and cat != chosen_category:
                rep = matched_categories[cat][0]
                rc = rep.get("reason_code")
                if not isinstance(rc, str) or not rc.strip():
                    rc = CATEGORY_DEFAULT_REASON_CODE.get(cat, "BOTTLENECK_UNKNOWN")
                ambiguity_candidates.append(
                    {
                        "category": cat,
                        "owning_system": CATEGORY_TO_OWNER[cat],
                        "reason_code": rc,
                    }
                )

    if chosen_category is None:
        chosen_category = "unknown"
        confidence = "low"
        reason_code = CATEGORY_DEFAULT_REASON_CODE["unknown"]
        action = CATEGORY_DEFAULT_ACTION["unknown"]
        evidence_ref = None
    else:
        primary_findings = matched_categories[chosen_category]
        primary = primary_findings[0]
        reason_code = primary.get("reason_code")
        if not isinstance(reason_code, str) or not reason_code.strip():
            reason_code = CATEGORY_DEFAULT_REASON_CODE[chosen_category]
        if reason_code not in CANONICAL_REASON_CODES:
            # unknown reason codes are allowed but trigger ambiguity
            ambiguous = True
            reason_code = CATEGORY_DEFAULT_REASON_CODE[chosen_category]
        evidence_ref = _evidence_ref(primary)
        if ambiguous:
            confidence = "low"
        elif len(primary_findings) >= 2:
            confidence = "high"
        else:
            confidence = "medium"
        action = CATEGORY_DEFAULT_ACTION[chosen_category]
        if ambiguous:
            action = "block"
            reason_code = "BOTTLENECK_AMBIGUOUS"

    rationale = (
        f"category={chosen_category}; ambiguous={ambiguous}; "
        f"reason_code={reason_code}"
    )

    return {
        "artifact_type": "bottleneck_classification",
        "schema_version": "1.0.0",
        "classification_id": classification_id,
        "audit_timestamp": audit_timestamp or "",
        "category": chosen_category,
        "owning_system": CATEGORY_TO_OWNER[chosen_category],
        "reason_code": reason_code,
        "evidence_artifact_ref": evidence_ref,
        "confidence": confidence,
        "ambiguous": ambiguous,
        "ambiguity_candidates": ambiguity_candidates,
        "next_safe_action": {
            "action": action,
            "rationale": rationale,
        },
        "non_authority_assertions": [
            "preparatory_only",
            "not_control_authority",
            "not_certification_authority",
            "not_enforcement_authority",
        ],
    }
