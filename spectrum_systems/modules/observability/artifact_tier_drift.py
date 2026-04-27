"""OBS: Artifact tier drift monitor (NT-07..09).

Extends the existing artifact tier audit with:

  * Transitive evidence tier validation: when a canonical wrapper artifact
    references downstream evidence (e.g., loop proof bundle → eval summary),
    the referenced evidence must also satisfy tier rules. Reports cannot be
    laundered through a canonical wrapper.
  * Tier-drift detection: tier changes between successive proof runs are
    flagged unless explicitly allowed by policy.
  * Missing tier metadata is an explicit, canonical block rather than a
    silent inference of ``evidence`` tier.

This module is non-owning. It returns a deterministic validation result for
canonical owners (CDE/SEL) to consume.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from spectrum_systems.modules.observability.artifact_tier_audit import (
    ArtifactTierError,
    classify_artifact,
    load_artifact_tier_policy,
)


CANONICAL_TIER_DRIFT_REASON_CODES = (
    "TIER_DRIFT_OK",
    "TIER_DRIFT_LOW_TO_EVIDENCE_UNAUTHORIZED",
    "TIER_DRIFT_METADATA_MISSING",
    "TIER_DRIFT_INDIRECT_EVIDENCE_LAUNDERING",
    "TIER_DRIFT_INFERRED_EVIDENCE_TIER",
    "TIER_DRIFT_CHANGED_BETWEEN_RUNS",
)


def validate_transitive_promotion_evidence_tiers(
    promotion_evidence_items: Iterable[Mapping[str, Any]],
    *,
    referenced_evidence_items: Optional[Iterable[Mapping[str, Any]]] = None,
    policy: Optional[Mapping[str, Any]] = None,
    validation_id: str,
    trace_id: str = "",
) -> Dict[str, Any]:
    """Tier-validate top-level promotion evidence AND any evidence those
    items transitively reference.

    A canonical wrapper artifact (``loop_proof_bundle``,
    ``certification_evidence_index``) cannot smuggle a low-tier artifact
    into promotion evidence by referencing it: each referenced evidence
    item must independently satisfy the allowlist tiers. Missing tier
    metadata blocks rather than being inferred as ``evidence``.
    """
    pol = dict(policy) if policy is not None else load_artifact_tier_policy()
    allow_tiers = set(
        pol.get("promotion_evidence_allowlist_tiers", ["canonical", "evidence"])
    )
    overrides = {str(o) for o in pol.get("explicit_promotion_overrides", []) or []}

    classified: List[Dict[str, Any]] = []
    blocking: List[str] = []
    decision = "allow"
    reason_code = "TIER_DRIFT_OK"
    counts: Dict[str, int] = {}

    def _block(new_reason: str, why: str) -> None:
        nonlocal decision, reason_code
        decision = "block"
        if reason_code == "TIER_DRIFT_OK":
            reason_code = new_reason
        blocking.append(why)

    def _check(item: Mapping[str, Any], depth: str) -> Dict[str, Any]:
        # Hard fail-closed: missing tier metadata is not silently inferred.
        explicit_tier = item.get("tier")
        artifact_id = item.get("artifact_id") or item.get("id") or "<unknown>"
        if explicit_tier is None and not item.get("artifact_path") and not item.get("artifact_type"):
            _block(
                "TIER_DRIFT_METADATA_MISSING",
                f"{depth} artifact {artifact_id} missing tier metadata "
                "(no tier, path, or type)",
            )
            return {
                "artifact_id": artifact_id,
                "tier": None,
                "tier_metadata_missing": True,
                "depth": depth,
            }
        cls = classify_artifact(item, pol)
        cls["depth"] = depth
        # If a tier was inferred from default_tier_when_unmatched fallback,
        # flag as inferred-evidence-tier when it lands in the allow tiers.
        had_no_explicit_tier = item.get("tier") is None
        had_unmatched = (
            had_no_explicit_tier
            and not item.get("artifact_path")
            and not item.get("artifact_type")
        )
        if had_unmatched and cls["tier"] in allow_tiers:
            _block(
                "TIER_DRIFT_INFERRED_EVIDENCE_TIER",
                f"{depth} artifact {artifact_id} inferred to tier "
                f"{cls['tier']!r} without explicit metadata",
            )

        tier = cls["tier"]
        counts[tier] = counts.get(tier, 0) + 1
        if tier in allow_tiers or artifact_id in overrides:
            return cls
        # Tier violation
        if depth == "transitive":
            _block(
                "TIER_DRIFT_INDIRECT_EVIDENCE_LAUNDERING",
                f"transitive evidence {artifact_id} is tier={tier!r}; "
                "wrapping a low-tier artifact in a canonical reference is forbidden",
            )
        else:
            _block(
                "TIER_DRIFT_LOW_TO_EVIDENCE_UNAUTHORIZED",
                f"top-level evidence {artifact_id} is tier={tier!r}",
            )
        return cls

    for item in promotion_evidence_items:
        if not isinstance(item, Mapping):
            continue
        classified.append(_check(item, "top"))

    if referenced_evidence_items:
        for item in referenced_evidence_items:
            if not isinstance(item, Mapping):
                continue
            classified.append(_check(item, "transitive"))

    return {
        "artifact_type": "artifact_tier_drift_validation_result",
        "schema_version": "1.0.0",
        "validation_id": validation_id,
        "trace_id": trace_id,
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "tier_counts": counts,
        "items": classified,
    }


def detect_tier_drift(
    previous_validation: Optional[Mapping[str, Any]],
    current_validation: Mapping[str, Any],
) -> Dict[str, Any]:
    """Compare two tier validation results (across two proof runs) and
    flag artifacts whose tier changed.

    A previous validation that is missing is treated as ``unknown
    baseline`` rather than an automatic pass.

    Returns a drift summary with:
      drift_status: ``ok`` | ``drift`` | ``unknown_baseline``
      drifted: [{artifact_id, previous_tier, current_tier}, ...]
      blocking_reasons: [str, ...]
    """
    if not isinstance(current_validation, Mapping):
        raise ArtifactTierError("current_validation must be a mapping")

    if previous_validation is None:
        return {
            "artifact_type": "artifact_tier_drift_summary",
            "schema_version": "1.0.0",
            "drift_status": "unknown_baseline",
            "reason_code": "TIER_DRIFT_OK",
            "drifted": [],
            "blocking_reasons": ["no previous validation; baseline unknown"],
        }

    prev_items = {
        str(it.get("artifact_id")): it
        for it in (previous_validation.get("items") or [])
        if isinstance(it, Mapping)
    }
    curr_items = {
        str(it.get("artifact_id")): it
        for it in (current_validation.get("items") or [])
        if isinstance(it, Mapping)
    }
    drifted: List[Dict[str, Any]] = []
    blocking: List[str] = []

    for aid, curr in curr_items.items():
        prev = prev_items.get(aid)
        if prev is None:
            continue
        if str(prev.get("tier") or "") != str(curr.get("tier") or ""):
            drifted.append(
                {
                    "artifact_id": aid,
                    "previous_tier": prev.get("tier"),
                    "current_tier": curr.get("tier"),
                }
            )
            blocking.append(
                f"artifact {aid} tier changed: "
                f"{prev.get('tier')!r} -> {curr.get('tier')!r}"
            )

    if drifted:
        return {
            "artifact_type": "artifact_tier_drift_summary",
            "schema_version": "1.0.0",
            "drift_status": "drift",
            "reason_code": "TIER_DRIFT_CHANGED_BETWEEN_RUNS",
            "drifted": drifted,
            "blocking_reasons": blocking,
        }

    return {
        "artifact_type": "artifact_tier_drift_summary",
        "schema_version": "1.0.0",
        "drift_status": "ok",
        "reason_code": "TIER_DRIFT_OK",
        "drifted": [],
        "blocking_reasons": [],
    }


__all__ = [
    "CANONICAL_TIER_DRIFT_REASON_CODES",
    "detect_tier_drift",
    "validate_transitive_promotion_evidence_tiers",
]
