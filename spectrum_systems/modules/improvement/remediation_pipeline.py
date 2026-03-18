"""
Remediation Pipeline — spectrum_systems/modules/improvement/remediation_pipeline.py

Orchestrates the AW1 end-to-end mapping pipeline:

  1. Accept validated clusters from AW0.
  2. Map each to a RemediationPlan via RemediationMapper.
  3. Filter and rank plans by confidence and impact.
  4. Emit a summary of top remediation targets and proposed actions.

Public API
----------
build_remediation_plans_from_validated_clusters(validated_clusters, classification_records, taxonomy_catalog)
    -> List[RemediationPlan]

filter_mapped_plans(plans, *, status)
    -> List[RemediationPlan]

summarize_remediation_targets(plans)
    -> Dict[str, Any]
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from spectrum_systems.modules.improvement.remediation_mapping import (
    RemediationMapper,
    RemediationPlan,
)

if TYPE_CHECKING:
    from spectrum_systems.modules.error_taxonomy.cluster_validation import ValidatedCluster
    from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord
    from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------


def build_remediation_plans_from_validated_clusters(
    validated_clusters: List["ValidatedCluster"],
    classification_records: List["ErrorClassificationRecord"],
    taxonomy_catalog: Optional["ErrorTaxonomyCatalog"] = None,
) -> List[RemediationPlan]:
    """Map all validated clusters to RemediationPlan objects.

    Parameters
    ----------
    validated_clusters:
        Validated clusters from AW0 (all statuses are accepted; invalid ones
        are mapped to ``rejected`` plans).
    classification_records:
        All classification records available (used for confidence and dominant
        signal computation).
    taxonomy_catalog:
        Optional catalog used to embed taxonomy_version in plans.

    Returns
    -------
    List[RemediationPlan]
        One plan per input cluster, in the same order.
    """
    taxonomy_version = "unknown"
    if taxonomy_catalog is not None:
        taxonomy_version = getattr(taxonomy_catalog, "version", "unknown")

    mapper = RemediationMapper(taxonomy_version=taxonomy_version)
    return mapper.map_many(
        validated_clusters=validated_clusters,
        classification_records=classification_records,
        taxonomy_catalog=taxonomy_catalog,
    )


def filter_mapped_plans(
    plans: List[RemediationPlan],
    *,
    status: Optional[str] = None,
) -> List[RemediationPlan]:
    """Filter plans by mapping_status.

    Parameters
    ----------
    plans:
        All RemediationPlan objects to filter.
    status:
        If provided, return only plans whose ``mapping_status`` matches.
        Valid values: ``"mapped"``, ``"ambiguous"``, ``"rejected"``.
        If ``None``, all plans are returned.

    Returns
    -------
    List[RemediationPlan]
        Filtered plans, sorted by primary action confidence (descending).
    """
    filtered = plans if status is None else [p for p in plans if p.mapping_status == status]
    return sorted(
        filtered,
        key=lambda p: (
            -_primary_confidence(p),
            p.cluster_signature,
        ),
    )


def summarize_remediation_targets(
    plans: List[RemediationPlan],
) -> Dict[str, Any]:
    """Produce a ranked summary of remediation targets and proposed actions.

    Parameters
    ----------
    plans:
        All RemediationPlan objects to summarize.

    Returns
    -------
    Dict[str, Any]
        Summary dict with counts, top targets, and top proposed actions.
    """
    status_counter: Counter[str] = Counter(p.mapping_status for p in plans)
    target_counter: Counter[str] = Counter()
    action_type_counter: Counter[str] = Counter()
    top_actions_by_confidence: List[Dict[str, Any]] = []

    for plan in plans:
        for target in plan.remediation_targets:
            target_counter[target] += 1
        for action in plan.proposed_actions:
            action_type_counter[action["action_type"]] += 1
            top_actions_by_confidence.append(
                {
                    "cluster_signature": plan.cluster_signature,
                    "action_type": action["action_type"],
                    "target_component": action["target_component"],
                    "confidence_score": action["confidence_score"],
                    "risk_level": action["risk_level"],
                }
            )

    top_actions_by_confidence.sort(key=lambda x: -x["confidence_score"])

    return {
        "total_plans": len(plans),
        "mapped": status_counter.get("mapped", 0),
        "ambiguous": status_counter.get("ambiguous", 0),
        "rejected": status_counter.get("rejected", 0),
        "top_remediation_targets": dict(target_counter.most_common()),
        "top_action_types": dict(action_type_counter.most_common()),
        "top_proposed_actions": top_actions_by_confidence[:10],
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _primary_confidence(plan: RemediationPlan) -> float:
    """Return the confidence score of the primary proposed action."""
    if not plan.proposed_actions:
        return 0.0
    idx = min(plan.primary_proposal_index, len(plan.proposed_actions) - 1)
    return float(plan.proposed_actions[idx].get("confidence_score", 0.0))
