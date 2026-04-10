"""GRC foundation: readiness gating, failure packetization, and bounded repair handoff artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema, validate_artifact
from spectrum_systems.modules.runtime.lineage_authenticity import LineageAuthenticityError, verify_authenticity
from spectrum_systems.utils.deterministic_id import deterministic_id


class GovernedRepairFoundationError(ValueError):
    """Raised when governed repair foundation logic must fail closed."""


_CANONICAL_FAILURE_CLASSES = {
    "missing_artifact",
    "invalid_artifact_shape",
    "cross_artifact_mismatch",
    "authenticity_lineage_mismatch",
    "slice_contract_mismatch",
    "runtime_logic_defect",
    "policy_blocked",
    "retry_budget_exhausted",
}

_REPAIRABILITY_CLASSES = {"artifact_only", "slice_metadata", "runtime_code", "escalate"}


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise GovernedRepairFoundationError(f"{schema_name} failed schema validation: {details}")


def _normalize_ref_list(values: Any, *, field: str) -> list[str]:
    if not isinstance(values, list):
        raise GovernedRepairFoundationError(f"{field} must be a list")
    normalized = sorted({str(item).strip() for item in values if isinstance(item, str) and item.strip()})
    if not normalized:
        raise GovernedRepairFoundationError(f"{field} must include at least one non-empty entry")
    return normalized


def _classify_repairability(*, failure_class: str, touched_refs: list[str]) -> str:
    if failure_class == "runtime_logic_defect":
        return "runtime_code"
    if failure_class == "slice_contract_mismatch":
        return "slice_metadata"
    if failure_class in {"policy_blocked", "retry_budget_exhausted"}:
        return "escalate"
    if touched_refs:
        return "artifact_only"
    return "escalate"


def evaluate_slice_artifact_readiness(
    *,
    slice_id: str,
    owning_system: str,
    runtime_seam: str,
    required_artifacts: list[dict[str, str]],
    contract_invariants: list[str],
    expected_failure_classes: list[str],
    command: str,
) -> dict[str, Any]:
    """Produce fail-closed readiness result without executing slice work."""
    if not isinstance(slice_id, str) or not slice_id.strip():
        raise GovernedRepairFoundationError("slice_id must be a non-empty string")
    if not isinstance(command, str) or not command.strip():
        raise GovernedRepairFoundationError("command must be a non-empty string")

    blockers: list[dict[str, Any]] = []
    checked_refs: list[str] = []

    for artifact in required_artifacts:
        if not isinstance(artifact, dict):
            raise GovernedRepairFoundationError("required_artifacts entries must be objects")
        artifact_ref = str(artifact.get("artifact_ref") or "").strip()
        schema_name = str(artifact.get("schema") or "").strip()
        authenticity_issuer = str(artifact.get("authenticity_issuer") or "").strip()
        if not artifact_ref or not schema_name:
            raise GovernedRepairFoundationError("required_artifacts entries require artifact_ref and schema")
        checked_refs.append(artifact_ref)

        path = Path(artifact_ref)
        if not path.is_file():
            blockers.append(
                {
                    "failure_class": "missing_artifact",
                    "reason": f"missing required artifact: {artifact_ref}",
                    "artifact_refs": [artifact_ref],
                    "invariant_refs": [],
                }
            )
            continue

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            blockers.append(
                {
                    "failure_class": "invalid_artifact_shape",
                    "reason": f"artifact must be a JSON object: {artifact_ref}",
                    "artifact_refs": [artifact_ref],
                    "invariant_refs": [],
                }
            )
            continue

        try:
            validate_artifact(payload, schema_name)
        except Exception as exc:
            blockers.append(
                {
                    "failure_class": "invalid_artifact_shape",
                    "reason": f"schema validation failed for {artifact_ref}: {exc}",
                    "artifact_refs": [artifact_ref],
                    "invariant_refs": [],
                }
            )
            continue

        if authenticity_issuer:
            try:
                verify_authenticity(artifact=payload, expected_issuer=authenticity_issuer)
            except LineageAuthenticityError as exc:
                blockers.append(
                    {
                        "failure_class": "authenticity_lineage_mismatch",
                        "reason": f"authenticity verification failed for {artifact_ref}: {exc}",
                        "artifact_refs": [artifact_ref],
                        "invariant_refs": ["authenticity_lineage"],
                    }
                )

    if "control_decision_payload_nested" in contract_invariants and "decision['control_decision']" not in command:
        blockers.append(
            {
                "failure_class": "slice_contract_mismatch",
                "reason": "slice command contract mismatch: nested control_decision payload not wired",
                "artifact_refs": [],
                "invariant_refs": ["control_decision_payload_nested"],
            }
        )

    if "lineage_trace_alignment" in contract_invariants:
        trace_ids: set[str] = set()
        for artifact in required_artifacts:
            ref = str(artifact.get("artifact_ref") or "").strip()
            path = Path(ref)
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("trace_id"), str) and payload["trace_id"].strip():
                trace_ids.add(payload["trace_id"].strip())
        if len(trace_ids) > 1:
            blockers.append(
                {
                    "failure_class": "cross_artifact_mismatch",
                    "reason": "cross-artifact mismatch: required lineage artifacts disagree on trace_id",
                    "artifact_refs": checked_refs,
                    "invariant_refs": ["lineage_trace_alignment"],
                }
            )

    readiness = {
        "artifact_type": "artifact_readiness_result",
        "schema_version": "1.0.0",
        "readiness_id": deterministic_id(
            prefix="arr",
            namespace="grc_readiness",
            payload={"slice_id": slice_id, "blockers": blockers, "command": command},
        ),
        "slice_id": slice_id,
        "owning_system": owning_system,
        "runtime_seam": runtime_seam,
        "status": "ready" if not blockers else "blocked",
        "blocking_reasons": blockers,
        "checked_artifact_refs": sorted(set(checked_refs)),
        "contract_invariant_refs": sorted(set(contract_invariants)),
        "expected_failure_classes": sorted(set(expected_failure_classes)),
    }
    _validate(readiness, "artifact_readiness_result")
    return readiness


def build_execution_failure_packet(
    *,
    readiness_result: dict[str, Any],
    execution_refs: list[str],
    trace_refs: list[str],
    enforcement_refs: list[str],
    validation_refs: list[str],
    batch_id: str | None,
    umbrella_id: str | None,
    roadmap_context_ref: str | None,
) -> dict[str, Any]:
    """Canonical RIL-owned packetization from blocked readiness/execution surface."""
    _validate(readiness_result, "artifact_readiness_result")
    if readiness_result["status"] != "blocked":
        raise GovernedRepairFoundationError("execution failure packet requires blocked readiness surface")

    blockers = readiness_result["blocking_reasons"]
    if not blockers:
        raise GovernedRepairFoundationError("blocked readiness result must contain blocking_reasons")
    primary = str(blockers[0]["failure_class"])
    if primary not in _CANONICAL_FAILURE_CLASSES:
        raise GovernedRepairFoundationError(f"unsupported failure class for packetization: {primary}")

    affected_refs: list[str] = []
    for blocker in blockers:
        affected_refs.extend(str(ref) for ref in blocker.get("artifact_refs", []) if isinstance(ref, str) and ref.strip())

    packet = {
        "artifact_type": "execution_failure_packet",
        "schema_version": "1.0.0",
        "failure_packet_id": deterministic_id(
            prefix="efp",
            namespace="grc_failure_packet",
            payload={
                "slice_id": readiness_result["slice_id"],
                "readiness_id": readiness_result["readiness_id"],
                "primary_failure_class": primary,
            },
        ),
        "slice_id": readiness_result["slice_id"],
        "batch_id": batch_id,
        "umbrella_id": umbrella_id,
        "roadmap_context_ref": roadmap_context_ref,
        "readiness_ref": f"artifact_readiness_result:{readiness_result['readiness_id']}",
        "execution_refs": _normalize_ref_list(execution_refs, field="execution_refs"),
        "trace_refs": _normalize_ref_list(trace_refs, field="trace_refs"),
        "enforcement_refs": _normalize_ref_list(enforcement_refs, field="enforcement_refs"),
        "validation_refs": _normalize_ref_list(validation_refs, field="validation_refs"),
        "classified_failure_type": primary,
        "explanation": str(blockers[0]["reason"]),
        "affected_artifact_refs": sorted(set(affected_refs or readiness_result.get("checked_artifact_refs", []))),
        "repairability_hint": _classify_repairability(
            failure_class=primary,
            touched_refs=sorted(set(affected_refs)),
        ),
    }
    _validate(packet, "execution_failure_packet")
    return packet


def build_bounded_repair_candidate(
    *,
    failure_packet: dict[str, Any],
    max_scope_refs: int = 5,
) -> dict[str, Any]:
    """FRE bounded repair candidate generation from canonical failure packet."""
    _validate(failure_packet, "execution_failure_packet")
    if max_scope_refs < 1:
        raise GovernedRepairFoundationError("max_scope_refs must be >= 1")

    touched_refs = [
        str(ref).strip() for ref in failure_packet.get("affected_artifact_refs", []) if isinstance(ref, str) and ref.strip()
    ]
    if len(touched_refs) > max_scope_refs:
        raise GovernedRepairFoundationError("bounded repair candidate rejected: scope exceeds bounded authority")

    repairability_class = str(failure_packet["repairability_hint"])
    if repairability_class not in _REPAIRABILITY_CLASSES:
        raise GovernedRepairFoundationError("failure packet repairability_hint is not supported")

    no_go = None
    if repairability_class == "escalate":
        no_go = "repair scope exceeds bounded authority; escalation required"

    candidate = {
        "artifact_type": "bounded_repair_candidate_artifact",
        "schema_version": "1.0.0",
        "candidate_id": deterministic_id(
            prefix="brc",
            namespace="grc_bounded_repair_candidate",
            payload={
                "failure_packet_id": failure_packet["failure_packet_id"],
                "repairability_class": repairability_class,
                "scope": sorted(set(touched_refs)),
            },
        ),
        "failure_packet_ref": f"execution_failure_packet:{failure_packet['failure_packet_id']}",
        "failing_slice_ref": f"slice:{failure_packet['slice_id']}",
        "repairability_class": repairability_class,
        "minimal_repair_scope": sorted(set(touched_refs)),
        "touched_artifact_intent": sorted(set(touched_refs)),
        "bounded_rationale": f"Classified {failure_packet['classified_failure_type']} from canonical failure packet.",
        "recurrence_prevention_note": "Preserve artifact-first validation and prevent recurrence by enforcing readiness invariants.",
        "explicit_no_go": no_go,
    }
    _validate(candidate, "bounded_repair_candidate_artifact")
    return candidate


def build_cde_repair_continuation_input(
    *,
    failure_packet: dict[str, Any],
    repair_candidate: dict[str, Any],
) -> dict[str, Any]:
    """Derive CDE continuation input without generating repair content in CDE."""
    _validate(failure_packet, "execution_failure_packet")
    _validate(repair_candidate, "bounded_repair_candidate_artifact")

    continuation = {
        "artifact_type": "cde_repair_continuation_input",
        "schema_version": "1.0.0",
        "continuation_input_id": deterministic_id(
            prefix="cri",
            namespace="grc_cde_continuation",
            payload={
                "failure_packet_id": failure_packet["failure_packet_id"],
                "candidate_id": repair_candidate["candidate_id"],
            },
        ),
        "failure_packet_ref": f"execution_failure_packet:{failure_packet['failure_packet_id']}",
        "repair_candidate_ref": f"bounded_repair_candidate_artifact:{repair_candidate['candidate_id']}",
        "failing_slice_ref": f"slice:{failure_packet['slice_id']}",
        "repairability_class": repair_candidate["repairability_class"],
        "recommended_continuation": "stop_escalate"
        if repair_candidate["repairability_class"] == "escalate"
        else "continue_repair_bounded",
        "evidence_refs": sorted(
            set(
                failure_packet["execution_refs"]
                + failure_packet["trace_refs"]
                + failure_packet["enforcement_refs"]
                + failure_packet["validation_refs"]
            )
        ),
    }
    _validate(continuation, "cde_repair_continuation_input")
    return continuation


def build_tpa_repair_gating_input(
    *,
    failure_packet: dict[str, Any],
    repair_candidate: dict[str, Any],
    retry_budget_remaining: int,
    complexity_score: int,
    risk_level: str,
) -> dict[str, Any]:
    """Derive TPA repair gating input without planning or executing the repair."""
    _validate(failure_packet, "execution_failure_packet")
    _validate(repair_candidate, "bounded_repair_candidate_artifact")
    if retry_budget_remaining < 0:
        raise GovernedRepairFoundationError("retry_budget_remaining must be >= 0")
    if complexity_score < 0:
        raise GovernedRepairFoundationError("complexity_score must be >= 0")
    if risk_level not in {"low", "medium", "high"}:
        raise GovernedRepairFoundationError("risk_level must be one of low|medium|high")

    gating = {
        "artifact_type": "tpa_repair_gating_input",
        "schema_version": "1.0.0",
        "gating_input_id": deterministic_id(
            prefix="rgi",
            namespace="grc_tpa_gating",
            payload={
                "failure_packet_id": failure_packet["failure_packet_id"],
                "candidate_id": repair_candidate["candidate_id"],
                "retry_budget_remaining": retry_budget_remaining,
            },
        ),
        "failure_packet_ref": f"execution_failure_packet:{failure_packet['failure_packet_id']}",
        "repair_candidate_ref": f"bounded_repair_candidate_artifact:{repair_candidate['candidate_id']}",
        "repair_scope_refs": repair_candidate["minimal_repair_scope"],
        "complexity_score": complexity_score,
        "risk_level": risk_level,
        "retry_budget_remaining": retry_budget_remaining,
        "allowed_artifact_refs": repair_candidate["touched_artifact_intent"],
    }
    _validate(gating, "tpa_repair_gating_input")
    return gating


__all__ = [
    "GovernedRepairFoundationError",
    "build_bounded_repair_candidate",
    "build_cde_repair_continuation_input",
    "build_execution_failure_packet",
    "build_tpa_repair_gating_input",
    "evaluate_slice_artifact_readiness",
]
