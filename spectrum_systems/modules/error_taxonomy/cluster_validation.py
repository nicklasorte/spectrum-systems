"""
Cluster Validation — spectrum_systems/modules/error_taxonomy/cluster_validation.py

Implements the AW0 Cluster Validation Layer that sits between AV (auto-failure
clustering) and AW (prompt improvement loop).  Only high-quality, stable, and
actionable clusters pass through to drive system changes.

Design principles
-----------------
- Fully deterministic: same input → same output, every time.
- No ML / embeddings.
- Full traceability: every validation decision is explicitly explained.
- Do not modify original ErrorCluster objects.
- All validation logic is rule-based and auditable.

Validation rules
----------------
A. SIZE CHECK        — cluster must have ≥ 3 records
B. COHESION CHECK    — dominant error_code must account for ≥ 60 % of codes
C. PASS CONSISTENCY  — cluster must not span > 3 distinct pass_types
D. STABILITY CHECK   — recomputed signature must match stored signature
E. ACTIONABILITY     — must map to ≤ 2 remediation_targets
F. CONFIDENCE CHECK  — average classification confidence must be ≥ 0.6

Public API
----------
ValidatedCluster
    In-memory, schema-validated output of one validation run.

ClusterValidator
    Validates ErrorCluster objects against the six quality rules.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import jsonschema

if TYPE_CHECKING:
    from spectrum_systems.modules.error_taxonomy.clustering import ErrorCluster
    from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord

# ---------------------------------------------------------------------------
# Schema path
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "validated_cluster.schema.json"
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_CLUSTER_SIZE: int = 3
MIN_COHESION: float = 0.6
MAX_PASS_TYPES: int = 3
MAX_REMEDIATION_TARGETS: int = 2
MIN_AVG_CONFIDENCE: float = 0.6


# ---------------------------------------------------------------------------
# ValidatedCluster
# ---------------------------------------------------------------------------


class ValidatedCluster:
    """In-memory representation of a validation result for one ErrorCluster.

    Parameters
    ----------
    cluster_id:
        ID of the source ErrorCluster.
    cluster_signature:
        Primary error code string that identifies the cluster.
    record_count:
        Number of classification records in the cluster.
    error_codes:
        All error codes present in the cluster (primary + secondary).
    pass_types:
        Distinct pass types found across the cluster's records.
    remediation_targets:
        Unique remediation targets from the cluster.
    validation_status:
        ``"valid"`` or ``"invalid"``.
    validation_reasons:
        Explicit, auditable reasons explaining each validation decision.
    stability_score:
        Float 0–1.
    cohesion_score:
        Float 0–1.
    actionability_score:
        Float 0–1.
    created_at:
        ISO-8601 timestamp.
    """

    def __init__(
        self,
        *,
        cluster_id: str,
        cluster_signature: str,
        record_count: int,
        error_codes: List[str],
        pass_types: List[str],
        remediation_targets: List[str],
        validation_status: str,
        validation_reasons: List[str],
        stability_score: float,
        cohesion_score: float,
        actionability_score: float,
        created_at: str,
    ) -> None:
        self.cluster_id = cluster_id
        self.cluster_signature = cluster_signature
        self.record_count = record_count
        self.error_codes = error_codes
        self.pass_types = pass_types
        self.remediation_targets = remediation_targets
        self.validation_status = validation_status
        self.validation_reasons = validation_reasons
        self.stability_score = stability_score
        self.cohesion_score = cohesion_score
        self.actionability_score = actionability_score
        self.created_at = created_at

    # --- Serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "cluster_signature": self.cluster_signature,
            "record_count": self.record_count,
            "error_codes": self.error_codes,
            "pass_types": self.pass_types,
            "remediation_targets": self.remediation_targets,
            "validation_status": self.validation_status,
            "validation_reasons": self.validation_reasons,
            "stability_score": round(self.stability_score, 4),
            "cohesion_score": round(self.cohesion_score, 4),
            "actionability_score": round(self.actionability_score, 4),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidatedCluster":
        return cls(
            cluster_id=data["cluster_id"],
            cluster_signature=data["cluster_signature"],
            record_count=data["record_count"],
            error_codes=data["error_codes"],
            pass_types=data["pass_types"],
            remediation_targets=data["remediation_targets"],
            validation_status=data["validation_status"],
            validation_reasons=data["validation_reasons"],
            stability_score=data["stability_score"],
            cohesion_score=data["cohesion_score"],
            actionability_score=data["actionability_score"],
            created_at=data["created_at"],
        )

    # --- Schema validation ---------------------------------------------------

    def validate_against_schema(self) -> List[str]:
        """Validate this object against the JSON Schema.

        Returns
        -------
        List[str]
            List of error message strings.  Empty list means valid.
        """
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        errors: List[str] = []
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(self.to_dict()):
            errors.append(err.message)
        return errors


# ---------------------------------------------------------------------------
# ClusterValidator
# ---------------------------------------------------------------------------


class ClusterValidator:
    """Validates ErrorCluster objects against six quality rules.

    Parameters
    ----------
    min_cluster_size:
        Minimum number of records a cluster must contain.  Default: 3.
    min_cohesion:
        Minimum fraction of records whose primary code matches the cluster
        signature.  Default: 0.6.
    max_pass_types:
        Maximum number of distinct pass_types allowed.  Default: 3.
    max_remediation_targets:
        Maximum number of remediation targets allowed.  Default: 2.
    min_avg_confidence:
        Minimum average classification confidence.  Default: 0.6.
    """

    def __init__(
        self,
        *,
        min_cluster_size: int = MIN_CLUSTER_SIZE,
        min_cohesion: float = MIN_COHESION,
        max_pass_types: int = MAX_PASS_TYPES,
        max_remediation_targets: int = MAX_REMEDIATION_TARGETS,
        min_avg_confidence: float = MIN_AVG_CONFIDENCE,
    ) -> None:
        self._min_cluster_size = min_cluster_size
        self._min_cohesion = min_cohesion
        self._max_pass_types = max_pass_types
        self._max_remediation_targets = max_remediation_targets
        self._min_avg_confidence = min_avg_confidence

    # --- Public entry point --------------------------------------------------

    def validate_cluster(
        self,
        cluster: "ErrorCluster",
        classification_records: List["ErrorClassificationRecord"],
    ) -> ValidatedCluster:
        """Validate one ErrorCluster against all six quality rules.

        Parameters
        ----------
        cluster:
            The ErrorCluster to validate.
        classification_records:
            All classification records that belong to this cluster.
            Used for signature recomputation and confidence checks.

        Returns
        -------
        ValidatedCluster
            A new ValidatedCluster object.  The original cluster is not modified.
        """
        reasons: List[str] = []
        is_invalid = False

        # Collect data needed across multiple rules
        pass_types = self._collect_pass_types(cluster, classification_records)
        error_codes = self._collect_error_codes(cluster)
        recomputed_signature = self._recompute_signature(classification_records)
        avg_confidence = self._compute_avg_confidence(classification_records)
        cohesion = self._compute_cohesion(cluster, classification_records)

        # A. SIZE CHECK
        if cluster.metrics["record_count"] < self._min_cluster_size:
            is_invalid = True
            reasons.append(
                f"too_small: record_count={cluster.metrics['record_count']} "
                f"< min={self._min_cluster_size}"
            )
        else:
            reasons.append(
                f"size_ok: record_count={cluster.metrics['record_count']} "
                f">= min={self._min_cluster_size}"
            )

        # B. COHESION CHECK
        if cohesion < self._min_cohesion:
            is_invalid = True
            reasons.append(
                f"low_cohesion: dominant_code_fraction={cohesion:.4f} "
                f"< min={self._min_cohesion}"
            )
        else:
            reasons.append(
                f"cohesion_ok: dominant_code_fraction={cohesion:.4f} "
                f">= min={self._min_cohesion}"
            )

        # C. PASS CONSISTENCY
        num_pass_types = len(pass_types)
        if num_pass_types > self._max_pass_types:
            # Flag but do not invalidate (per spec: "flag")
            reasons.append(
                f"too_broad: pass_type_count={num_pass_types} "
                f"> max={self._max_pass_types}"
            )
        else:
            reasons.append(
                f"pass_consistency_ok: pass_type_count={num_pass_types} "
                f"<= max={self._max_pass_types}"
            )

        # D. STABILITY CHECK
        stored_sig = cluster.cluster_signature.get("primary_error_code", "")
        if recomputed_signature != stored_sig:
            is_invalid = True
            reasons.append(
                f"unstable_signature: stored={stored_sig!r} "
                f"!= recomputed={recomputed_signature!r}"
            )
        else:
            reasons.append(
                f"signature_stable: stored={stored_sig!r} "
                f"== recomputed={recomputed_signature!r}"
            )

        # E. ACTIONABILITY CHECK
        num_targets = len(cluster.remediation_targets)
        if num_targets > self._max_remediation_targets:
            is_invalid = True
            reasons.append(
                f"unclear_remediation: remediation_target_count={num_targets} "
                f"> max={self._max_remediation_targets}"
            )
        else:
            reasons.append(
                f"actionability_ok: remediation_target_count={num_targets} "
                f"<= max={self._max_remediation_targets}"
            )

        # F. CONFIDENCE CHECK
        if avg_confidence < self._min_avg_confidence:
            is_invalid = True
            reasons.append(
                f"low_confidence: avg_confidence={avg_confidence:.4f} "
                f"< min={self._min_avg_confidence}"
            )
        else:
            reasons.append(
                f"confidence_ok: avg_confidence={avg_confidence:.4f} "
                f">= min={self._min_avg_confidence}"
            )

        # Compute scores
        stability_score = self._compute_stability_score(
            cluster, classification_records, recomputed_signature
        )
        cohesion_score = cohesion
        actionability_score = self._compute_actionability_score(cluster)

        return ValidatedCluster(
            cluster_id=cluster.cluster_id,
            cluster_signature=cluster.cluster_signature.get("primary_error_code", ""),
            record_count=cluster.metrics["record_count"],
            error_codes=error_codes,
            pass_types=sorted(pass_types),
            remediation_targets=list(cluster.remediation_targets),
            validation_status="invalid" if is_invalid else "valid",
            validation_reasons=reasons,
            stability_score=stability_score,
            cohesion_score=cohesion_score,
            actionability_score=actionability_score,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # --- Scoring helpers -----------------------------------------------------

    def _compute_stability_score(
        self,
        cluster: "ErrorCluster",
        records: List["ErrorClassificationRecord"],
        recomputed_signature: str,
    ) -> float:
        """Score 0–1 based on signature consistency and record overlap.

        A score of 1.0 means the signature is perfectly stable and all records
        contribute to the dominant code.  A score of 0.0 means the signature
        does not match the recomputed value at all.
        """
        stored_sig = cluster.cluster_signature.get("primary_error_code", "")
        sig_match = 1.0 if recomputed_signature == stored_sig else 0.0

        if not records:
            return sig_match

        # Fraction of records whose primary code matches the stored signature
        matching = sum(
            1
            for r in records
            if self._record_primary_code(r) == stored_sig
        )
        overlap = matching / len(records)
        return round((sig_match + overlap) / 2.0, 4)

    def _compute_cohesion(
        self,
        cluster: "ErrorCluster",
        records: List["ErrorClassificationRecord"],
    ) -> float:
        """Fraction of all error code occurrences accounted for by the dominant code."""
        if not records:
            # Fall back to the cluster's stored signature if no live records
            primary = cluster.cluster_signature.get("primary_error_code", "")
            all_codes = [primary] + cluster.cluster_signature.get("secondary_error_codes", [])
            if not all_codes:
                return 0.0
            return round(1.0 / len(all_codes), 4)

        code_counts: Counter[str] = Counter()
        for rec in records:
            for entry in rec.classifications:
                code_counts[entry["error_code"]] += 1

        if not code_counts:
            return 0.0

        dominant_code = cluster.cluster_signature.get("primary_error_code", "")
        dominant_count = code_counts.get(dominant_code, 0)
        total = sum(code_counts.values())
        return round(dominant_count / total, 4) if total > 0 else 0.0

    def _compute_actionability_score(self, cluster: "ErrorCluster") -> float:
        """Inverse of number of remediation targets, normalized to 0–1.

        0 targets  → 1.0 (no ambiguity)
        1 target   → 1.0
        2 targets  → 0.5
        3 targets  → 0.333…
        n targets  → 1/n
        """
        n = len(cluster.remediation_targets)
        if n <= 1:
            return 1.0
        return round(1.0 / n, 4)

    # --- Collection helpers --------------------------------------------------

    def _collect_pass_types(
        self,
        cluster: "ErrorCluster",
        records: List["ErrorClassificationRecord"],
    ) -> List[str]:
        """Collect distinct pass_types from live records, falling back to cluster context."""
        if records:
            pts: set[str] = set()
            for rec in records:
                pt = rec.context.get("pass_type") or ""
                if pt:
                    pts.add(pt)
            return sorted(pts)
        # Fallback: use context_distribution stored in cluster
        return sorted(cluster.context_distribution.get("pass_types", {}).keys())

    def _collect_error_codes(self, cluster: "ErrorCluster") -> List[str]:
        """Return all error codes (primary + secondary) in deterministic order."""
        sig = cluster.cluster_signature
        primary = sig.get("primary_error_code", "")
        secondary = sig.get("secondary_error_codes", [])
        all_codes = [primary] + [c for c in secondary if c != primary]
        return all_codes

    def _recompute_signature(
        self,
        records: List["ErrorClassificationRecord"],
    ) -> str:
        """Recompute the primary error code from live records.

        Returns the most frequent error code, or empty string if no records.
        """
        if not records:
            return ""
        code_counts: Counter[str] = Counter()
        for rec in records:
            for entry in rec.classifications:
                code_counts[entry["error_code"]] += 1
        if not code_counts:
            return ""
        # Deterministic tie-breaking: sort by (-count, code)
        ordered = sorted(code_counts.items(), key=lambda x: (-x[1], x[0]))
        return ordered[0][0]

    def _compute_avg_confidence(
        self,
        records: List["ErrorClassificationRecord"],
    ) -> float:
        """Compute average classification confidence across all records."""
        confidences: List[float] = []
        for rec in records:
            for entry in rec.classifications:
                confidences.append(float(entry.get("confidence", 1.0)))
        if not confidences:
            return 0.0
        return sum(confidences) / len(confidences)

    @staticmethod
    def _record_primary_code(record: "ErrorClassificationRecord") -> str:
        """Return the highest-confidence error code for a single record."""
        if not record.classifications:
            return ""
        best = max(
            record.classifications,
            key=lambda e: (float(e.get("confidence", 0.0)), e["error_code"]),
        )
        return best["error_code"]
