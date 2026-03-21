"""Deterministic Strategic Knowledge Validation Gate for admission decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema

from .contracts import validate

VALIDATOR_VERSION = "1.0.0"
ARTIFACT_TYPES = frozenset(
    {
        "book_intelligence_pack",
        "transcript_intelligence_pack",
        "story_bank_entry",
        "tactic_register",
        "viewpoint_pack",
        "evidence_map",
    }
)

TRUST_WEIGHTS = {
    "schema_valid": 0.35,
    "source_refs_valid": 0.25,
    "artifact_refs_valid": 0.10,
    "evidence_anchor_coverage": 0.15,
    "provenance_completeness": 0.15,
}

EVIDENCE_REVIEW_THRESHOLD = 0.80
PROVENANCE_REBUILD_THRESHOLD = 1.00
ALLOW_TRUST_THRESHOLD = 0.90


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")



def _load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_source_catalog(catalog_path: Path) -> dict[str, Any]:
    if not catalog_path.exists():
        raise FileNotFoundError(f"Missing source catalog: {catalog_path}")
    catalog = _load_json_file(catalog_path)
    if not isinstance(catalog, dict) or "sources" not in catalog:
        raise ValueError("source catalog payload is malformed")
    return catalog


def _load_artifact_registry(registry_path: Path) -> dict[str, Any]:
    if not registry_path.exists():
        raise FileNotFoundError(f"Missing artifact registry: {registry_path}")
    registry = _load_json_file(registry_path)
    if not isinstance(registry, dict) or "artifacts" not in registry:
        raise ValueError("artifact registry payload is malformed")
    return registry


def _validate_schema(artifact: dict[str, Any], issues: list[ValidationIssue]) -> bool:
    artifact_type = artifact.get("artifact_type")
    if artifact_type not in ARTIFACT_TYPES:
        issues.append(
            ValidationIssue(
                code="UNKNOWN_ARTIFACT_TYPE",
                severity="error",
                message=f"Unsupported artifact_type for strategic validation gate: {artifact_type!r}",
            )
        )
        return False

    try:
        validate(artifact, artifact_type)
    except (ValidationError, ValueError) as exc:
        issues.append(
            ValidationIssue(
                code="SCHEMA_VALIDATION_FAILED",
                severity="error",
                message=f"Artifact failed schema validation for {artifact_type}: {getattr(exc, 'message', str(exc))}",
            )
        )
        return False

    return True


def _check_source_refs(
    artifact: dict[str, Any],
    source_catalog_path: Path,
    issues: list[ValidationIssue],
) -> bool:
    source = artifact.get("source")
    if not isinstance(source, dict):
        issues.append(
            ValidationIssue(
                code="SOURCE_REF_MISSING",
                severity="error",
                message="Artifact source reference is missing or malformed.",
            )
        )
        return False

    source_id = source.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        issues.append(
            ValidationIssue(
                code="SOURCE_ID_MISSING",
                severity="error",
                message="Artifact source.source_id is required.",
            )
        )
        return False

    try:
        catalog = _load_source_catalog(source_catalog_path)
    except (FileNotFoundError, ValueError) as exc:
        issues.append(ValidationIssue(code="SOURCE_CATALOG_UNAVAILABLE", severity="error", message=str(exc)))
        return False

    sources = catalog.get("sources", [])
    for entry in sources:
        if entry.get("source_id") == source_id:
            status = entry.get("source_status")
            if status in {"blocked", "archived"}:
                issues.append(
                    ValidationIssue(
                        code="SOURCE_REF_NOT_ADMISSIBLE",
                        severity="error",
                        message=f"source_id {source_id} is {status} in source catalog.",
                    )
                )
                return False
            return True

    issues.append(
        ValidationIssue(
            code="SOURCE_REF_UNRESOLVED",
            severity="error",
            message=f"source_id {source_id} is not present in source catalog.",
        )
    )
    return False


def _extract_artifact_refs(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    refs = artifact.get("artifact_refs", [])
    if refs is None:
        return []
    if not isinstance(refs, list):
        return []
    return [ref for ref in refs if isinstance(ref, dict)]


def _check_artifact_refs(
    artifact_refs: list[dict[str, Any]],
    artifact_registry_path: Path,
    issues: list[ValidationIssue],
) -> bool:
    if not artifact_refs:
        return True

    try:
        registry = _load_artifact_registry(artifact_registry_path)
    except (FileNotFoundError, ValueError) as exc:
        issues.append(ValidationIssue(code="ARTIFACT_REGISTRY_UNAVAILABLE", severity="error", message=str(exc)))
        return False

    known = {
        (item.get("artifact_type"), item.get("artifact_id"))
        for item in registry.get("artifacts", [])
        if isinstance(item, dict)
    }
    all_resolved = True
    for ref in artifact_refs:
        ref_key = (ref.get("artifact_type"), ref.get("artifact_id"))
        if ref_key not in known:
            all_resolved = False
            issues.append(
                ValidationIssue(
                    code="ARTIFACT_REF_UNRESOLVED",
                    severity="warning",
                    message=f"artifact ref {ref_key!r} was not found in artifact registry.",
                )
            )
    return all_resolved


def _compute_evidence_anchor_coverage(artifact: dict[str, Any]) -> float:
    anchors = artifact.get("evidence_anchors")
    if not isinstance(anchors, list) or not anchors:
        return 0.0

    valid = 0
    for anchor in anchors:
        if not isinstance(anchor, dict):
            continue
        anchor_type = anchor.get("anchor_type")
        if anchor_type == "pdf" and isinstance(anchor.get("page_number"), int) and anchor["page_number"] >= 1:
            valid += 1
        elif anchor_type == "transcript" and isinstance(anchor.get("timestamp_start"), str) and isinstance(
            anchor.get("timestamp_end"), str
        ):
            valid += 1
    return round(valid / len(anchors), 4)


def _compute_provenance_completeness(artifact: dict[str, Any]) -> float:
    provenance = artifact.get("provenance")
    required = ("extraction_run_id", "extractor_version")
    if not isinstance(provenance, dict):
        return 0.0

    present = 0
    for key in required:
        value = provenance.get(key)
        if isinstance(value, str) and value.strip():
            present += 1
    return round(present / len(required), 4)


def compute_trust_score(
    *,
    schema_valid: bool,
    source_refs_valid: bool,
    artifact_refs_valid: bool,
    evidence_anchor_coverage: float,
    provenance_completeness: float,
) -> float:
    score = 0.0
    score += TRUST_WEIGHTS["schema_valid"] * (1.0 if schema_valid else 0.0)
    score += TRUST_WEIGHTS["source_refs_valid"] * (1.0 if source_refs_valid else 0.0)
    score += TRUST_WEIGHTS["artifact_refs_valid"] * (1.0 if artifact_refs_valid else 0.0)
    score += TRUST_WEIGHTS["evidence_anchor_coverage"] * max(0.0, min(1.0, evidence_anchor_coverage))
    score += TRUST_WEIGHTS["provenance_completeness"] * max(0.0, min(1.0, provenance_completeness))
    return round(max(0.0, min(1.0, score)), 4)


def _derive_system_response(
    *,
    schema_valid: bool,
    source_refs_valid: bool,
    artifact_refs_valid: bool,
    evidence_anchor_coverage: float,
    provenance_completeness: float,
    trust_score: float,
) -> str:
    if not schema_valid:
        return "block"
    if not source_refs_valid:
        return "block"
    if provenance_completeness <= 0.0:
        return "block"
    if provenance_completeness < PROVENANCE_REBUILD_THRESHOLD:
        return "require_rebuild"
    if not artifact_refs_valid:
        return "require_review"
    if evidence_anchor_coverage < EVIDENCE_REVIEW_THRESHOLD:
        return "require_review"
    if trust_score < ALLOW_TRUST_THRESHOLD:
        return "require_review"
    return "allow"


def collect_validation_issues(
    *,
    schema_valid: bool,
    source_refs_valid: bool,
    artifact_refs_valid: bool,
    evidence_anchor_coverage: float,
    provenance_completeness: float,
    issues: list[ValidationIssue],
) -> list[dict[str, str]]:
    collected = list(issues)
    if evidence_anchor_coverage < EVIDENCE_REVIEW_THRESHOLD:
        collected.append(
            ValidationIssue(
                code="LOW_EVIDENCE_COVERAGE",
                severity="warning",
                message=(
                    "Evidence anchor coverage below review threshold "
                    f"({evidence_anchor_coverage:.4f} < {EVIDENCE_REVIEW_THRESHOLD:.2f})."
                ),
            )
        )
    if provenance_completeness < PROVENANCE_REBUILD_THRESHOLD:
        severity = "error" if provenance_completeness <= 0 else "warning"
        collected.append(
            ValidationIssue(
                code="PROVENANCE_INCOMPLETE",
                severity=severity,
                message=(
                    "Provenance completeness below required threshold "
                    f"({provenance_completeness:.4f} < {PROVENANCE_REBUILD_THRESHOLD:.2f})."
                ),
            )
        )
    if schema_valid and source_refs_valid and artifact_refs_valid and not collected:
        collected.append(
            ValidationIssue(
                code="VALIDATION_PASSED",
                severity="info",
                message="Artifact satisfied all strategic knowledge validation gate checks.",
            )
        )
    return [issue.as_dict() for issue in collected]


def validate_strategic_knowledge_artifact(
    *,
    artifact: dict[str, Any],
    data_lake_root: Path,
    evaluated_at: str | None = None,
    validator_version: str = VALIDATOR_VERSION,
) -> dict[str, Any]:
    issues: list[ValidationIssue] = []
    artifact_type = artifact.get("artifact_type")
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(f"Unsupported artifact_type for strategic validation gate: {artifact_type!r}")

    schema_valid = _validate_schema(artifact, issues)

    source_catalog_path = data_lake_root / "strategic_knowledge" / "metadata" / "source_catalog.json"
    source_refs_valid = _check_source_refs(artifact, source_catalog_path, issues)

    artifact_refs = _extract_artifact_refs(artifact)
    artifact_registry_path = data_lake_root / "strategic_knowledge" / "lineage" / "artifact_registry.json"
    artifact_refs_valid = _check_artifact_refs(artifact_refs, artifact_registry_path, issues)

    evidence_anchor_coverage = _compute_evidence_anchor_coverage(artifact)
    provenance_completeness = _compute_provenance_completeness(artifact)

    trust_score = compute_trust_score(
        schema_valid=schema_valid,
        source_refs_valid=source_refs_valid,
        artifact_refs_valid=artifact_refs_valid,
        evidence_anchor_coverage=evidence_anchor_coverage,
        provenance_completeness=provenance_completeness,
    )

    system_response = _derive_system_response(
        schema_valid=schema_valid,
        source_refs_valid=source_refs_valid,
        artifact_refs_valid=artifact_refs_valid,
        evidence_anchor_coverage=evidence_anchor_coverage,
        provenance_completeness=provenance_completeness,
        trust_score=trust_score,
    )

    decision = {
        "decision_id": f"SK-VAL-{artifact.get('artifact_id', 'UNKNOWN')}",
        "artifact_id": str(artifact.get("artifact_id", "UNKNOWN")),
        "artifact_type": str(artifact.get("artifact_type")),
        "schema_version": str(artifact.get("schema_version", "unknown")),
        "evaluated_at": evaluated_at or _utc_now_iso(),
        "validator_version": validator_version,
        "schema_valid": schema_valid,
        "source_refs_valid": source_refs_valid,
        "artifact_refs_valid": artifact_refs_valid,
        "evidence_anchor_coverage": evidence_anchor_coverage,
        "provenance_completeness": provenance_completeness,
        "trust_score": trust_score,
        "issues": collect_validation_issues(
            schema_valid=schema_valid,
            source_refs_valid=source_refs_valid,
            artifact_refs_valid=artifact_refs_valid,
            evidence_anchor_coverage=evidence_anchor_coverage,
            provenance_completeness=provenance_completeness,
            issues=issues,
        ),
        "system_response": system_response,
    }

    decision_schema = load_schema("strategic_knowledge_validation_decision")
    Draft202012Validator(decision_schema).validate(decision)
    return decision


__all__ = [
    "ALLOW_TRUST_THRESHOLD",
    "EVIDENCE_REVIEW_THRESHOLD",
    "PROVENANCE_REBUILD_THRESHOLD",
    "TRUST_WEIGHTS",
    "VALIDATOR_VERSION",
    "collect_validation_issues",
    "compute_trust_score",
    "validate_strategic_knowledge_artifact",
]
