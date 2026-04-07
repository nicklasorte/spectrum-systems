"""Deterministic Failure Diagnosis Engine (BATCH-FRE-01)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class FailureDiagnosisError(ValueError):
    """Raised when deterministic diagnosis cannot be produced safely."""


_FAILURE_SOURCE_TYPES = {
    "contract_preflight",
    "pytest_summary",
    "contract_enforcement",
    "readiness_failure",
    "certification_failure",
    "control_surface_enforcement",
}

_FAILURE_CLASSES = {
    "schema_mismatch",
    "contract_registration_missing",
    "branch_policy_violation",
    "dependency_graph_violation",
    "test_expectation_drift",
    "unknown_failure",
}

_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "R001",
        "matches": {"branch_policy_violation"},
        "classification": "branch_policy_violation",
        "explanation": "Explicit invariant violation evidence is authoritative and has highest precedence.",
    },
    {
        "rule_id": "R002",
        "matches": {"contract_registration_missing"},
        "classification": "contract_registration_missing",
        "explanation": "Control surface input is required for governed execution and missing inputs fail closed.",
    },
    {
        "rule_id": "R003",
        "matches": {"schema_mismatch"},
        "classification": "schema_mismatch",
        "explanation": "Required governed artifact surface is missing from failure intake.",
    },
    {
        "rule_id": "R004",
        "matches": {"dependency_graph_violation"},
        "classification": "dependency_graph_violation",
        "explanation": "Manifest/registry mismatch evidence indicates authoritative taxonomy or consumer-pin drift.",
    },
    {
        "rule_id": "R005",
        "matches": {"test_expectation_drift"},
        "classification": "test_expectation_drift",
        "explanation": "Schema/example enforcement failures indicate contract drift.",
    },
    {"rule_id": "R006", "matches": {"unknown_failure"}, "classification": "unknown_failure", "explanation": "Fallback class."},
]

_SMALLEST_SAFE_FIX = {
    "schema_mismatch": "align_schema_example_pair",
    "contract_registration_missing": "align_contract_registration",
    "branch_policy_violation": "enforce_branch_policy",
    "dependency_graph_violation": "repair_dependency_graph",
    "test_expectation_drift": "align_test_expectations",
    "unknown_failure": "manual_triage_required",
}

_RECOMMENDED_REPAIR_AREA = {
    "schema_mismatch": "contracts/schemas and contracts/examples",
    "contract_registration_missing": "contracts/standards-manifest.json",
    "branch_policy_violation": ".github/workflows and governance policy surfaces",
    "dependency_graph_violation": "runtime module dependency boundaries",
    "test_expectation_drift": "test assertions and contract behavior alignment",
    "unknown_failure": "manual diagnosis queue",
}

_BLOCKING_SEVERITY = {
    "schema_mismatch": "high",
    "contract_registration_missing": "blocker",
    "branch_policy_violation": "blocker",
    "dependency_graph_violation": "high",
    "test_expectation_drift": "medium",
    "unknown_failure": "high",
}

_SAFE_REPAIRABLE_CLASSES = {
    "contract_registration_missing",
    "schema_mismatch",
    "test_expectation_drift",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _validate(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise FailureDiagnosisError(f"{label} failed schema validation ({schema_name}): {details}")


def _require_non_empty_string_list(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise FailureDiagnosisError(f"{field_name} must be a non-empty list of strings")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise FailureDiagnosisError(f"{field_name} entries must be non-empty strings")
        normalized.append(item.strip())
    return normalized


def _append_evidence(
    evidence: list[dict[str, Any]],
    *,
    source_surface: str,
    evidence_type: str,
    message: str,
    artifact_ref: str,
    details: dict[str, Any] | None = None,
) -> None:
    evidence_id = f"E-{_canonical_hash([source_surface, evidence_type, message, artifact_ref, details or {}])[:16]}"
    row = {
        "evidence_id": evidence_id,
        "source_surface": source_surface,
        "evidence_type": evidence_type,
        "message": message,
        "artifact_ref": artifact_ref,
        "details": details or {},
    }
    evidence.append(row)


def normalize_failure_intake(
    *,
    failure_source_type: str,
    source_artifact_refs: list[str],
    failure_payload: dict[str, Any],
) -> dict[str, Any]:
    """Normalize supported failure surfaces into deterministic evidence rows."""
    if failure_source_type not in _FAILURE_SOURCE_TYPES:
        raise FailureDiagnosisError(
            f"unsupported failure_source_type '{failure_source_type}'; expected one of {sorted(_FAILURE_SOURCE_TYPES)}"
        )
    refs = sorted(set(_require_non_empty_string_list(source_artifact_refs, field_name="source_artifact_refs")))
    if not isinstance(failure_payload, dict):
        raise FailureDiagnosisError("failure_payload must be an object")

    evidence: list[dict[str, Any]] = []
    summary = str(failure_payload.get("observed_failure_summary") or "").strip()
    if not summary:
        summary = f"Failure captured from {failure_source_type}."

    if failure_source_type == "contract_preflight":
        preflight_status = str(failure_payload.get("preflight_status") or "").strip()
        if preflight_status not in {"ALLOW", "BLOCK", "WARN"}:
            raise FailureDiagnosisError("contract_preflight failure_payload.preflight_status must be ALLOW, WARN, or BLOCK")

        for surface in sorted(set(failure_payload.get("missing_required_surfaces") or [])):
            _append_evidence(
                evidence,
                source_surface="contract_preflight",
                evidence_type="contract_registration_missing",
                message=f"Required surface missing: {surface}",
                artifact_ref=refs[0],
                details={"surface": surface},
            )

        for item in sorted(set(failure_payload.get("missing_control_inputs") or [])):
            _append_evidence(
                evidence,
                source_surface="contract_preflight",
                evidence_type="contract_registration_missing",
                message=f"Control-surface input missing: {item}",
                artifact_ref=refs[0],
                details={"surface": item},
            )

        for violation in sorted(set(failure_payload.get("invariant_violations") or [])):
            _append_evidence(
                evidence,
                source_surface="contract_preflight",
                evidence_type="branch_policy_violation",
                message=f"Invariant violation: {violation}",
                artifact_ref=refs[0],
                details={"invariant": violation},
            )

        for drift in sorted(set(failure_payload.get("schema_example_failures") or [])):
            _append_evidence(
                evidence,
                source_surface="contract_preflight",
                evidence_type="schema_mismatch",
                message=f"Schema/example failure: {drift}",
                artifact_ref=refs[0],
                details={"failure": drift},
            )

    elif failure_source_type == "pytest_summary":
        failures = failure_payload.get("failing_tests")
        if not isinstance(failures, list) or not failures:
            raise FailureDiagnosisError("pytest_summary failure_payload.failing_tests must be a non-empty list")
        for row in failures:
            if not isinstance(row, dict):
                raise FailureDiagnosisError("pytest_summary failing_tests entries must be objects")
            test_name = str(row.get("test_name") or "").strip()
            failure_message = str(row.get("failure_message") or "").strip()
            if not test_name or not failure_message:
                raise FailureDiagnosisError("pytest_summary failing_tests entries require test_name and failure_message")
            markers = [str(item).strip() for item in (row.get("markers") or []) if str(item).strip()]
            evidence_type = "test_expectation_drift" if "contract_behavior_changed" in markers else "unknown_failure"
            _append_evidence(
                evidence,
                source_surface="pytest",
                evidence_type=evidence_type,
                message=f"{test_name}: {failure_message}",
                artifact_ref=refs[0],
                details={"test_name": test_name, "markers": sorted(markers)},
            )

    elif failure_source_type in {"contract_enforcement", "control_surface_enforcement", "readiness_failure", "certification_failure"}:
        map_fields = [
            ("schema_example_failures", "schema_mismatch", "Schema/example failure"),
            ("producer_failures", "dependency_graph_violation", "Producer failure"),
            ("consumer_failures", "dependency_graph_violation", "Consumer failure"),
            ("fixture_failures", "dependency_graph_violation", "Fixture failure"),
            ("invariant_violations", "branch_policy_violation", "Invariant violation"),
            ("manifest_mismatches", "contract_registration_missing", "Manifest/registry mismatch"),
            ("authority_anchor_gaps", "contract_registration_missing", "Source authority anchor gap"),
            ("policy_composition_gaps", "dependency_graph_violation", "Policy composition gap"),
            ("corroboration_validation_gaps", "dependency_graph_violation", "Corroboration validation gap"),
            ("override_temporal_validation_gaps", "branch_policy_violation", "Override temporal validation gap"),
            ("certification_surface_gaps", "contract_registration_missing", "Certification surface gap"),
            ("missing_control_inputs", "contract_registration_missing", "Control surface input missing"),
            ("missing_required_surfaces", "contract_registration_missing", "Required surface missing"),
        ]
        for field_name, evidence_type, prefix in map_fields:
            for item in sorted(set(failure_payload.get(field_name) or [])):
                _append_evidence(
                    evidence,
                    source_surface=failure_source_type,
                    evidence_type=evidence_type,
                    message=f"{prefix}: {item}",
                    artifact_ref=refs[0],
                    details={"field": field_name, "value": item},
                )

    if not evidence:
        raise FailureDiagnosisError(
            f"missing required intake evidence for {failure_source_type}; refuse to fabricate diagnosis"
        )

    return {
        "failure_source_type": failure_source_type,
        "source_artifact_refs": refs,
        "observed_failure_summary": summary,
        "evidence": sorted(evidence, key=lambda item: (item["evidence_type"], item["message"], item["evidence_id"])),
    }


def _classify(evidence: list[dict[str, Any]]) -> tuple[str, list[str], list[dict[str, Any]]]:
    evidence_types = {row["evidence_type"] for row in evidence}
    matched_classes: list[str] = []
    reasoning_trace: list[dict[str, Any]] = []

    for rule in _RULES:
        matched_ids = [row["evidence_id"] for row in evidence if row["evidence_type"] in rule["matches"]]
        matched = bool(matched_ids)
        reasoning_trace.append(
            {
                "rule_id": rule["rule_id"],
                "matched": matched,
                "classification_candidate": rule["classification"],
                "matched_evidence_ids": sorted(matched_ids),
                "reason": rule["explanation"],
            }
        )
        if matched:
            matched_classes.append(rule["classification"])

    primary = matched_classes[0] if matched_classes else "unknown_failure"
    if primary not in _FAILURE_CLASSES:
        raise FailureDiagnosisError(f"classifier produced unsupported class '{primary}'")

    secondary = sorted({cls for cls in matched_classes[1:] if cls != primary})
    if not matched_classes:
        secondary = sorted(cls for cls in evidence_types if cls in _FAILURE_CLASSES and cls != primary)

    return primary, secondary, reasoning_trace


def build_failure_diagnosis_artifact(
    *,
    failure_source_type: str,
    source_artifact_refs: list[str],
    failure_payload: dict[str, Any],
    emitted_at: str | None = None,
    run_id: str = "run-fre-001",
    trace_id: str = "trace-fre-001",
    policy_id: str = "FRE-001.failure_diagnosis.v1",
    governing_ref: str = "docs/roadmaps/system_roadmap.md#batch-fre-01",
) -> dict[str, Any]:
    """Build a deterministic diagnosis artifact from governed failure evidence."""
    intake = normalize_failure_intake(
        failure_source_type=failure_source_type,
        source_artifact_refs=source_artifact_refs,
        failure_payload=failure_payload,
    )
    primary, secondary, reasoning_trace = _classify(intake["evidence"])

    smallest_safe_fix_class = _SMALLEST_SAFE_FIX[primary]
    recommended_repair_area = _RECOMMENDED_REPAIR_AREA[primary]
    blocking_severity = _BLOCKING_SEVERITY[primary]

    classification_key = {
        "failure_source_type": intake["failure_source_type"],
        "source_artifact_refs": intake["source_artifact_refs"],
        "evidence": [
            {
                "evidence_type": row["evidence_type"],
                "message": row["message"],
                "artifact_ref": row["artifact_ref"],
            }
            for row in intake["evidence"]
        ],
        "primary_root_cause": primary,
        "secondary_contributors": secondary,
        "smallest_safe_fix_class": smallest_safe_fix_class,
    }
    diagnosis_id = f"FDIAG-{_canonical_hash(classification_key)[:20]}"

    artifact = {
        "artifact_type": "failure_diagnosis_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.74",
        "diagnosis_id": diagnosis_id,
        "failure_source_type": intake["failure_source_type"],
        "source_artifact_refs": intake["source_artifact_refs"],
        "observed_failure_summary": intake["observed_failure_summary"],
        "evidence": intake["evidence"],
        "primary_root_cause": primary,
        "secondary_contributors": secondary,
        "smallest_safe_fix_class": smallest_safe_fix_class,
        "recommended_repair_area": recommended_repair_area,
        "blocking_severity": blocking_severity,
        "deterministic_reasoning_trace": reasoning_trace,
        "affected_surfaces": sorted({row["source_surface"] for row in intake["evidence"]}),
        "expected_validation_commands": [
            "pytest tests/test_failure_diagnosis_engine.py",
            "python scripts/run_contract_enforcement.py",
        ],
        "related_contract_refs": [
            "contracts/schemas/failure_diagnosis_artifact.schema.json",
            "contracts/standards-manifest.json",
        ],
        "emitted_at": emitted_at or _utc_now(),
        "trace": {
            "run_id": run_id,
            "trace_id": trace_id,
            "policy_id": policy_id,
            "governing_ref": governing_ref,
            "intake_hash": _canonical_hash(intake),
        },
    }

    _validate(artifact, "failure_diagnosis_artifact", label="failure_diagnosis_artifact")
    return artifact


def normalize_pytest_failure_packet(
    *,
    source_run_ref: str,
    command_ref: str,
    failing_tests: list[dict[str, Any]],
) -> dict[str, Any]:
    """Normalize failed test output into structured RIL-consumable packet."""
    if not isinstance(source_run_ref, str) or not source_run_ref.strip():
        raise FailureDiagnosisError("source_run_ref must be a non-empty string")
    if not isinstance(command_ref, str) or not command_ref.strip():
        raise FailureDiagnosisError("command_ref must be a non-empty string")
    if not isinstance(failing_tests, list) or not failing_tests:
        raise FailureDiagnosisError("failing_tests must be a non-empty list")

    normalized_tests: list[dict[str, Any]] = []
    for row in failing_tests:
        if not isinstance(row, dict):
            raise FailureDiagnosisError("failing_tests entries must be objects")
        test_name = str(row.get("test_name") or "").strip()
        message = str(row.get("failure_message") or "").strip()
        if not test_name or not message:
            raise FailureDiagnosisError("failing_tests entries require test_name and failure_message")
        normalized_tests.append(
            {
                "test_name": test_name,
                "failure_message": message,
                "artifact_ref": str(row.get("artifact_ref") or f"pytest_failure:{test_name}").strip(),
                "command_ref": str(row.get("command_ref") or command_ref).strip(),
                "markers": [str(item).strip() for item in (row.get("markers") or []) if str(item).strip()],
            }
        )

    failure_id = deterministic_id(
        prefix="flr",
        namespace="ril_failure_packet",
        payload={
            "source_run_ref": source_run_ref,
            "command_ref": command_ref,
            "failing_tests": normalized_tests,
        },
    )
    return {
        "failure_id": failure_id,
        "source_run_ref": source_run_ref.strip(),
        "source_test_refs": sorted(test["artifact_ref"] for test in normalized_tests),
        "failing_tests": sorted(normalized_tests, key=lambda item: item["test_name"]),
        "command_ref": command_ref.strip(),
    }


def build_failure_repair_candidate_artifact(
    *,
    failure_packet: dict[str, Any],
    failure_diagnosis_artifact: dict[str, Any],
    proposed_repair_ref: str,
    trace_refs: list[str],
) -> dict[str, Any]:
    """Build FRE bounded repair candidate artifact from structured failure and diagnosis."""
    if not isinstance(failure_packet, dict):
        raise FailureDiagnosisError("failure_packet must be an object")
    if not isinstance(failure_diagnosis_artifact, dict):
        raise FailureDiagnosisError("failure_diagnosis_artifact must be an object")
    if not isinstance(proposed_repair_ref, str) or not proposed_repair_ref.strip():
        raise FailureDiagnosisError("proposed_repair_ref must be non-empty")
    if not isinstance(trace_refs, list) or not trace_refs or not all(isinstance(item, str) and item.strip() for item in trace_refs):
        raise FailureDiagnosisError("trace_refs must be a non-empty list of strings")

    primary = str(failure_diagnosis_artifact.get("primary_root_cause") or "").strip()
    failure_id = str(failure_packet.get("failure_id") or "").strip()
    source_run_ref = str(failure_packet.get("source_run_ref") or "").strip()
    source_test_refs = failure_packet.get("source_test_refs")
    if not primary or not failure_id or not source_run_ref or not isinstance(source_test_refs, list) or not source_test_refs:
        raise FailureDiagnosisError("failure packet or diagnosis missing required fields")

    safe_to_repair = primary in _SAFE_REPAIRABLE_CLASSES
    bounded_scope = sorted(
        set(
            str(item).strip()
            for item in (
                failure_diagnosis_artifact.get("recommended_repair_paths")
                or failure_diagnosis_artifact.get("related_contract_refs")
                or []
            )
            if isinstance(item, str) and item.strip()
        )
    )
    if safe_to_repair and not bounded_scope:
        safe_to_repair = False

    artifact = {
        "artifact_type": "failure_repair_candidate_artifact",
        "schema_version": "1.0.0",
        "failure_id": failure_id,
        "source_run_ref": source_run_ref,
        "source_test_refs": sorted(set(str(item).strip() for item in source_test_refs if str(item).strip())),
        "failure_class": primary,
        "safe_to_repair": safe_to_repair,
        "bounded_scope": bounded_scope,
        "proposed_repair_ref": proposed_repair_ref.strip(),
        "trace_refs": sorted(set(item.strip() for item in trace_refs if item.strip())),
    }
    _validate(artifact, "failure_repair_candidate_artifact", label="failure_repair_candidate_artifact")
    return artifact


def load_failure_class_registry() -> dict[str, Any]:
    """Load and validate the canonical finite failure class registry."""
    registry = json.loads(
        (Path(__file__).resolve().parents[3] / "contracts" / "examples" / "failure_class_registry.json").read_text(
            encoding="utf-8"
        )
    )
    _validate(registry, "failure_class_registry", label="failure_class_registry")
    return registry


def build_eval_candidate_artifact(
    *,
    failure_diagnosis_artifact: dict[str, Any],
    trace_refs: list[str],
) -> dict[str, Any]:
    """Deterministically derive eval candidate from failure evidence without executing evals."""
    _validate(failure_diagnosis_artifact, "failure_diagnosis_artifact", label="failure_diagnosis_artifact")
    if not isinstance(trace_refs, list) or not trace_refs:
        raise FailureDiagnosisError("trace_refs must be a non-empty list")

    failure_class = str(failure_diagnosis_artifact["primary_root_cause"])
    proposed_eval_type = "schema" if failure_class == "schema_mismatch" else (
        "contract" if failure_class in {"contract_registration_missing", "test_expectation_drift"} else "integration"
    )
    seed = {
        "failure_class": failure_class,
        "source_failure_ref": f"failure_diagnosis_artifact:{failure_diagnosis_artifact['diagnosis_id']}",
        "evidence": failure_diagnosis_artifact["evidence"],
    }
    candidate_id = f"EVC-{_canonical_hash(seed)[:20]}"
    candidate = {
        "artifact_type": "eval_candidate_artifact",
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "failure_class": failure_class,
        "source_failure_ref": f"failure_diagnosis_artifact:{failure_diagnosis_artifact['diagnosis_id']}",
        "minimal_repro_case": failure_diagnosis_artifact["observed_failure_summary"],
        "expected_behavior": f"Failure class '{failure_class}' should be blocked by governed validation before merge.",
        "proposed_eval_type": proposed_eval_type,
        "trace_refs": sorted(set(trace_refs)),
    }
    _validate(candidate, "eval_candidate_artifact", label="eval_candidate_artifact")
    return candidate
