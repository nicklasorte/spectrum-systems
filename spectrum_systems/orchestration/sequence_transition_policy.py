"""Authoritative fail-closed transition policy for the 3-slice sequential trust path."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.trust_spine_invariants import (
    validate_trust_spine_evidence_completeness,
    validate_trust_spine_invariants,
)
from spectrum_systems.modules.runtime.stage_contract_runtime import (
    evaluate_stage_transition_readiness,
    load_stage_contract,
)
from spectrum_systems.modules.runtime.hnx_execution_state import evaluate_long_running_policy

SEQUENCE_STATES = {
    "admitted",
    "executing_slice_1",
    "executing_slice_2",
    "executing_slice_3",
    "review_pending",
    "remediation_pending",
    "certification_pending",
    "promoted",
    "blocked",
    "frozen",
}

_ALLOWED: dict[str, set[str]] = {
    "admitted": {"executing_slice_1", "blocked", "frozen"},
    "executing_slice_1": {"executing_slice_2", "blocked", "frozen"},
    "executing_slice_2": {"executing_slice_3", "blocked", "frozen"},
    "executing_slice_3": {"review_pending", "blocked", "frozen"},
    "review_pending": {"remediation_pending", "certification_pending", "blocked", "frozen"},
    "remediation_pending": {"certification_pending", "blocked", "frozen"},
    "certification_pending": {"promoted", "blocked", "frozen"},
    "promoted": {"promoted"},
    "blocked": {"blocked", "frozen"},
    "frozen": {"frozen"},
}


@dataclass(frozen=True)
class SequenceTransitionDecision:
    allowed: bool
    reason: str | None = None


def _path_exists(value: Any) -> bool:
    return isinstance(value, str) and value != "" and Path(value).is_file()


def _load_json_if_path(path_value: Any) -> dict[str, Any] | None:
    if not _path_exists(path_value):
        return None
    try:
        payload = json.loads(Path(path_value).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _ref_from_manifest(manifest: dict[str, Any], key: str) -> str | None:
    refs = manifest.get("done_certification_input_refs")
    if not isinstance(refs, dict):
        return None
    value = refs.get(key)
    if isinstance(value, str) and value:
        return value
    return None


_BLOCK_VOCAB = frozenset({"deny", "block", "blocked", "freeze", "frozen", "hold", "require_review"})


def _normalized_block_value(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_blocking_value(value: Any) -> bool:
    return _normalized_block_value(value) in _BLOCK_VOCAB


def _authority_path_mode(manifest: dict[str, Any]) -> str:
    value = manifest.get("authority_path_mode")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "active_runtime"


def _validate_policy_authority(policy_payload: dict[str, Any]) -> tuple[bool, str | None]:
    decision = policy_payload.get("decision")
    system_response = policy_payload.get("system_response")
    decision_norm = _normalized_block_value(decision)
    response_norm = _normalized_block_value(system_response)
    if not decision_norm and not response_norm:
        return False, "promotion requires policy_ref decision/system_response authority"
    if decision is not None and not decision_norm:
        return False, "promotion requires non-empty policy_ref decision when present"
    if system_response is not None and not response_norm:
        return False, "promotion requires non-empty policy_ref system_response when present"
    contradictory = {
        ("allow", "block"),
        ("allow", "freeze"),
        ("deny", "allow"),
        ("require_review", "allow"),
    }
    if (decision_norm, response_norm) in contradictory:
        return False, "promotion blocked: policy_ref contains contradictory decision/system_response authority"
    if _is_blocking_value(decision_norm) or _is_blocking_value(response_norm):
        blocked_by = decision_norm if _is_blocking_value(decision_norm) else response_norm
        return False, f"promotion blocked by control authority decision ({blocked_by})"
    return True, None


def _validate_replay_authority(replay_payload: dict[str, Any]) -> tuple[bool, str | None]:
    status = _normalized_block_value(replay_payload.get("status"))
    if status == "blocked":
        return False, "promotion blocked by replay_result_ref status=blocked"
    if replay_payload.get("prerequisites_valid") is False:
        return False, "promotion blocked by replay_result_ref prerequisites_valid=false"
    return True, None


def _coverage_required_deficit(coverage_payload: dict[str, Any]) -> bool:
    required_gaps = coverage_payload.get("required_slice_gaps")
    if isinstance(required_gaps, list) and required_gaps:
        return True
    uncovered = coverage_payload.get("uncovered_required_slices")
    if isinstance(uncovered, list) and uncovered:
        return True
    coverage_gaps = coverage_payload.get("coverage_gaps")
    if isinstance(coverage_gaps, list):
        for entry in coverage_gaps:
            if not isinstance(entry, dict):
                continue
            severity = _normalized_block_value(entry.get("severity"))
            gap_type = _normalized_block_value(entry.get("gap_type"))
            is_required = entry.get("required") is True or "required" in gap_type
            if is_required and severity in {"high", "critical"}:
                return True
            if is_required and _normalized_block_value(entry.get("status")) in {"missing", "uncovered", "gap"}:
                return True
    return False


def _promotion_authority_gate(manifest: dict[str, Any]) -> tuple[bool, str | None]:
    refs = manifest.get("done_certification_input_refs")
    refs_dict = refs if isinstance(refs, dict) else {}
    closure_bundle_ref = manifest.get("hard_gate_falsification_record_path")
    if not isinstance(closure_bundle_ref, str) or not closure_bundle_ref.strip():
        closure_bundle_ref = refs_dict.get("hard_gate_falsification_record_path")
    gate_proof_ref = "embedded" if isinstance(manifest.get("control_loop_gate_proof"), dict) else refs_dict.get("certification_pack_ref")
    if not isinstance(closure_bundle_ref, str) or not closure_bundle_ref.strip():
        closure_bundle_ref = refs_dict.get("certification_pack_ref")
    completeness_result = validate_trust_spine_evidence_completeness(
        refs={
            "replay_result_ref": refs_dict.get("replay_result_ref"),
            "policy_ref": refs_dict.get("policy_ref"),
            "enforcement_result_ref": refs_dict.get("enforcement_result_ref"),
            "eval_coverage_summary_ref": refs_dict.get("eval_coverage_summary_ref"),
            "certification_pack_ref": refs_dict.get("certification_pack_ref"),
            "gate_proof_ref": gate_proof_ref,
            "closure_bundle_ref": closure_bundle_ref,
        },
        target_surface="promotion",
        authority_path_mode=_authority_path_mode(manifest),
    )
    if not completeness_result.passed:
        required_refs_suffix = (
            " (required_refs=replay_result_ref,policy_ref,enforcement_result_ref,eval_coverage_summary_ref)"
        )
        missing_suffix = ""
        if completeness_result.missing_refs:
            missing_suffix = " (missing_refs=" + ",".join(completeness_result.missing_refs) + ")"
        return (
            False,
            "promotion blocked by trust-spine evidence completeness: "
            + "; ".join(completeness_result.blocking_reasons)
            + required_refs_suffix
            + missing_suffix,
        )

    replay_ref = _ref_from_manifest(manifest, "replay_result_ref")
    if not _path_exists(replay_ref):
        return False, "promotion requires done_certification_input_refs.replay_result_ref"
    replay_payload = _load_json_if_path(replay_ref)
    if not isinstance(replay_payload, dict):
        return False, "promotion requires readable replay_result_ref artifact"
    replay_valid, replay_error = _validate_replay_authority(replay_payload)
    if not replay_valid:
        return False, replay_error

    policy_ref = _ref_from_manifest(manifest, "policy_ref")
    if not _path_exists(policy_ref):
        return False, "promotion requires done_certification_input_refs.policy_ref"

    policy_payload = _load_json_if_path(policy_ref)
    if not isinstance(policy_payload, dict):
        return False, "promotion requires readable control decision policy_ref artifact"
    policy_valid, policy_error = _validate_policy_authority(policy_payload)
    if not policy_valid:
        return False, policy_error

    enforcement_ref = _ref_from_manifest(manifest, "enforcement_result_ref")
    if not _path_exists(enforcement_ref):
        return False, "promotion requires done_certification_input_refs.enforcement_result_ref"
    enforcement_payload = _load_json_if_path(enforcement_ref)
    if not isinstance(enforcement_payload, dict):
        return False, "promotion requires readable enforcement_result_ref artifact"
    final_status = enforcement_payload.get("final_status") or enforcement_payload.get("enforcement_status")
    if _is_blocking_value(final_status):
        return False, f"promotion blocked by consumed enforcement result ({_normalized_block_value(final_status)})"

    coverage_ref = _ref_from_manifest(manifest, "eval_coverage_summary_ref")
    if not _path_exists(coverage_ref):
        return False, "promotion requires done_certification_input_refs.eval_coverage_summary_ref"
    coverage_payload = _load_json_if_path(coverage_ref)
    if not isinstance(coverage_payload, dict):
        return False, "promotion requires readable eval_coverage_summary_ref artifact"
    if _coverage_required_deficit(coverage_payload):
        return False, "promotion blocked: required eval coverage gaps present"

    invariant_result = validate_trust_spine_invariants(
        replay_result=replay_payload,
        evaluation_control_decision=policy_payload,
        enforcement_result=enforcement_payload,
        eval_coverage_summary=coverage_payload,
        gate_proof_evidence=manifest.get("control_loop_gate_proof"),
        done_certification_record=None,
        target_surface="promotion",
    )
    if not invariant_result.passed:
        return (
            False,
            "promotion blocked by trust-spine invariant violations: "
            + "; ".join(invariant_result.blocking_reasons),
        )

    return True, None


def _has_traceability(manifest: dict[str, Any]) -> bool:
    trace_id = manifest.get("sequence_trace_id")
    lineage = manifest.get("sequence_lineage")
    return isinstance(trace_id, str) and trace_id and isinstance(lineage, list) and bool(lineage)


def _reports_count(manifest: dict[str, Any]) -> int:
    reports = manifest.get("execution_report_paths")
    if not isinstance(reports, list):
        return 0
    return sum(1 for item in reports if _path_exists(item))


def _gate_proof_passes(manifest: dict[str, Any]) -> tuple[bool, str | None]:
    gate = manifest.get("control_loop_gate_proof")
    if not isinstance(gate, dict):
        refs = manifest.get("done_certification_input_refs")
        pack_ref = refs.get("certification_pack_ref") if isinstance(refs, dict) else None
        if isinstance(pack_ref, str) and pack_ref:
            pack_path = Path(pack_ref)
            if pack_path.is_file():
                try:
                    gate = json.loads(pack_path.read_text(encoding="utf-8")).get("gate_proof_evidence")
                except (OSError, json.JSONDecodeError):
                    return False, "promotion requires readable certification pack gate_proof_evidence"
    if not isinstance(gate, dict):
        return False, "promotion requires control_loop_gate_proof"
    required_true = (
        "severity_linkage_complete",
        "deterministic_transition_consumption",
        "policy_caused_action_observed",
        "recurrence_prevention_linked",
        "failure_binding_required_for_progression",
        "missing_binding_blocks_progression",
        "advisory_only_learning_rejected",
        "transition_policy_consumes_binding_deterministically",
    )
    for field in required_true:
        if gate.get(field) is not True:
            return False, f"promotion requires gate proof field {field}=true"
    for refs_key in (
        "severity_linkage_refs",
        "transition_consumption_refs",
        "policy_action_refs",
        "recurrence_prevention_refs",
    ):
        refs = gate.get(refs_key)
        if not isinstance(refs, list) or not refs:
            return False, f"promotion requires gate proof evidence in {refs_key}"
    return True, None



def _hard_gate_falsification_passes(manifest: dict[str, Any]) -> tuple[bool, str | None]:
    artifact = manifest.get("hard_gate_falsification")
    certification_pack: dict[str, Any] | None = None
    falsification_ref: str | None = None
    refs = manifest.get("done_certification_input_refs")
    if isinstance(refs, dict):
        candidate_pack_ref = refs.get("certification_pack_ref")
        if _path_exists(candidate_pack_ref):
            try:
                certification_pack = json.loads(Path(candidate_pack_ref).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return False, "promotion requires readable certification_pack_ref for falsification resolution"
            gate = certification_pack.get("gate_proof_evidence")
            if isinstance(gate, dict):
                falsification_refs = gate.get("hard_gate_falsification_refs")
                if isinstance(falsification_refs, list) and falsification_refs:
                    first_ref = falsification_refs[0]
                    if isinstance(first_ref, str) and first_ref:
                        falsification_ref = first_ref
    if not isinstance(artifact, dict):
        ref = manifest.get("hard_gate_falsification_record_path")
        if not isinstance(ref, str) or not ref:
            if isinstance(refs, dict):
                ref = refs.get("hard_gate_falsification_record_path")
        if (not isinstance(ref, str) or not ref) and isinstance(falsification_ref, str):
            ref = falsification_ref
        if _path_exists(ref):
            try:
                artifact = json.loads(Path(ref).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return False, "promotion requires readable hard_gate_falsification_record_path"
    if not isinstance(artifact, dict):
        return False, "promotion requires hard_gate_falsification evidence"
    if artifact.get("artifact_type") != "pqx_hard_gate_falsification_record":
        return False, "promotion requires pqx_hard_gate_falsification_record artifact"
    if artifact.get("overall_result") != "pass":
        return False, "promotion blocked: hard gate falsification result is fail"
    checks = artifact.get("checks")
    if not isinstance(checks, list) or len(checks) < 8:
        return False, "promotion requires complete hard-gate falsification checks"
    if any(check.get("passed") is not True for check in checks if isinstance(check, dict)):
        return False, "promotion blocked: one or more hard-gate falsification checks failed"
    return True, None




def _obedience_gate(manifest: dict[str, Any]) -> tuple[bool, str | None]:
    refs = manifest.get("done_certification_input_refs")
    obedience_ref = manifest.get("control_surface_obedience_result_ref")
    if (not isinstance(obedience_ref, str) or not obedience_ref.strip()) and isinstance(refs, dict):
        obedience_ref = refs.get("control_surface_obedience_result_ref")
    if not isinstance(obedience_ref, str) or not obedience_ref.strip():
        return True, None
    if not _path_exists(obedience_ref):
        return False, "promotion blocked: control_surface_obedience_result_ref is unreadable"
    try:
        payload = json.loads(Path(obedience_ref).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "promotion blocked: control_surface_obedience_result_ref is unreadable"
    errors = sorted(
        Draft202012Validator(load_schema("control_surface_obedience_result")).iter_errors(payload),
        key=lambda err: str(list(err.absolute_path)),
    )
    if errors:
        return False, "promotion blocked: control_surface_obedience_result failed schema validation"
    if payload.get("overall_decision") == "BLOCK":
        return False, "promotion blocked by control_surface_obedience_result overall_decision=BLOCK"
    return True, None


def _cohesion_gate(manifest: dict[str, Any]) -> tuple[bool, str | None]:
    refs = manifest.get("done_certification_input_refs")
    refs_dict = refs if isinstance(refs, dict) else {}
    authority_mode = _authority_path_mode(manifest)
    cohesion_ref = manifest.get("trust_spine_evidence_cohesion_result_ref")
    if (not isinstance(cohesion_ref, str) or not cohesion_ref.strip()) and isinstance(refs_dict, dict):
        cohesion_ref = refs_dict.get("trust_spine_evidence_cohesion_result_ref")

    if authority_mode == "active_runtime":
        if not isinstance(cohesion_ref, str) or not cohesion_ref.strip():
            return False, "promotion requires done_certification_input_refs.trust_spine_evidence_cohesion_result_ref"
    elif not isinstance(cohesion_ref, str) or not cohesion_ref.strip():
        return True, None

    if not _path_exists(cohesion_ref):
        return False, "promotion blocked: trust_spine_evidence_cohesion_result_ref is unreadable"
    try:
        payload = json.loads(Path(cohesion_ref).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "promotion blocked: trust_spine_evidence_cohesion_result_ref is unreadable"
    errors = sorted(
        Draft202012Validator(load_schema("trust_spine_evidence_cohesion_result")).iter_errors(payload),
        key=lambda err: str(list(err.absolute_path)),
    )
    if errors:
        return False, "promotion blocked: trust_spine_evidence_cohesion_result failed schema validation"
    if payload.get("overall_decision") == "BLOCK":
        return False, "promotion blocked by trust_spine_evidence_cohesion_result overall_decision=BLOCK"
    return True, None


def _stage_contract_input_counts(manifest: dict[str, Any]) -> dict[str, int]:
    refs = manifest.get("done_certification_input_refs")
    refs_dict = refs if isinstance(refs, dict) else {}

    def _ref_present(key: str) -> int:
        value = refs_dict.get(key)
        return 1 if _path_exists(value) else 0

    return {
        "replay_result": _ref_present("replay_result_ref"),
        "evaluation_control_decision": _ref_present("policy_ref"),
        "evaluation_enforcement_action": _ref_present("enforcement_result_ref"),
        "eval_coverage_summary": _ref_present("eval_coverage_summary_ref"),
        "review_control_signal": _ref_present("review_control_signal_ref"),
        "trust_spine_evidence_cohesion_result": _ref_present("trust_spine_evidence_cohesion_result_ref"),
        "done_certification_record": 1 if _path_exists(manifest.get("certification_record_path")) else 0,
        "hard_gate_falsification_record": 1 if _path_exists(manifest.get("hard_gate_falsification_record_path")) else 0,
    }


def _stage_contract_eval_statuses(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        "certification_status": "pass" if manifest.get("certification_status") == "passed" else "fail",
        "promotion_control_allow": "pass" if manifest.get("control_allow_promotion") is True else "fail",
    }


def _continuity_gate(manifest: dict[str, Any], contract: dict[str, Any]) -> tuple[bool, str | None]:
    policy_result = evaluate_long_running_policy(
        stage_contract=contract,
        checkpoint_record=manifest.get("checkpoint_record") if isinstance(manifest.get("checkpoint_record"), dict) else None,
        handoff_artifact=manifest.get("handoff_artifact") if isinstance(manifest.get("handoff_artifact"), dict) else None,
        request_resume=manifest.get("request_resume") is True,
        checkpoint_age_minutes=int(manifest.get("checkpoint_age_minutes") or 0),
        has_resume_validation_evidence=manifest.get("has_resume_validation_evidence") is True,
        request_async_wait=manifest.get("request_async_wait") is True,
        wait_elapsed_minutes=int(manifest.get("wait_elapsed_minutes") or 0),
    )
    if policy_result.get("allowed") is True:
        return True, None
    reason_codes = policy_result.get("reason_codes") or []
    failures = (policy_result.get("validation_failures") or []) + (policy_result.get("policy_failures") or [])
    reason = ",".join(reason_codes + failures) if (reason_codes or failures) else "HNX_LONG_RUNNING_POLICY_BLOCKED"
    state = policy_result.get("recommended_state") or "block"
    return False, f"continuity gate blocked: {reason} ({state})"


def _stage_contract_gate(manifest: dict[str, Any], target_state: str) -> tuple[bool, str | None]:
    contract_path = manifest.get("stage_contract_path")
    if not isinstance(contract_path, str) or not contract_path.strip():
        return True, None

    if target_state in {"blocked", "frozen"}:
        return True, None

    if not _path_exists(contract_path):
        return False, "stage-contract gate blocked: unreadable stage_contract_path"

    try:
        contract = load_stage_contract(contract_path)
    except Exception as exc:  # noqa: BLE001
        return False, f"stage-contract gate blocked: invalid stage contract ({exc})"

    continuity_ok, continuity_error = _continuity_gate(manifest, contract)
    if not continuity_ok:
        return False, continuity_error

    readiness = evaluate_stage_transition_readiness(
        contract_payload=contract,
        present_input_artifacts=_stage_contract_input_counts(manifest),
        present_output_artifacts={},
        eval_status_map=_stage_contract_eval_statuses(manifest),
        trace_complete=_has_traceability(manifest),
        policy_violation=manifest.get("decision_blocked") is True,
        budget_status=manifest.get("stage_contract_budget_status") if isinstance(manifest.get("stage_contract_budget_status"), dict) else {},
    )

    if readiness.ready_to_advance:
        return True, None

    reason = ",".join(readiness.reason_codes) if readiness.reason_codes else "STAGE_CONTRACT_READINESS_BLOCKED"
    return False, f"stage-contract gate blocked: {reason} ({readiness.recommended_state})"


def _review_signal_gate(manifest: dict[str, Any]) -> tuple[bool, str | None]:
    policy = manifest.get("review_signal_policy")
    policy_dict = policy if isinstance(policy, dict) else {}
    review_required = policy_dict.get("required_for_promotion") is True
    review_ref = manifest.get("review_control_signal_ref")
    if not isinstance(review_ref, str) or not review_ref.strip():
        refs = manifest.get("done_certification_input_refs")
        if isinstance(refs, dict):
            review_ref = refs.get("review_control_signal_ref")
    if not isinstance(review_ref, str) or not review_ref.strip():
        if review_required:
            return False, "promotion blocked: required review_control_signal is missing"
        return True, None
    if not _path_exists(review_ref):
        return False, "promotion blocked: review_control_signal_ref is unreadable"
    try:
        payload = json.loads(Path(review_ref).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "promotion blocked: review_control_signal_ref is unreadable"
    errors = sorted(
        Draft202012Validator(load_schema("review_control_signal")).iter_errors(payload),
        key=lambda err: str(list(err.absolute_path)),
    )
    if errors:
        return False, "promotion blocked: review_control_signal failed schema validation"
    gate_assessment = str(payload.get("gate_assessment") or "")
    if gate_assessment == "FAIL":
        return False, "promotion blocked by review_control_signal gate_assessment=FAIL"
    if gate_assessment == "CONDITIONAL":
        return False, "promotion blocked by review_control_signal gate_assessment=CONDITIONAL"
    if str(payload.get("scale_recommendation") or "") == "NO":
        return False, "promotion blocked by review_control_signal scale_recommendation=NO"
    return True, None

def evaluate_sequence_transition(manifest: dict[str, Any], target_state: str) -> SequenceTransitionDecision:
    current_state = manifest.get("current_state")
    if not isinstance(current_state, str) or current_state not in SEQUENCE_STATES:
        return SequenceTransitionDecision(False, "unknown current sequence state")
    if target_state not in SEQUENCE_STATES:
        return SequenceTransitionDecision(False, "unknown target sequence state")
    if target_state not in _ALLOWED[current_state]:
        return SequenceTransitionDecision(False, f"illegal transition: {current_state} -> {target_state}")

    if current_state != target_state and not _has_traceability(manifest):
        return SequenceTransitionDecision(False, "missing required sequence traceability")

    if target_state == "executing_slice_1":
        if not _path_exists(manifest.get("roadmap_artifact_path")):
            return SequenceTransitionDecision(False, "missing required artifact: roadmap_artifact_path")
    elif target_state == "executing_slice_2":
        if _reports_count(manifest) < 1:
            return SequenceTransitionDecision(False, "slice_2 requires slice_1 execution evidence")
    elif target_state == "executing_slice_3":
        if _reports_count(manifest) < 2:
            return SequenceTransitionDecision(False, "slice_3 requires slice_1 and slice_2 execution evidence")
    elif target_state == "review_pending":
        if _reports_count(manifest) < 3:
            return SequenceTransitionDecision(False, "review_pending requires 3 completed slice execution artifacts")
    elif target_state == "remediation_pending":
        reviews = manifest.get("implementation_review_paths")
        if not isinstance(reviews, list) or not reviews:
            return SequenceTransitionDecision(False, "remediation_pending requires review artifacts")
    elif target_state == "certification_pending":
        review_paths = manifest.get("implementation_review_paths")
        if not isinstance(review_paths, list) or not review_paths:
            return SequenceTransitionDecision(False, "certification_pending requires review artifacts")
    elif target_state == "promoted":
        required_judgments = manifest.get("required_judgments")
        if isinstance(required_judgments, list) and "artifact_release_readiness" in required_judgments:
            required_paths = {
                "judgment_record_path": manifest.get("judgment_record_path"),
                "judgment_application_record_path": manifest.get("judgment_application_record_path"),
                "judgment_eval_result_path": manifest.get("judgment_eval_result_path"),
            }
            for field, path in required_paths.items():
                if not _path_exists(path):
                    return SequenceTransitionDecision(False, f"promotion requires {field} when artifact_release_readiness judgment is required")
        if manifest.get("certification_status") != "passed":
            return SequenceTransitionDecision(False, "promotion requires certification_status=passed")
        if not _path_exists(manifest.get("certification_record_path")):
            return SequenceTransitionDecision(False, "promotion requires certification_record_path")
        gate_passed, gate_error = _gate_proof_passes(manifest)
        if not gate_passed:
            return SequenceTransitionDecision(False, gate_error)
        falsification_passed, falsification_error = _hard_gate_falsification_passes(manifest)
        if not falsification_passed:
            return SequenceTransitionDecision(False, falsification_error)
        authority_passed, authority_error = _promotion_authority_gate(manifest)
        if not authority_passed:
            return SequenceTransitionDecision(False, authority_error)
        review_signal_passed, review_signal_error = _review_signal_gate(manifest)
        if not review_signal_passed:
            return SequenceTransitionDecision(False, review_signal_error)
        obedience_passed, obedience_error = _obedience_gate(manifest)
        if not obedience_passed:
            return SequenceTransitionDecision(False, obedience_error)
        cohesion_passed, cohesion_error = _cohesion_gate(manifest)
        if not cohesion_passed:
            return SequenceTransitionDecision(False, cohesion_error)
        if manifest.get("decision_blocked") is True:
            return SequenceTransitionDecision(False, "promotion blocked by decision_blocked=true")
        if manifest.get("control_allow_promotion") is not True:
            return SequenceTransitionDecision(False, "promotion requires explicit control_allow_promotion=true")

    contract_gate_passed, contract_gate_error = _stage_contract_gate(manifest, target_state)
    if not contract_gate_passed:
        return SequenceTransitionDecision(False, contract_gate_error)

    if target_state in {"blocked", "frozen"}:
        issues = manifest.get("blocking_issues")
        if not isinstance(issues, list) or not issues:
            return SequenceTransitionDecision(False, f"{target_state} transition requires non-empty blocking_issues")

    return SequenceTransitionDecision(True)
