"""
Remediation Mapping Engine — spectrum_systems/modules/improvement/remediation_mapping.py

Implements the AW1 layer that converts VALIDATED failure clusters (from AW0)
into specific, auditable proposed fixes.  No fixes are applied; this module
only proposes candidate interventions for later simulation in AW2.

Design principles
-----------------
- Only clusters with ``validation_status == "valid"`` may be mapped.
- Mapping is fully deterministic and rule-based (no LLM, no ML).
- At most 2 proposed actions per cluster.
- Ambiguous clusters (no clear dominant signal) remain ambiguous.
- Every decision is explicitly recorded in ``mapping_reasons``.

Mapping rules
-------------
A. GROUND.* dominant      → grounding_rule_change / grounding_verifier
B. EXTRACT.MISSED_DECISION or EXTRACT.MISSED_ACTION_ITEM dominant
                          → prompt_change / decision_extraction_prompt or
                            action_item_extraction_prompt
C. SCHEMA.INVALID_OUTPUT  → schema_change / output_schema_contract
D. INPUT.BAD_TRANSCRIPT_QUALITY → input_quality_rule_change / transcript_preprocessing_rules
E. RETRIEVE.* dominant    → retrieval_change / retrieval_selection_rules
F. HUMAN.NEEDS_SUPPORT + GROUND.WEAK_SUPPORT → grounding_rule_change / synthesis_grounding_rules
G. Mixed / no clear dominant → ambiguous / no_action

Public API
----------
RemediationPlan
    In-memory, schema-validated output of one mapping run.

RemediationMapper
    Maps ValidatedCluster objects to RemediationPlan objects.
"""
from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import jsonschema

from spectrum_systems.modules.improvement.target_registry import (
    KNOWN_TARGET_COMPONENTS,
    validate_target_component,
)

if TYPE_CHECKING:
    from spectrum_systems.modules.error_taxonomy.cluster_validation import ValidatedCluster
    from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord
    from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog

# ---------------------------------------------------------------------------
# Schema path
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "remediation_plan.schema.json"
)

# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------

_HIGH_COHESION: float = 0.75
_HIGH_ACTIONABILITY: float = 0.75
_DOMINANT_SHARE_THRESHOLD: float = 0.6


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def compute_mapping_confidence(
    cohesion_score: float,
    actionability_score: float,
    avg_confidence: float,
    dominant_share: float,
) -> float:
    """Compute a deterministic mapping confidence score in [0, 1].

    High confidence requires all four inputs to be strong.  Otherwise the
    score is degraded proportionally so uncertainty is preserved.

    Parameters
    ----------
    cohesion_score:
        Cluster cohesion from ValidatedCluster (0–1).
    actionability_score:
        Cluster actionability from ValidatedCluster (0–1).
    avg_confidence:
        Average classification confidence of the cluster's records (0–1).
    dominant_share:
        Fraction of error code occurrences belonging to the dominant code (0–1).

    Returns
    -------
    float
        Confidence score rounded to 4 decimal places.
    """
    raw = (cohesion_score + actionability_score + avg_confidence + dominant_share) / 4.0
    return round(min(max(raw, 0.0), 1.0), 4)


def compute_risk_level(action_type: str, confidence_score: float) -> str:
    """Return a deterministic risk level string for a proposed action.

    Parameters
    ----------
    action_type:
        One of the valid action_type enum values.
    confidence_score:
        Mapping confidence for this action (0–1).

    Returns
    -------
    str
        ``"low"``, ``"medium"``, or ``"high"``.
    """
    base: Dict[str, str] = {
        "schema_change": "high",
        "prompt_change": "medium",
        "grounding_rule_change": "medium",
        "input_quality_rule_change": "low",
        "retrieval_change": "medium",
        "observability_change": "low",
        "no_action": "low",
    }
    level = base.get(action_type, "medium")
    # Degrade risk upward when confidence is low, preserve otherwise
    if confidence_score < 0.5 and level == "low":
        level = "medium"
    elif confidence_score < 0.4 and level == "medium":
        level = "high"
    return level


# ---------------------------------------------------------------------------
# RemediationPlan
# ---------------------------------------------------------------------------


class RemediationPlan:
    """In-memory representation of one remediation mapping result.

    Parameters
    ----------
    remediation_id:
        Unique identifier for this plan.
    cluster_id:
        ID of the source ValidatedCluster.
    cluster_signature:
        Primary error code string that identifies the source cluster.
    taxonomy_version:
        Version of the error taxonomy catalog used when mapping.
    created_at:
        ISO-8601 timestamp.
    mapping_status:
        ``"mapped"``, ``"ambiguous"``, or ``"rejected"``.
    mapping_reasons:
        Auditable reasons explaining every mapping decision.
    dominant_error_codes:
        Error codes that dominated the mapping signal.
    remediation_targets:
        Canonical target components identified for remediation.
    proposed_actions:
        List of up to 2 proposed action dicts (schema-validated).
    primary_proposal_index:
        Index of the top-ranked action in proposed_actions.
    evidence_summary:
        Aggregate evidence metrics dict.
    """

    def __init__(
        self,
        *,
        remediation_id: str,
        cluster_id: str,
        cluster_signature: str,
        taxonomy_version: str,
        created_at: str,
        mapping_status: str,
        mapping_reasons: List[str],
        dominant_error_codes: List[str],
        remediation_targets: List[str],
        proposed_actions: List[Dict[str, Any]],
        primary_proposal_index: int,
        evidence_summary: Dict[str, Any],
    ) -> None:
        self.remediation_id = remediation_id
        self.cluster_id = cluster_id
        self.cluster_signature = cluster_signature
        self.taxonomy_version = taxonomy_version
        self.created_at = created_at
        self.mapping_status = mapping_status
        self.mapping_reasons = mapping_reasons
        self.dominant_error_codes = dominant_error_codes
        self.remediation_targets = remediation_targets
        self.proposed_actions = proposed_actions
        self.primary_proposal_index = primary_proposal_index
        self.evidence_summary = evidence_summary

    # --- Serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "remediation_id": self.remediation_id,
            "cluster_id": self.cluster_id,
            "cluster_signature": self.cluster_signature,
            "taxonomy_version": self.taxonomy_version,
            "created_at": self.created_at,
            "mapping_status": self.mapping_status,
            "mapping_reasons": self.mapping_reasons,
            "dominant_error_codes": self.dominant_error_codes,
            "remediation_targets": self.remediation_targets,
            "proposed_actions": self.proposed_actions,
            "primary_proposal_index": self.primary_proposal_index,
            "evidence_summary": self.evidence_summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RemediationPlan":
        return cls(
            remediation_id=data["remediation_id"],
            cluster_id=data["cluster_id"],
            cluster_signature=data["cluster_signature"],
            taxonomy_version=data["taxonomy_version"],
            created_at=data["created_at"],
            mapping_status=data["mapping_status"],
            mapping_reasons=data["mapping_reasons"],
            dominant_error_codes=data["dominant_error_codes"],
            remediation_targets=data["remediation_targets"],
            proposed_actions=data["proposed_actions"],
            primary_proposal_index=data["primary_proposal_index"],
            evidence_summary=data["evidence_summary"],
        )

    # --- Schema validation ---------------------------------------------------

    def validate_against_schema(self) -> List[str]:
        """Validate this object against the JSON Schema.

        Returns
        -------
        List[str]
            List of validation error messages.  Empty list means valid.
        """
        if not _SCHEMA_PATH.exists():
            return [f"Schema file not found: {_SCHEMA_PATH}"]
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        errors: List[str] = []
        for err in jsonschema.Draft202012Validator(schema).iter_errors(self.to_dict()):
            errors.append(err.message)
        return errors


# ---------------------------------------------------------------------------
# RemediationMapper
# ---------------------------------------------------------------------------


class RemediationMapper:
    """Maps ValidatedCluster objects to RemediationPlan objects.

    Parameters
    ----------
    taxonomy_version:
        Version string of the error taxonomy catalog.  Embedded in every plan.
    """

    def __init__(self, taxonomy_version: str = "unknown") -> None:
        self._taxonomy_version = taxonomy_version

    # --- Public API ----------------------------------------------------------

    def map_validated_cluster(
        self,
        validated_cluster: "ValidatedCluster",
        classification_records: List["ErrorClassificationRecord"],
    ) -> RemediationPlan:
        """Map one validated cluster to a RemediationPlan.

        Parameters
        ----------
        validated_cluster:
            A ``ValidatedCluster`` object from AW0.
        classification_records:
            Classification records belonging to this cluster (used for
            avg_confidence and dominant-share computation).

        Returns
        -------
        RemediationPlan
            A new RemediationPlan.  The original cluster is not modified.
        """
        # Gate: only valid clusters may be mapped
        if validated_cluster.validation_status != "valid":
            return self._build_rejected_plan(validated_cluster)

        # Compute evidence
        avg_confidence = self._compute_avg_confidence(classification_records)
        dominant_code, dominant_share = self._compute_dominant_signal(
            validated_cluster, classification_records
        )

        # Build evidence summary
        evidence_summary = {
            "record_count": validated_cluster.record_count,
            "avg_cluster_confidence": round(avg_confidence, 4),
            "weighted_severity_score": 0.0,
            "pass_types": list(validated_cluster.pass_types),
        }

        # Determine mapping
        return self._apply_mapping_rules(
            validated_cluster=validated_cluster,
            dominant_code=dominant_code,
            dominant_share=dominant_share,
            avg_confidence=avg_confidence,
            evidence_summary=evidence_summary,
        )

    def map_many(
        self,
        validated_clusters: List["ValidatedCluster"],
        classification_records: List["ErrorClassificationRecord"],
        taxonomy_catalog: Optional["ErrorTaxonomyCatalog"] = None,
    ) -> List[RemediationPlan]:
        """Map a list of validated clusters to RemediationPlan objects.

        Parameters
        ----------
        validated_clusters:
            All ``ValidatedCluster`` objects to map.
        classification_records:
            All classification records (indexed internally by cluster).
        taxonomy_catalog:
            Optional catalog used to enrich taxonomy_version.

        Returns
        -------
        List[RemediationPlan]
            One plan per input cluster, in the same order.
        """
        if taxonomy_catalog is not None:
            self._taxonomy_version = getattr(taxonomy_catalog, "version", self._taxonomy_version)

        # Build index: cluster_id → records
        record_index: Dict[str, List["ErrorClassificationRecord"]] = {}
        for rec in classification_records:
            for cluster in validated_clusters:
                if hasattr(cluster, "record_ids") and cluster.record_ids:
                    if rec.classification_id in set(cluster.record_ids):
                        record_index.setdefault(cluster.cluster_id, []).append(rec)

        plans: List[RemediationPlan] = []
        for vc in validated_clusters:
            records = record_index.get(vc.cluster_id, [])
            plans.append(self.map_validated_cluster(vc, records))
        return plans

    # --- Mapping rules -------------------------------------------------------

    def _apply_mapping_rules(
        self,
        *,
        validated_cluster: "ValidatedCluster",
        dominant_code: str,
        dominant_share: float,
        avg_confidence: float,
        evidence_summary: Dict[str, Any],
    ) -> RemediationPlan:
        """Apply deterministic mapping rules and return a RemediationPlan."""
        reasons: List[str] = []
        error_codes = validated_cluster.error_codes
        family = dominant_code.split(".")[0] if "." in dominant_code else dominant_code

        confidence = compute_mapping_confidence(
            cohesion_score=validated_cluster.cohesion_score,
            actionability_score=validated_cluster.actionability_score,
            avg_confidence=avg_confidence,
            dominant_share=dominant_share,
        )

        # ── Rule A: GROUND.* ─────────────────────────────────────────────
        if family == "GROUND" and dominant_share >= _DOMINANT_SHARE_THRESHOLD:
            reasons.append(
                f"rule_A: dominant GROUND family code {dominant_code!r} "
                f"with share={dominant_share:.3f}"
            )
            # Sub-rule F: HUMAN.NEEDS_SUPPORT co-present with GROUND.WEAK_SUPPORT
            has_human_needs = any("HUMAN.NEEDS_SUPPORT" in c for c in error_codes)
            has_weak_support = any("GROUND.WEAK_SUPPORT" in c for c in error_codes)
            if has_human_needs and has_weak_support:
                reasons.append(
                    "rule_F: HUMAN.NEEDS_SUPPORT + GROUND.WEAK_SUPPORT co-present "
                    "→ target synthesis_grounding_rules"
                )
                target = validate_target_component("synthesis_grounding_rules")
            else:
                target = validate_target_component("grounding_verifier")

            action = self._build_action(
                action_type="grounding_rule_change",
                target_component=target,
                rationale=(
                    f"Dominant error family is GROUND ({dominant_code}, share={dominant_share:.2f}). "
                    "Grounding rules need tightening to reduce missing or weak references."
                ),
                expected_benefit="Reduce GROUND-family errors by enforcing stricter reference constraints.",
                confidence=confidence,
            )
            return self._build_mapped_plan(
                validated_cluster=validated_cluster,
                dominant_code=dominant_code,
                actions=[action],
                reasons=reasons,
                evidence_summary=evidence_summary,
            )

        # ── Rule B: EXTRACT.MISSED_DECISION / EXTRACT.MISSED_ACTION_ITEM ──
        if dominant_code in ("EXTRACT.MISSED_DECISION", "EXTRACT.MISSED_ACTION_ITEM"):
            reasons.append(
                f"rule_B: dominant extraction miss code {dominant_code!r} "
                f"with share={dominant_share:.3f}"
            )
            if dominant_code == "EXTRACT.MISSED_DECISION":
                target = validate_target_component("decision_extraction_prompt")
            else:
                target = validate_target_component("action_item_extraction_prompt")

            action = self._build_action(
                action_type="prompt_change",
                target_component=target,
                rationale=(
                    f"Dominant error {dominant_code!r} indicates the extraction prompt "
                    "is failing to capture required items."
                ),
                expected_benefit="Improve extraction recall by revising the relevant extraction prompt.",
                confidence=confidence,
            )
            return self._build_mapped_plan(
                validated_cluster=validated_cluster,
                dominant_code=dominant_code,
                actions=[action],
                reasons=reasons,
                evidence_summary=evidence_summary,
            )

        # ── Rule C: SCHEMA.INVALID_OUTPUT ───────────────────────────────
        if dominant_code == "SCHEMA.INVALID_OUTPUT" and dominant_share >= _DOMINANT_SHARE_THRESHOLD:
            reasons.append(
                f"rule_C: dominant SCHEMA.INVALID_OUTPUT "
                f"with share={dominant_share:.3f}"
            )
            target = validate_target_component("output_schema_contract")
            action = self._build_action(
                action_type="schema_change",
                target_component=target,
                rationale=(
                    "Dominant error SCHEMA.INVALID_OUTPUT indicates the output contract "
                    "does not match what the pipeline actually produces."
                ),
                expected_benefit="Eliminate schema validation failures by aligning the output contract.",
                confidence=confidence,
            )
            return self._build_mapped_plan(
                validated_cluster=validated_cluster,
                dominant_code=dominant_code,
                actions=[action],
                reasons=reasons,
                evidence_summary=evidence_summary,
            )

        # ── Rule D: INPUT.BAD_TRANSCRIPT_QUALITY ────────────────────────
        if dominant_code == "INPUT.BAD_TRANSCRIPT_QUALITY" and dominant_share >= _DOMINANT_SHARE_THRESHOLD:
            reasons.append(
                f"rule_D: dominant INPUT.BAD_TRANSCRIPT_QUALITY "
                f"with share={dominant_share:.3f}"
            )
            target = validate_target_component("transcript_preprocessing_rules")
            action = self._build_action(
                action_type="input_quality_rule_change",
                target_component=target,
                rationale=(
                    "Dominant error INPUT.BAD_TRANSCRIPT_QUALITY indicates poor-quality "
                    "transcripts are reaching the pipeline without quality gating."
                ),
                expected_benefit="Block or flag low-quality transcripts before processing.",
                confidence=confidence,
            )
            return self._build_mapped_plan(
                validated_cluster=validated_cluster,
                dominant_code=dominant_code,
                actions=[action],
                reasons=reasons,
                evidence_summary=evidence_summary,
            )

        # ── Rule E: RETRIEVE.* ──────────────────────────────────────────
        if family == "RETRIEVE" and dominant_share >= _DOMINANT_SHARE_THRESHOLD:
            reasons.append(
                f"rule_E: dominant RETRIEVE family code {dominant_code!r} "
                f"with share={dominant_share:.3f}"
            )
            target = validate_target_component("retrieval_selection_rules")
            action = self._build_action(
                action_type="retrieval_change",
                target_component=target,
                rationale=(
                    f"Dominant error family is RETRIEVE ({dominant_code}). "
                    "Retrieval selection rules need updating to surface more relevant context."
                ),
                expected_benefit="Reduce retrieval errors by refining selection and ranking rules.",
                confidence=confidence,
            )
            return self._build_mapped_plan(
                validated_cluster=validated_cluster,
                dominant_code=dominant_code,
                actions=[action],
                reasons=reasons,
                evidence_summary=evidence_summary,
            )

        # ── Rule F (standalone): HUMAN.NEEDS_SUPPORT + GROUND.WEAK_SUPPORT
        has_human_needs = any("HUMAN.NEEDS_SUPPORT" in c for c in error_codes)
        has_weak_support = any("GROUND.WEAK_SUPPORT" in c for c in error_codes)
        if has_human_needs and has_weak_support:
            reasons.append(
                "rule_F: HUMAN.NEEDS_SUPPORT + GROUND.WEAK_SUPPORT co-present "
                "without a single dominant code → target synthesis_grounding_rules"
            )
            target = validate_target_component("synthesis_grounding_rules")
            action = self._build_action(
                action_type="grounding_rule_change",
                target_component=target,
                rationale=(
                    "Co-occurrence of HUMAN.NEEDS_SUPPORT and GROUND.WEAK_SUPPORT indicates "
                    "the synthesis layer is not enforcing sufficient evidence requirements."
                ),
                expected_benefit="Require stronger evidence before synthesis proceeds.",
                confidence=confidence,
            )
            return self._build_mapped_plan(
                validated_cluster=validated_cluster,
                dominant_code=dominant_code,
                actions=[action],
                reasons=reasons,
                evidence_summary=evidence_summary,
            )

        # ── Rule G: Ambiguous ───────────────────────────────────────────
        reasons.append(
            f"rule_G: no clear dominant target (dominant_code={dominant_code!r}, "
            f"share={dominant_share:.3f}, family={family!r}) → ambiguous"
        )
        no_action = self._build_action(
            action_type="no_action",
            target_component=validate_target_component("none"),
            rationale=(
                "No clear dominant error signal identified. "
                "Mixed cluster requires further investigation before intervention."
            ),
            expected_benefit="None — ambiguous clusters are not acted upon.",
            confidence=confidence,
        )
        return RemediationPlan(
            remediation_id=str(uuid.uuid4()),
            cluster_id=validated_cluster.cluster_id,
            cluster_signature=validated_cluster.cluster_signature,
            taxonomy_version=self._taxonomy_version,
            created_at=datetime.now(timezone.utc).isoformat(),
            mapping_status="ambiguous",
            mapping_reasons=reasons,
            dominant_error_codes=[dominant_code] if dominant_code else [],
            remediation_targets=[],
            proposed_actions=[no_action],
            primary_proposal_index=0,
            evidence_summary=evidence_summary,
        )

    # --- Plan builders -------------------------------------------------------

    def _build_mapped_plan(
        self,
        *,
        validated_cluster: "ValidatedCluster",
        dominant_code: str,
        actions: List[Dict[str, Any]],
        reasons: List[str],
        evidence_summary: Dict[str, Any],
    ) -> RemediationPlan:
        targets = [a["target_component"] for a in actions if a["target_component"] != "none"]
        return RemediationPlan(
            remediation_id=str(uuid.uuid4()),
            cluster_id=validated_cluster.cluster_id,
            cluster_signature=validated_cluster.cluster_signature,
            taxonomy_version=self._taxonomy_version,
            created_at=datetime.now(timezone.utc).isoformat(),
            mapping_status="mapped",
            mapping_reasons=reasons,
            dominant_error_codes=[dominant_code] if dominant_code else [],
            remediation_targets=targets,
            proposed_actions=actions,
            primary_proposal_index=0,
            evidence_summary=evidence_summary,
        )

    def _build_rejected_plan(
        self,
        validated_cluster: "ValidatedCluster",
    ) -> RemediationPlan:
        return RemediationPlan(
            remediation_id=str(uuid.uuid4()),
            cluster_id=validated_cluster.cluster_id,
            cluster_signature=validated_cluster.cluster_signature,
            taxonomy_version=self._taxonomy_version,
            created_at=datetime.now(timezone.utc).isoformat(),
            mapping_status="rejected",
            mapping_reasons=[
                f"cluster_rejected: validation_status={validated_cluster.validation_status!r}; "
                "only valid clusters may be mapped"
            ],
            dominant_error_codes=[],
            remediation_targets=[],
            proposed_actions=[
                self._build_action(
                    action_type="no_action",
                    target_component=validate_target_component("none"),
                    rationale="Cluster failed AW0 validation gate.",
                    expected_benefit="None.",
                    confidence=0.0,
                )
            ],
            primary_proposal_index=0,
            evidence_summary={
                "record_count": validated_cluster.record_count,
                "avg_cluster_confidence": 0.0,
                "weighted_severity_score": 0.0,
                "pass_types": list(validated_cluster.pass_types),
            },
        )

    # --- Action builder -------------------------------------------------------

    def _build_action(
        self,
        *,
        action_type: str,
        target_component: str,
        rationale: str,
        expected_benefit: str,
        confidence: float,
    ) -> Dict[str, Any]:
        return {
            "action_id": str(uuid.uuid4()),
            "action_type": action_type,
            "target_component": target_component,
            "rationale": rationale,
            "expected_benefit": expected_benefit,
            "risk_level": compute_risk_level(action_type, confidence),
            "confidence_score": round(confidence, 4),
        }

    # --- Signal helpers -------------------------------------------------------

    @staticmethod
    def _compute_dominant_signal(
        validated_cluster: "ValidatedCluster",
        classification_records: List["ErrorClassificationRecord"],
    ) -> tuple[str, float]:
        """Return (dominant_error_code, share_fraction).

        Falls back to cluster signature when no live records are available.
        """
        if classification_records:
            code_counts: Counter[str] = Counter()
            for rec in classification_records:
                for entry in rec.classifications:
                    code_counts[entry["error_code"]] += 1
            if code_counts:
                total = sum(code_counts.values())
                dominant_code, dominant_count = code_counts.most_common(1)[0]
                return dominant_code, round(dominant_count / total, 4)

        # Fallback to cluster signature
        dominant_code = validated_cluster.cluster_signature
        # Use cohesion_score as a proxy for dominant share
        return dominant_code, validated_cluster.cohesion_score

    @staticmethod
    def _compute_avg_confidence(
        classification_records: List["ErrorClassificationRecord"],
    ) -> float:
        confidences: List[float] = []
        for rec in classification_records:
            for entry in rec.classifications:
                confidences.append(float(entry.get("confidence", 1.0)))
        if not confidences:
            return 0.0
        return sum(confidences) / len(confidences)
