"""
Clustering Engine — spectrum_systems/modules/error_taxonomy/clustering.py

Groups ErrorClassificationRecord objects into deterministic, explainable
failure pattern clusters for downstream analysis (AW prompt improvement loop).

Design principles
-----------------
- Fully deterministic: same input → same output, every time.
- Multi-label aware: a record can have multiple error codes; it is assigned
  to the cluster whose primary_error_code matches its *most frequent* code.
- Small clusters below ``min_cluster_size`` are merged into a sibling cluster
  that shares the same dominant family, or kept if no sibling exists.
- No opaque ML: grouping is purely code-frequency and co-occurrence based.
- All traceability is preserved: every cluster references its source records.

Public API
----------
ErrorCluster
    In-memory representation of one failure pattern cluster.

ErrorClusterer
    Performs clustering on a list of ErrorClassificationRecord objects.
"""
from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import jsonschema

if TYPE_CHECKING:
    from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
    from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "error_cluster.schema.json"
)


# ---------------------------------------------------------------------------
# ErrorCluster
# ---------------------------------------------------------------------------

class ErrorCluster:
    """In-memory representation of one failure pattern cluster.

    Parameters
    ----------
    cluster_id:
        Unique identifier.
    timestamp:
        ISO-8601 timestamp when this cluster was created.
    taxonomy_version:
        Version of the taxonomy catalog used.
    cluster_signature:
        Dict with ``primary_error_code``, ``secondary_error_codes``,
        ``dominant_family``.
    metrics:
        Dict with ``record_count``, ``weighted_severity_score``,
        ``avg_confidence``.
    context_distribution:
        Dict with ``artifact_types``, ``pass_types``, ``source_systems``.
    remediation_targets:
        List of unique remediation target strings.
    representative_examples:
        List of representative example dicts.
    notes:
        Optional free-text notes.
    record_ids:
        IDs of all classification records that belong to this cluster.
        Not persisted to the schema but useful for in-memory traceability.
    """

    def __init__(
        self,
        *,
        cluster_id: str,
        timestamp: str,
        taxonomy_version: str,
        cluster_signature: Dict[str, Any],
        metrics: Dict[str, Any],
        context_distribution: Dict[str, Any],
        remediation_targets: List[str],
        representative_examples: List[Dict[str, Any]],
        notes: str = "",
        record_ids: Optional[List[str]] = None,
    ) -> None:
        self.cluster_id = cluster_id
        self.timestamp = timestamp
        self.taxonomy_version = taxonomy_version
        self.cluster_signature = cluster_signature
        self.metrics = metrics
        self.context_distribution = context_distribution
        self.remediation_targets = remediation_targets
        self.representative_examples = representative_examples
        self.notes = notes
        self.record_ids: List[str] = record_ids or []

    # --- Serialisation ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "cluster_id": self.cluster_id,
            "timestamp": self.timestamp,
            "taxonomy_version": self.taxonomy_version,
            "cluster_signature": self.cluster_signature,
            "metrics": self.metrics,
            "context_distribution": self.context_distribution,
            "remediation_targets": self.remediation_targets,
            "representative_examples": self.representative_examples,
        }
        if self.notes:
            d["notes"] = self.notes
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorCluster":
        return cls(
            cluster_id=data["cluster_id"],
            timestamp=data["timestamp"],
            taxonomy_version=data["taxonomy_version"],
            cluster_signature=data["cluster_signature"],
            metrics=data["metrics"],
            context_distribution=data["context_distribution"],
            remediation_targets=data["remediation_targets"],
            representative_examples=data["representative_examples"],
            notes=data.get("notes", ""),
        )

    # --- Schema validation ------------------------------------------------

    def validate_against_schema(self) -> List[str]:
        """Validate against the JSON Schema.

        Returns a list of error message strings.  Empty list means valid.
        """
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        errors: List[str] = []
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(self.to_dict()):
            errors.append(err.message)
        return errors


# ---------------------------------------------------------------------------
# ErrorClusterer
# ---------------------------------------------------------------------------

class ErrorClusterer:
    """Clusters ErrorClassificationRecord objects into failure pattern groups.

    Parameters
    ----------
    catalog:
        Loaded ``ErrorTaxonomyCatalog``.  Used for severity lookups and
        remediation target resolution.
    min_cluster_size:
        Clusters with fewer records than this threshold are merged into a
        sibling cluster that shares the same dominant family.  Default: 2.
    taxonomy_version:
        Taxonomy version string to embed in produced clusters.  Defaults to
        the version from ``catalog``.
    severity_weights:
        Optional override for severity → weight mapping.
    """

    _DEFAULT_SEVERITY_WEIGHTS: Dict[str, float] = {
        "low": 1.0,
        "medium": 2.0,
        "high": 3.0,
        "critical": 5.0,
    }

    def __init__(
        self,
        catalog: "ErrorTaxonomyCatalog",
        *,
        min_cluster_size: int = 2,
        taxonomy_version: Optional[str] = None,
        severity_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self._catalog = catalog
        self._min_cluster_size = min_cluster_size
        self._taxonomy_version = taxonomy_version or catalog.version
        self._severity_weights = severity_weights or self._DEFAULT_SEVERITY_WEIGHTS

    # --- Public entry point -----------------------------------------------

    def group_records(
        self,
        records: List["ErrorClassificationRecord"],
    ) -> List["ErrorCluster"]:
        """Cluster a list of classification records into failure pattern groups.

        Steps
        -----
        1. Group records by their *primary* (most frequent) error code.
        2. Within each primary-code group, sub-cluster by co-occurring codes
           and pass_type.
        3. Merge clusters smaller than ``min_cluster_size`` into the sibling
           cluster with the closest dominant family.

        Parameters
        ----------
        records:
            List of ``ErrorClassificationRecord`` objects.  Records from
            incompatible taxonomy versions are silently skipped.

        Returns
        -------
        List[ErrorCluster]
            Deterministically ordered list of clusters.
        """
        if not records:
            return []

        # Filter to consistent taxonomy version
        compatible = [
            r for r in records if r.taxonomy_version == self._taxonomy_version
        ]
        if not compatible:
            return []

        # Step 1: group by primary error code
        primary_groups: Dict[str, List["ErrorClassificationRecord"]] = defaultdict(list)
        for rec in compatible:
            primary_code = self._primary_code(rec)
            primary_groups[primary_code].append(rec)

        # Step 2: sub-cluster within each primary group by co-occurring codes +
        #         pass_type signature; collect into flat list
        raw_clusters: List[List["ErrorClassificationRecord"]] = []
        for primary_code in sorted(primary_groups.keys()):
            group = primary_groups[primary_code]
            sub_groups = self._sub_cluster(group)
            raw_clusters.extend(sub_groups)

        # Step 3: merge small clusters
        merged = self._merge_small_clusters(raw_clusters)

        # Build ErrorCluster objects
        clusters = [self._build_cluster(group) for group in merged]
        return clusters

    # --- Signature / metrics helpers --------------------------------------

    def compute_cluster_signature(
        self,
        records: List["ErrorClassificationRecord"],
    ) -> Dict[str, Any]:
        """Compute the cluster signature from a group of records.

        The primary_error_code is the most frequently occurring error code.
        secondary_error_codes are all other codes that appear in the group,
        in descending frequency order.
        dominant_family is derived from primary_error_code.

        Parameters
        ----------
        records:
            Non-empty list of ``ErrorClassificationRecord`` objects.

        Returns
        -------
        Dict with ``primary_error_code``, ``secondary_error_codes``,
        ``dominant_family``.
        """
        code_counts: Counter[str] = Counter()
        for rec in records:
            for entry in rec.classifications:
                code_counts[entry["error_code"]] += 1

        if not code_counts:
            return {
                "primary_error_code": "UNKNOWN",
                "secondary_error_codes": [],
                "dominant_family": "UNKNOWN",
            }

        # Deterministic: sort by (-count, code) to break ties alphabetically
        ordered = sorted(code_counts.items(), key=lambda x: (-x[1], x[0]))
        primary = ordered[0][0]
        secondary = [code for code, _ in ordered[1:]]
        dominant_family = primary.split(".")[0] if "." in primary else primary

        return {
            "primary_error_code": primary,
            "secondary_error_codes": secondary,
            "dominant_family": dominant_family,
        }

    def compute_metrics(
        self,
        records: List["ErrorClassificationRecord"],
    ) -> Dict[str, Any]:
        """Compute aggregate metrics for a group of records.

        Parameters
        ----------
        records:
            Non-empty list of ``ErrorClassificationRecord`` objects.

        Returns
        -------
        Dict with ``record_count``, ``weighted_severity_score``,
        ``avg_confidence``.
        """
        record_count = len(records)
        all_confidences: List[float] = []
        weighted_severity = 0.0

        for rec in records:
            for entry in rec.classifications:
                confidence = float(entry.get("confidence", 1.0))
                all_confidences.append(confidence)
                code = entry["error_code"]
                subtype = self._catalog.get_error(code)
                severity = subtype.default_severity if subtype else "medium"
                weight = self._severity_weights.get(severity, 2.0)
                weighted_severity += weight * confidence

        avg_confidence = (
            sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        )

        return {
            "record_count": record_count,
            "weighted_severity_score": round(weighted_severity, 4),
            "avg_confidence": round(avg_confidence, 4),
        }

    def extract_representative_examples(
        self,
        records: List["ErrorClassificationRecord"],
        top_n: int = 3,
    ) -> List[Dict[str, Any]]:
        """Extract the top-N most representative examples from a record group.

        Selection criterion: records whose total classification confidence is
        highest (most confident examples), with ties broken by classification_id
        for determinism.

        Parameters
        ----------
        records:
            List of ``ErrorClassificationRecord`` objects.
        top_n:
            Number of examples to return.

        Returns
        -------
        List of dicts with ``classification_id``, ``error_codes``,
        ``explanation``.
        """
        scored = []
        for rec in records:
            total_conf = sum(
                float(e.get("confidence", 0.0)) for e in rec.classifications
            )
            scored.append((total_conf, rec.classification_id, rec))

        # Sort by descending confidence, then ascending id for determinism
        scored.sort(key=lambda x: (-x[0], x[1]))

        examples = []
        for _, _, rec in scored[:top_n]:
            codes = [e["error_code"] for e in rec.classifications]
            explanation = rec.classifications[0].get("explanation", "") if rec.classifications else ""
            examples.append({
                "classification_id": rec.classification_id,
                "error_codes": codes,
                "explanation": explanation,
            })
        return examples

    # --- Internal helpers -------------------------------------------------

    def _primary_code(self, record: "ErrorClassificationRecord") -> str:
        """Return the most-frequent error code for a record.

        If a record has multiple classifications, the code with the highest
        confidence wins; ties broken alphabetically by full error_code string.
        """
        if not record.classifications:
            return "UNKNOWN"
        best = max(
            record.classifications,
            key=lambda e: (float(e.get("confidence", 0.0)), e["error_code"]),
        )
        return best["error_code"]

    def _cooccurrence_key(self, record: "ErrorClassificationRecord") -> str:
        """Produce a stable co-occurrence key for sub-clustering.

        Key = sorted tuple of all error codes + pass_type.
        """
        codes = sorted(e["error_code"] for e in record.classifications)
        pass_type = record.context.get("pass_type") or ""
        source = record.context.get("source_system") or ""
        return "|".join(codes) + f"@{pass_type}@{source}"

    def _sub_cluster(
        self,
        group: List["ErrorClassificationRecord"],
    ) -> List[List["ErrorClassificationRecord"]]:
        """Sub-cluster a primary-code group by co-occurrence + pass_type signature."""
        sub_groups: Dict[str, List["ErrorClassificationRecord"]] = defaultdict(list)
        for rec in group:
            key = self._cooccurrence_key(rec)
            sub_groups[key].append(rec)
        # Return sorted for determinism
        return [sub_groups[k] for k in sorted(sub_groups.keys())]

    def _merge_small_clusters(
        self,
        raw_clusters: List[List["ErrorClassificationRecord"]],
    ) -> List[List["ErrorClassificationRecord"]]:
        """Merge clusters below min_cluster_size into the closest sibling.

        Merge strategy:
        - Find the largest cluster that shares the same dominant family.
        - If none exists, keep the small cluster as-is (it may be unique).
        """
        if not raw_clusters:
            return []

        # Build family → index map pointing to the largest cluster per family
        family_to_largest: Dict[str, int] = {}
        for i, group in enumerate(raw_clusters):
            if len(group) < self._min_cluster_size:
                continue
            sig = self.compute_cluster_signature(group)
            family = sig["dominant_family"]
            if family not in family_to_largest:
                family_to_largest[family] = i
            else:
                current_largest_size = len(raw_clusters[family_to_largest[family]])
                if len(group) > current_largest_size:
                    family_to_largest[family] = i

        merged: List[List["ErrorClassificationRecord"]] = []
        merge_targets: Dict[int, int] = {}  # small_idx → large_idx (in merged list)

        # First pass: add all non-small clusters
        index_map: Dict[int, int] = {}  # original index → merged index
        for i, group in enumerate(raw_clusters):
            if len(group) >= self._min_cluster_size:
                index_map[i] = len(merged)
                merged.append(list(group))

        # Second pass: merge small clusters
        for i, group in enumerate(raw_clusters):
            if len(group) >= self._min_cluster_size:
                continue
            sig = self.compute_cluster_signature(group)
            family = sig["dominant_family"]
            if family in family_to_largest:
                target_orig_idx = family_to_largest[family]
                target_merged_idx = index_map.get(target_orig_idx)
                if target_merged_idx is not None:
                    merged[target_merged_idx].extend(group)
                    continue
            # No suitable sibling — keep as standalone
            merged.append(list(group))

        return merged

    def _compute_context_distribution(
        self,
        records: List["ErrorClassificationRecord"],
    ) -> Dict[str, Any]:
        """Compute distribution of artifact_types, pass_types, source_systems."""
        artifact_types: Counter[str] = Counter()
        pass_types: Counter[str] = Counter()
        source_systems: Counter[str] = Counter()
        for rec in records:
            ctx = rec.context
            artifact_types[ctx.get("artifact_type") or "unknown"] += 1
            pass_types[ctx.get("pass_type") or "unknown"] += 1
            source_systems[ctx.get("source_system") or "unknown"] += 1
        return {
            "artifact_types": dict(artifact_types),
            "pass_types": dict(pass_types),
            "source_systems": dict(source_systems),
        }

    def _compute_remediation_targets(
        self,
        records: List["ErrorClassificationRecord"],
    ) -> List[str]:
        """Collect unique remediation targets from all error codes in the group."""
        targets: set[str] = set()
        for rec in records:
            for entry in rec.classifications:
                code = entry["error_code"]
                subtype = self._catalog.get_error(code)
                if subtype:
                    targets.add(subtype.remediation_target)
        return sorted(targets)

    def _build_cluster(
        self,
        records: List["ErrorClassificationRecord"],
    ) -> "ErrorCluster":
        """Build an ErrorCluster from a group of records."""
        return ErrorCluster(
            cluster_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            taxonomy_version=self._taxonomy_version,
            cluster_signature=self.compute_cluster_signature(records),
            metrics=self.compute_metrics(records),
            context_distribution=self._compute_context_distribution(records),
            remediation_targets=self._compute_remediation_targets(records),
            representative_examples=self.extract_representative_examples(records),
            record_ids=[r.classification_id for r in records],
        )
