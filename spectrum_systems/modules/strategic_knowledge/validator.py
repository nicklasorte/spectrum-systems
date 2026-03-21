"""Deterministic Strategic Knowledge Validation Gate decision logic (pure)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

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

COMMON_ARTIFACT_FIELDS = {
    "artifact_type",
    "artifact_id",
    "artifact_version",
    "schema_version",
    "created_at",
    "source",
    "provenance",
    "evidence_anchors",
    "artifact_refs",
}

ARTIFACT_SPECIFIC_FIELDS = {
    "book_intelligence_pack": {"insights", "themes", "key_claims", "confidence"},
    "transcript_intelligence_pack": {"decisions", "open_questions", "action_signals"},
    "story_bank_entry": {"headline", "narrative", "strategic_relevance"},
    "tactic_register": {"tactic_name", "context", "recommended_use"},
    "viewpoint_pack": {"viewpoint", "supporting_arguments", "counterpoints"},
    "evidence_map": {"claim_id", "claim_text", "confidence"},
}


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


def _coerce_context(context: dict[str, Any] | None) -> dict[str, Any]:
    return context if isinstance(context, dict) else {}


def _validate_schema(input_artifact: dict[str, Any], issues: list[ValidationIssue]) -> bool:
    artifact_type = input_artifact.get("artifact_type")
    if artifact_type not in ARTIFACT_TYPES:
        issues.append(
            ValidationIssue(
                code="UNKNOWN_ARTIFACT_TYPE",
                severity="error",
                message=f"Unsupported artifact_type for strategic validation gate: {artifact_type!r}",
            )
        )
        return False

    required_fields = {
        "artifact_type",
        "artifact_id",
        "artifact_version",
        "schema_version",
        "created_at",
        "source",
        "provenance",
        "evidence_anchors",
    }
    missing_required = sorted(field for field in required_fields if field not in input_artifact)
    if missing_required:
        issues.append(
            ValidationIssue(
                code="SCHEMA_REQUIRED_FIELDS_MISSING",
                severity="error",
                message=f"Missing required fields: {', '.join(missing_required)}",
            )
        )
        return False

    allowed_fields = COMMON_ARTIFACT_FIELDS | ARTIFACT_SPECIFIC_FIELDS[artifact_type]
    unknown = sorted(set(input_artifact.keys()) - allowed_fields)
    if unknown:
        issues.append(
            ValidationIssue(
                code="SCHEMA_UNKNOWN_FIELDS",
                severity="error",
                message=f"Unknown fields are not allowed: {', '.join(unknown)}",
            )
        )
        return False

    return True


def _check_source_refs(
    input_artifact: dict[str, Any],
    source_catalog: dict[str, Any] | None,
    issues: list[ValidationIssue],
) -> bool:
    source = input_artifact.get("source")
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

    if not isinstance(source_catalog, dict) or not isinstance(source_catalog.get("sources"), list):
        issues.append(
            ValidationIssue(
                code="SOURCE_CATALOG_UNAVAILABLE",
                severity="error",
                message="source catalog payload is unavailable or malformed",
            )
        )
        return False

    for entry in source_catalog["sources"]:
        if isinstance(entry, dict) and entry.get("source_id") == source_id:
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


def _extract_artifact_refs(input_artifact: dict[str, Any]) -> list[dict[str, Any]]:
    refs = input_artifact.get("artifact_refs", [])
    if refs is None or not isinstance(refs, list):
        return []
    return [ref for ref in refs if isinstance(ref, dict)]


def _check_artifact_refs(
    artifact_refs: list[dict[str, Any]],
    artifact_registry: dict[str, Any] | None,
    issues: list[ValidationIssue],
) -> bool:
    if not artifact_refs:
        return True

    if not isinstance(artifact_registry, dict) or not isinstance(artifact_registry.get("artifacts"), list):
        issues.append(
            ValidationIssue(
                code="ARTIFACT_REGISTRY_UNAVAILABLE",
                severity="error",
                message="artifact registry payload is unavailable or malformed",
            )
        )
        return False

    known = {
        (item.get("artifact_type"), item.get("artifact_id"))
        for item in artifact_registry["artifacts"]
        if isinstance(item, dict)
    }

    all_resolved = True
    for ref in artifact_refs:
        key = (ref.get("artifact_type"), ref.get("artifact_id"))
        if key not in known:
            all_resolved = False
            issues.append(
                ValidationIssue(
                    code="ARTIFACT_REF_UNRESOLVED",
                    severity="warning",
                    message=f"artifact ref {key!r} was not found in artifact registry.",
                )
            )
    return all_resolved


def _compute_evidence_anchor_coverage(input_artifact: dict[str, Any]) -> float:
    anchors = input_artifact.get("evidence_anchors")
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


def _compute_provenance_completeness(input_artifact: dict[str, Any]) -> float:
    provenance = input_artifact.get("provenance")
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
        collected.append(
            ValidationIssue(
                code="PROVENANCE_INCOMPLETE",
                severity="warning",
                message=(
                    "Provenance completeness below required threshold "
                    f"({provenance_completeness:.4f} < {PROVENANCE_REBUILD_THRESHOLD:.2f})."
                ),
            )
        )
    if schema_valid and source_refs_valid and artifact_refs_valid and evidence_anchor_coverage >= EVIDENCE_REVIEW_THRESHOLD:
        if provenance_completeness >= PROVENANCE_REBUILD_THRESHOLD:
            collected.append(
                ValidationIssue(
                    code="VALIDATION_PASSED",
                    severity="info",
                    message="Artifact satisfied all strategic knowledge validation gate checks.",
                )
            )

    return [issue.as_dict() for issue in collected]


def validate_strategic_knowledge_artifact(
    input_artifact: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate strategic knowledge candidate artifact with fail-closed policy logic."""

    context_payload = _coerce_context(context)
    issues: list[ValidationIssue] = []

    schema_signal = context_payload.get("schema_valid")
    if isinstance(schema_signal, bool):
        schema_valid = schema_signal
        if not schema_valid:
            issues.append(
                ValidationIssue(
                    code="SCHEMA_VALIDATION_FAILED",
                    severity="error",
                    message="Artifact failed contract schema validation signal from context.",
                )
            )
    else:
        schema_valid = _validate_schema(input_artifact, issues)

    source_refs_valid = _check_source_refs(input_artifact, context_payload.get("source_catalog"), issues)
    artifact_refs_valid = _check_artifact_refs(
        _extract_artifact_refs(input_artifact),
        context_payload.get("artifact_registry"),
        issues,
    )

    evidence_anchor_coverage = _compute_evidence_anchor_coverage(input_artifact)
    provenance_completeness = _compute_provenance_completeness(input_artifact)

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

    return {
        "decision_id": f"SK-VAL-{input_artifact.get('artifact_id', 'UNKNOWN')}",
        "artifact_id": str(input_artifact.get("artifact_id", "UNKNOWN")),
        "artifact_type": str(input_artifact.get("artifact_type", "UNKNOWN")),
        "schema_version": str(input_artifact.get("schema_version", "unknown")),
        "evaluated_at": str(context_payload.get("evaluated_at") or _utc_now_iso()),
        "validator_version": str(context_payload.get("validator_version") or VALIDATOR_VERSION),
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
