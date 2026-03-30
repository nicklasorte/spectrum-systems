"""Deterministic fail-closed control-layer next-step decision engine."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

_POLICY_PATH = Path(__file__).resolve().parents[2] / "data" / "policy" / "next_step_decision_policy.json"
_REQUIRED_POLICY_ID = "NEXT_STEP_DECISION_POLICY"


class NextStepDecisionError(ValueError):
    """Raised when next-step decision inputs are not valid objects."""


def _load_json(path: str | Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise NextStepDecisionError(f"expected object artifact: {path}")
    return payload


def _canonical_json_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_policy_compatibility(policy: Dict[str, Any]) -> None:
    if policy.get("policy_id") != _REQUIRED_POLICY_ID:
        raise NextStepDecisionError("next-step decision policy_id is incompatible")

    states = policy.get("allowed_states")
    if not isinstance(states, list) or not states:
        raise NextStepDecisionError("next-step decision policy missing allowed_states")

    mapping = policy.get("decision_mapping_rules")
    if not isinstance(mapping, dict):
        raise NextStepDecisionError("next-step decision policy missing decision_mapping_rules")

    state_set = set(states)
    mapping_set = set(mapping.keys())
    if state_set != mapping_set:
        raise NextStepDecisionError("next-step decision policy state mapping mismatch")

    required_evidence = policy.get("required_evidence_by_state")
    if not isinstance(required_evidence, dict):
        raise NextStepDecisionError("next-step decision policy missing required_evidence_by_state")
    if not set(required_evidence.keys()).issubset(state_set):
        raise NextStepDecisionError("next-step decision policy evidence state mismatch")


def _load_next_step_policy() -> tuple[Dict[str, Any], str]:
    if not _POLICY_PATH.is_file():
        raise NextStepDecisionError(f"next-step decision policy missing: {_POLICY_PATH}")
    try:
        policy = _load_json(_POLICY_PATH)
    except json.JSONDecodeError as exc:
        raise NextStepDecisionError("next-step decision policy is not valid JSON") from exc

    schema = load_schema("next_step_decision_policy")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(policy), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise NextStepDecisionError(f"next-step decision policy failed schema validation: {details}")

    _validate_policy_compatibility(policy)
    return policy, _canonical_json_hash(policy)


def _path_exists(path_value: Any) -> bool:
    return isinstance(path_value, str) and path_value != "" and Path(path_value).is_file()


def _all_paths_exist(paths: Any) -> bool:
    return isinstance(paths, list) and all(_path_exists(path) for path in paths)


def _validate_governance_authority(manifest: Dict[str, Any], policy: Dict[str, Any]) -> tuple[list[str], bool, bool]:
    missing: list[str] = []
    governance = policy["governance_requirements"]
    canonical_paths = governance["canonical_paths"]
    strategy_path_expected = canonical_paths["strategy_authority.path"]

    strategy = manifest.get("strategy_authority")
    strategy_ok = True
    if not isinstance(strategy, dict):
        missing.append("strategy_authority")
        strategy_ok = False
    else:
        if strategy.get("path") != strategy_path_expected:
            missing.append("strategy_authority.path")
            strategy_ok = False
        elif not _path_exists(strategy.get("path")):
            missing.append("strategy_authority.path")
            strategy_ok = False

    source_authorities = manifest.get("source_authorities")
    source_ok = True
    if not isinstance(source_authorities, list) or not source_authorities:
        missing.append("source_authorities")
        source_ok = False
    else:
        source_index_path = Path(canonical_paths["source_index_path"])
        source_index_text = source_index_path.read_text(encoding="utf-8") if source_index_path.is_file() else ""
        if not source_index_path.is_file():
            missing.append(canonical_paths["source_index_path"])
            source_ok = False

        required_keys = governance["source_authority_required_keys"]
        require_declared = governance["source_authorities_must_be_declared_in_index"]

        seen: set[tuple[str, str]] = set()
        for idx, item in enumerate(source_authorities):
            if not isinstance(item, dict):
                missing.append(f"source_authorities[{idx}]")
                source_ok = False
                continue
            source_id = item.get("source_id")
            source_path = item.get("path")
            for key in required_keys:
                if not isinstance(item.get(key), str) or not item.get(key):
                    missing.append(f"source_authorities[{idx}].{key}")
                    source_ok = False
            if not isinstance(source_path, str) or not source_path:
                continue
            if not _path_exists(source_path):
                missing.append(f"source_authorities[{idx}].path")
                source_ok = False
            elif require_declared and source_index_text and (
                source_id not in source_index_text or source_path not in source_index_text
            ):
                missing.append(f"source_authorities[{idx}].declared_in_source_index")
                source_ok = False
            key = (str(source_id), source_path)
            if key in seen:
                missing.append(f"source_authorities[{idx}].duplicate")
                source_ok = False
            seen.add(key)

    return sorted(set(missing)), strategy_ok, source_ok


def _drift_triggered(status: str | None, block_on: set[str]) -> bool:
    if status is None:
        return False
    return status in block_on


def _detect_drift(manifest: Dict[str, Any], policy: Dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    block_on = set(policy["drift_blocking_rules"]["block_on"])

    for key in ("drift_detection_result_path", "drift_result_path"):
        path = manifest.get(key)
        if _path_exists(path):
            payload = _load_json(path)
            status = payload.get("drift_status")
            detected = payload.get("drift_detected")
            if detected is True and "drift_detected" in block_on:
                reasons.append(f"{key}:drift_detected")
            if isinstance(status, str) and _drift_triggered(status, block_on):
                reasons.append(f"{key}:{status}")

    list_key = manifest.get("drift_detection_artifact_paths")
    if isinstance(list_key, list):
        for path in list_key:
            if not _path_exists(path):
                continue
            payload = _load_json(path)
            status = payload.get("drift_status")
            if payload.get("drift_detected") is True and "drift_detected" in block_on:
                reasons.append("drift_detection_artifact_paths:drift_detected")
            if isinstance(status, str) and _drift_triggered(status, block_on):
                reasons.append(f"drift_detection_artifact_paths:{status}")

    return bool(reasons), sorted(set(reasons))


def _required_input_missing_for_state(manifest: Dict[str, Any], state: str, policy: Dict[str, Any]) -> list[str]:
    missing: list[str] = []
    requirements = policy["required_evidence_by_state"].get(state, {})
    required_fields = requirements.get("required_fields", []) if isinstance(requirements, dict) else []

    for key in required_fields:
        value = manifest.get(key)
        if key.endswith("_paths"):
            if not _all_paths_exist(value):
                missing.append(key)
        elif key.endswith("_path"):
            if not _path_exists(value):
                missing.append(key)
        elif key == "done_certification_input_refs":
            if not isinstance(value, dict) or not value:
                missing.append(key)
            else:
                required_refs = {
                    "replay_result_ref",
                    "regression_result_ref",
                    "certification_pack_ref",
                    "error_budget_ref",
                    "policy_ref",
                }
                for ref in sorted(required_refs):
                    if not isinstance(value.get(ref), str) or not value.get(ref):
                        missing.append(f"done_certification_input_refs.{ref}")
        else:
            if value in (None, "", []):
                missing.append(key)
    return missing


def _decision_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_next_step_decision(cycle_manifest_path: str) -> Dict[str, Any]:
    policy, policy_hash = _load_next_step_policy()
    manifest = _load_json(cycle_manifest_path)

    cycle_id = str(manifest.get("cycle_id", "cycle-invalid"))
    state = str(manifest.get("current_state", "invalid"))
    decided_at = manifest.get("updated_at") if isinstance(manifest.get("updated_at"), str) else "1970-01-01T00:00:00Z"

    states = set(policy["allowed_states"])
    governance = policy["governance_requirements"]
    mapping = policy["decision_mapping_rules"]

    missing_inputs, strategy_ok, source_ok = _validate_governance_authority(manifest, policy)
    blocking_reasons: list[str] = []
    drift_detected, drift_reasons = _detect_drift(manifest, policy)

    if state not in states:
        missing_inputs.append("current_state")
        next_action = governance["invalid_state_action"]
        allowed_actions = [governance["invalid_state_action"]]
        blocking_reasons.append("invalid lifecycle state")
    else:
        next_action = mapping[state]["next_action"]
        allowed_actions = mapping[state]["allowed_actions"]
        missing_inputs.extend(_required_input_missing_for_state(manifest, state, policy))

    if missing_inputs:
        next_action = governance["missing_input_action"]
        blocking_reasons.append("missing required governance signals")

    if drift_detected:
        next_action = policy["drift_blocking_rules"]["remediation_action"]
        blocking_reasons.append(policy["drift_blocking_rules"]["blocking_reason"])

    blocking = bool(missing_inputs or blocking_reasons or state == "blocked")
    if state == "certified_done" and not (missing_inputs or drift_detected):
        blocking = False

    trust_score = 100
    trust_score -= min(len(set(missing_inputs)) * 20, 80)
    if not strategy_ok:
        trust_score -= 20
    if not source_ok:
        trust_score -= 20
    if drift_detected:
        trust_score -= 25
    trust_score = max(0, min(100, trust_score))

    strategy_compliant = strategy_ok and state in states and not drift_detected
    source_grounded = source_ok

    core_id_fields = {
        "cycle_id": cycle_id,
        "current_state": state,
        "next_action": next_action,
        "allowed_actions": allowed_actions,
        "blocking": blocking,
        "required_inputs_missing": sorted(set(missing_inputs)),
        "drift_detected": drift_detected,
        "drift_reasons": drift_reasons,
        "strategy_compliant": strategy_compliant,
        "source_grounded": source_grounded,
        "trust_score": trust_score,
        "policy_id": policy["policy_id"],
        "policy_version": policy["version"],
        "policy_hash": policy_hash,
        "decided_at": decided_at,
    }

    decision = {
        "decision_id": _decision_id(core_id_fields),
        "cycle_id": cycle_id,
        "current_state": state,
        "next_action": next_action,
        "allowed_actions": allowed_actions,
        "blocking": blocking,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "required_inputs_missing": sorted(set(missing_inputs)),
        "drift_detected": drift_detected,
        "drift_reasons": drift_reasons,
        "strategy_compliant": strategy_compliant,
        "source_grounded": source_grounded,
        "trust_score": trust_score,
        "policy_id": policy["policy_id"],
        "policy_version": policy["version"],
        "policy_hash": policy_hash,
        "decision_rationale": (
            f"state={state};action={next_action};blocking={'true' if blocking else 'false'};"
            f"reasons={len(set(blocking_reasons))};drift={'true' if drift_detected else 'false'};trust={trust_score}"
        ),
        "decided_at": decided_at,
    }

    schema = load_schema("next_step_decision_artifact")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(decision)
    return decision
