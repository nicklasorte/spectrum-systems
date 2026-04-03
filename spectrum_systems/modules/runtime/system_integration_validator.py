"""Cross-layer integration validator for governed end-to-end system coherence (BATCH-Z)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class CoreSystemIntegrationValidationError(ValueError):
    """Raised when integration inputs are malformed or non-replayable."""


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise CoreSystemIntegrationValidationError(f"{schema_name} validation failed: {details}")


def _has_replay_chain(source_refs: dict[str, str]) -> bool:
    required = {
        "program_artifact",
        "review_control_signal",
        "eval_result",
        "context_bundle_v2",
        "tpa_gate",
        "roadmap_execution_loop_validation",
        "roadmap_multi_batch_run_result",
        "control_decision",
        "certification_pack",
    }
    missing = [key for key in sorted(required) if not isinstance(source_refs.get(key), str) or not source_refs[key].strip()]
    return not missing


def _normalize_source_refs(source_refs: dict[str, str]) -> dict[str, str]:
    required = [
        "program_artifact",
        "review_control_signal",
        "eval_result",
        "context_bundle_v2",
        "tpa_gate",
        "roadmap_execution_loop_validation",
        "roadmap_multi_batch_run_result",
        "control_decision",
        "certification_pack",
    ]
    normalized: dict[str, str] = {}
    for key in required:
        value = source_refs.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()
        else:
            normalized[key] = f"missing:{key}"
    for key in sorted(source_refs):
        value = source_refs[key]
        if key not in normalized and isinstance(value, str) and value.strip():
            normalized[key] = value.strip()
    return normalized


def _trace_navigation(
    *,
    trace_id: str,
    source_refs: dict[str, str],
    blocking_conditions: list[str],
    replay_ready: bool,
) -> dict[str, Any]:
    ordered_artifacts = [
        source_refs.get("program_artifact", "missing:program_artifact"),
        source_refs.get("review_control_signal", "missing:review_control_signal"),
        source_refs.get("context_bundle_v2", "missing:context_bundle_v2"),
        source_refs.get("tpa_gate", "missing:tpa_gate"),
        source_refs.get("roadmap_execution_loop_validation", "missing:roadmap_execution_loop_validation"),
        source_refs.get("roadmap_multi_batch_run_result", "missing:roadmap_multi_batch_run_result"),
        source_refs.get("control_decision", "missing:control_decision"),
        source_refs.get("certification_pack", "missing:certification_pack"),
    ]
    decision_points = [
        "PRG:program_artifact_constraints",
        "RVW:review_gate_assessment",
        "CTX:context_validation",
        "TPA:tpa_gate_decision",
        "RDX:bounded_execution_outcome",
        "CONTROL:control_decision",
        "CERT:certification_status",
    ]
    layer_transitions = [
        "PRG->RVW",
        "RVW->CTX",
        "CTX->TPA",
        "TPA->RDX",
        "RDX->CONTROL",
        "CONTROL->CERT",
    ]
    replay_entry_points = {
        "replay_from_context": {
            "required_artifacts": [source_refs.get("context_bundle_v2", "missing:context_bundle_v2"), source_refs.get("tpa_gate", "missing:tpa_gate")],
            "trace_refs": [trace_id, source_refs.get("context_bundle_v2", "missing:context_bundle_v2")],
        },
        "replay_from_plan": {
            "required_artifacts": [
                source_refs.get("program_artifact", "missing:program_artifact"),
                source_refs.get("review_control_signal", "missing:review_control_signal"),
                source_refs.get("roadmap_execution_loop_validation", "missing:roadmap_execution_loop_validation"),
            ],
            "trace_refs": [trace_id, source_refs.get("roadmap_execution_loop_validation", "missing:roadmap_execution_loop_validation")],
        },
        "replay_from_execution": {
            "required_artifacts": [
                source_refs.get("roadmap_multi_batch_run_result", "missing:roadmap_multi_batch_run_result"),
                source_refs.get("control_decision", "missing:control_decision"),
                source_refs.get("certification_pack", "missing:certification_pack"),
            ],
            "trace_refs": [trace_id, source_refs.get("roadmap_multi_batch_run_result", "missing:roadmap_multi_batch_run_result")],
        },
        "replay_from_failure": {
            "required_artifacts": sorted(set(blocking_conditions + [source_refs.get("control_decision", "missing:control_decision")])),
            "trace_refs": [trace_id, source_refs.get("control_decision", "missing:control_decision")],
        },
    }
    return {
        "trace_id": trace_id,
        "execution_path": ordered_artifacts,
        "decision_points": decision_points,
        "influencing_artifacts": sorted(set(ordered_artifacts + [source_refs.get("eval_result", "missing:eval_result")])),
        "layer_transitions": layer_transitions,
        "replay_entry_points": replay_entry_points,
        "replay_ready": replay_ready,
    }


def validate_core_system_integration(
    *,
    program_artifact: dict[str, Any],
    review_control_signal: dict[str, Any],
    eval_result: dict[str, Any],
    context_bundle: dict[str, Any],
    tpa_gate: dict[str, Any],
    roadmap_loop_validation: dict[str, Any],
    roadmap_multi_batch_result: dict[str, Any],
    control_decision: dict[str, Any],
    certification_pack: dict[str, Any],
    validation_scope: dict[str, Any],
    trace_id: str,
    source_refs: dict[str, str],
    created_at: str | None = None,
) -> dict[str, Any]:
    """Validate PRG→RVW→CTX→TPA→MAP/RDX→control/certification coherence fail-closed."""

    if not isinstance(trace_id, str) or not trace_id.strip():
        raise CoreSystemIntegrationValidationError("trace_id is required")

    exercised_layers = ["PRG", "RVW", "RPT", "CTX", "TPA", "MAP", "RDX", "CONTROL", "CERT"]
    findings: list[dict[str, str]] = []

    def add_finding(*, code: str, message: str, layer: str, severity: str) -> None:
        findings.append(
            {
                "code": code,
                "message": message,
                "layer": layer,
                "severity": severity,
            }
        )

    # Authority invariants.
    if str(review_control_signal.get("gate_assessment") or "") == "PASS" and str(control_decision.get("decision") or "") in {"block", "freeze"}:
        pass
    if str(review_control_signal.get("authorizes_execution") or "").lower() in {"true", "yes"}:
        add_finding(
            code="AUTH_REVIEW_DIRECT_AUTHORIZATION",
            message="review signal attempted direct authorization",
            layer="RVW",
            severity="error",
        )
    if bool(context_bundle.get("control_override")):
        add_finding(
            code="AUTH_CONTEXT_CONTROL_OVERRIDE",
            message="context attempted to override control decision",
            layer="CTX",
            severity="error",
        )
    if str(program_artifact.get("override_control") or "").lower() in {"block", "freeze", "allow"}:
        add_finding(
            code="AUTH_PROGRAM_OVERRIDE",
            message="program attempted to override control authority",
            layer="PRG",
            severity="error",
        )
    if bool(tpa_gate.get("gate_replaces_control", False)):
        add_finding(
            code="AUTH_TPA_REPLACES_CONTROL",
            message="TPA gate attempted to replace control",
            layer="TPA",
            severity="error",
        )

    # Constraint propagation invariants.
    if not bool(roadmap_multi_batch_result.get("program_constraints_applied", False)):
        add_finding(
            code="PROP_PROGRAM_CONSTRAINTS_MISSING",
            message="program constraints did not reach roadmap execution",
            layer="MAP",
            severity="error",
        )
    if not bool(control_decision.get("review_eval_ingested", False)):
        add_finding(
            code="PROP_REVIEW_EVAL_NOT_INGESTED",
            message="review findings were not propagated into eval/control",
            layer="CONTROL",
            severity="error",
        )
    if not isinstance(tpa_gate.get("context_bundle_ref"), str) or not str(tpa_gate.get("context_bundle_ref")).strip():
        add_finding(
            code="PROP_CTX_TO_TPA_MISSING",
            message="TPA gate missing context bundle linkage",
            layer="TPA",
            severity="error",
        )
    if bool(tpa_gate.get("speculative_expansion_detected", False)):
        add_finding(
            code="PROP_TPA_UNBOUNDED",
            message="TPA output indicates unbounded speculative expansion",
            layer="TPA",
            severity="error",
        )

    # Determinism + replay invariants.
    deterministic_fingerprint = _hash(
        {
            "program": program_artifact,
            "review": review_control_signal,
            "eval": eval_result,
            "context": context_bundle,
            "tpa": tpa_gate,
            "loop": roadmap_loop_validation,
            "multi_batch": roadmap_multi_batch_result,
            "control": control_decision,
            "cert": certification_pack,
            "scope": validation_scope,
            "source_refs": source_refs,
        }
    )

    if str(roadmap_loop_validation.get("determinism_status") or "") != "deterministic":
        add_finding(
            code="DETERMINISM_LOOP_NON_DETERMINISTIC",
            message="roadmap loop reported non-deterministic status",
            layer="RDX",
            severity="error",
        )

    if str(roadmap_multi_batch_result.get("stop_reason") or "") == "silent_continuation":
        add_finding(
            code="BOUND_MULTI_BATCH_DRIFT",
            message="multi-batch execution reported silent continuation",
            layer="RDX",
            severity="error",
        )

    if str(control_decision.get("decision") or "") in {"block", "freeze"} and bool(roadmap_multi_batch_result.get("batches_executed_count", 0)):
        add_finding(
            code="AUTH_CONTROL_BYPASS",
            message="execution proceeded despite control block/freeze",
            layer="CONTROL",
            severity="error",
        )

    replay_ready = _has_replay_chain(source_refs)
    if not replay_ready:
        add_finding(
            code="REPLAY_CHAIN_INCOMPLETE",
            message="integration replay chain missing required source references",
            layer="CERT",
            severity="error",
        )

    if str(certification_pack.get("certification_status") or "") not in {"complete", "pass"}:
        add_finding(
            code="CERTIFICATION_INCOMPLETE",
            message="certification layer did not complete",
            layer="CERT",
            severity="error",
        )

    blocking_conditions = sorted({item["code"] for item in findings if item["severity"] == "error"})
    authority_boundary_status = "bounded" if not any(code.startswith("AUTH_") for code in blocking_conditions) else "violated"
    determinism_status = "deterministic" if "DETERMINISM_LOOP_NON_DETERMINISTIC" not in blocking_conditions else "non_deterministic"
    replay_status = "replayable" if replay_ready else "not_replayable"

    normalized_source_refs = _normalize_source_refs(source_refs)
    trace_navigation = _trace_navigation(
        trace_id=trace_id,
        source_refs=normalized_source_refs,
        blocking_conditions=blocking_conditions,
        replay_ready=replay_ready,
    )

    artifact = {
        "validation_id": f"CSIV-{_hash({**validation_scope, 'trace_id': trace_id, 'fingerprint': deterministic_fingerprint})[:12].upper()}",
        "schema_version": "1.1.0",
        "exercised_layers": exercised_layers,
        "validation_scope": {
            "batch_id": str(validation_scope.get("batch_id") or ""),
            "run_id": str(validation_scope.get("run_id") or ""),
            "mode": str(validation_scope.get("mode") or "governed_integration"),
        },
        "determinism_status": determinism_status,
        "replay_status": replay_status,
        "authority_boundary_status": authority_boundary_status,
        "cross_layer_findings": sorted(findings, key=lambda item: (item["severity"], item["layer"], item["code"])),
        "blocking_conditions": blocking_conditions,
        "deterministic_outcome": "deterministic" if not blocking_conditions else "failed_closed",
        "replayability_fingerprint": deterministic_fingerprint,
        "trace_navigation": trace_navigation,
        "upstream_refs": sorted(set(normalized_source_refs.values())),
        "downstream_refs": [f"core_system_integration_validation:CSIV-{_hash({**validation_scope, 'trace_id': trace_id, 'fingerprint': deterministic_fingerprint})[:12].upper()}"],
        "related_artifacts": sorted(set(normalized_source_refs.values())),
        "created_at": created_at or _utc_now(),
        "trace_id": trace_id,
        "source_refs": normalized_source_refs,
    }
    _validate_schema(artifact, "core_system_integration_validation")
    return artifact


__all__ = [
    "CoreSystemIntegrationValidationError",
    "validate_core_system_integration",
]
