"""Deterministic fail-closed roadmap eligibility evaluator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class RoadmapEligibilityError(ValueError):
    """Raised when governed roadmap metadata is invalid or cannot be evaluated."""


def _load_json(path: str | Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RoadmapEligibilityError(f"expected object artifact: {path}")
    return payload


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _canonical_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _validate_schema(payload: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RoadmapEligibilityError(f"{schema_name} failed schema validation: {details}")


def _step_map(steps: list[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    step_ids = [str(step["step_id"]) for step in steps]
    if len(step_ids) != len(set(step_ids)):
        raise RoadmapEligibilityError("duplicate step_id values in governed roadmap")
    order_indexes = [int(step["order_index"]) for step in steps]
    if len(order_indexes) != len(set(order_indexes)):
        raise RoadmapEligibilityError("duplicate order_index values in governed roadmap")
    return {str(step["step_id"]): step for step in steps}


def _load_review_control_signals(available_artifacts: set[str]) -> list[Dict[str, Any]]:
    signals: list[Dict[str, Any]] = []
    validator = Draft202012Validator(load_schema("review_control_signal"), format_checker=FormatChecker())
    for ref in sorted(available_artifacts):
        path = Path(ref)
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("artifact_type") != "review_control_signal":
            continue
        errors = sorted(validator.iter_errors(payload), key=lambda err: str(list(err.absolute_path)))
        if errors:
            raise RoadmapEligibilityError("review_control_signal failed schema validation in available_artifact_refs")
        signals.append(payload)
    return signals


def _evaluate_step(
    step: Dict[str, Any],
    *,
    step_by_id: Dict[str, Dict[str, Any]],
    available_artifacts: set[str],
    satisfied_trust: set[str],
    satisfied_review: set[str],
    satisfied_eval: set[str],
    review_signals: list[Dict[str, Any]],
) -> Dict[str, Any]:
    dependency_steps = [str(item) for item in step["dependency_step_ids"]]
    ambiguous_dependency_steps = sorted(dep for dep in dependency_steps if dep not in step_by_id)
    missing_dependency_steps = sorted(
        dep
        for dep in dependency_steps
        if dep in step_by_id and str(step_by_id[dep]["status"]) != "completed"
    )

    dependency_artifacts = [str(item) for item in step["dependency_artifact_refs"]]
    missing_artifacts = sorted(ref for ref in dependency_artifacts if ref not in available_artifacts)

    trust_requirements = [str(item) for item in step["trust_requirements"]]
    missing_trust = sorted(req for req in trust_requirements if req not in satisfied_trust)

    review_requirements = [str(item) for item in step["review_requirements"]]
    missing_review = sorted(req for req in review_requirements if req not in satisfied_review)
    if review_signals:
        failed_reviews = sorted(
            str(item["review_id"]) for item in review_signals if str(item.get("gate_assessment") or "") == "FAIL"
        )
        if failed_reviews:
            missing_review.extend([f"review_gate_fail:{review_id}" for review_id in failed_reviews])
        mode = str(step.get("hardening_vs_expansion") or "").strip().lower()
        if mode == "expansion":
            no_scale_reviews = sorted(
                str(item["review_id"]) for item in review_signals if str(item.get("scale_recommendation") or "") == "NO"
            )
            if no_scale_reviews:
                missing_review.extend([f"review_scale_no:{review_id}" for review_id in no_scale_reviews])
    missing_review = sorted(set(missing_review))

    eval_requirements = [str(item) for item in step["eval_requirements"]]
    missing_eval = sorted(req for req in eval_requirements if req not in satisfied_eval)

    blocked_reasons: list[str] = []
    if ambiguous_dependency_steps:
        blocked_reasons.append("ambiguous_dependency_reference")
    if missing_dependency_steps or ambiguous_dependency_steps:
        blocked_reasons.append("unmet_dependency_steps")
    if missing_artifacts:
        blocked_reasons.append("unmet_dependency_artifacts")
    if missing_trust:
        blocked_reasons.append("unmet_trust_requirements")
    if missing_review:
        blocked_reasons.append("unmet_review_requirements")
    if missing_eval:
        blocked_reasons.append("unmet_eval_requirements")

    return {
        "step_id": str(step["step_id"]),
        "blocked_reasons": blocked_reasons,
        "missing_dependency_step_ids": sorted(set(missing_dependency_steps + ambiguous_dependency_steps)),
        "missing_dependency_artifact_refs": missing_artifacts,
        "missing_trust_requirements": missing_trust,
        "unmet_review_requirements": missing_review,
        "unmet_eval_requirements": missing_eval,
    }


def _strategy_status(step: Dict[str, Any], *, steps: list[Dict[str, Any]]) -> Dict[str, Any]:
    step_id = str(step["step_id"])
    order_index = int(step["order_index"])
    mode = str(step.get("hardening_vs_expansion") or "").strip().lower()
    behavior_affecting = bool(step.get("behavior_affecting"))
    replay_trace_implications = str(step.get("replay_trace_implications") or "").strip()
    eval_control_path = str(step.get("eval_control_path") or "").strip()
    strategy_alignment = str(step.get("strategy_alignment") or "").strip()
    primary_trust_gain = str(step.get("primary_trust_gain") or "").strip()
    bounded_strategy_risk = bool(step.get("bounded_strategy_risk"))

    violated_invariants: list[str] = []
    drift_signals: list[str] = []

    if not strategy_alignment:
        violated_invariants.append("missing_strategy_alignment")
    if not primary_trust_gain:
        violated_invariants.append("missing_primary_trust_gain")
    if behavior_affecting and not replay_trace_implications:
        violated_invariants.append("missing_replay_trace_implications")

    is_expansion = mode == "expansion"
    if is_expansion and not eval_control_path:
        violated_invariants.append("missing_eval_control_path")

    incomplete_hardening_dependencies = sorted(
        str(candidate["step_id"])
        for candidate in steps
        if int(candidate["order_index"]) < order_index
        and str(candidate.get("hardening_vs_expansion") or "").strip().lower() == "hardening"
        and str(candidate["status"]) != "completed"
    )
    if is_expansion and incomplete_hardening_dependencies:
        drift_signals.append("expansion_precedes_hardening_completion")

    if violated_invariants:
        decision = "block"
        rationale = "strategy gate blocked due to missing required strategy/trust/control declarations"
    elif drift_signals:
        decision = "freeze"
        rationale = "strategy gate froze expansion until earlier hardening slices are complete"
    elif bounded_strategy_risk:
        decision = "warn"
        rationale = "strategy gate warns due to bounded declared strategy risk"
    else:
        decision = "allow"
        rationale = "strategy gate allows execution; required strategy and trust declarations are complete"

    return {
        "artifact_type": "pqx_strategy_status_artifact",
        "schema_version": "1.0.0",
        "roadmap_row_id": step_id,
        "strategy_gate_decision": decision,
        "violated_invariants": violated_invariants,
        "drift_signals": drift_signals,
        "hardening_vs_expansion": mode,
        "replay_trace_declared": bool(replay_trace_implications),
        "eval_control_declared": bool(eval_control_path),
        "rationale": rationale,
    }


def build_roadmap_eligibility(governed_roadmap_path: str | Path) -> Dict[str, Any]:
    roadmap = _load_json(governed_roadmap_path)
    _validate_schema(roadmap, "governed_roadmap_artifact")

    steps_raw = roadmap["steps"]
    if not isinstance(steps_raw, list):
        raise RoadmapEligibilityError("governed roadmap steps must be a list")
    steps = sorted(steps_raw, key=lambda item: (int(item["order_index"]), str(item["step_id"])))
    step_by_id = _step_map(steps)

    available_artifacts = {str(item) for item in roadmap["available_artifact_refs"]}
    review_signals = _load_review_control_signals(available_artifacts)
    satisfied_trust = {str(item) for item in roadmap["satisfied_trust_requirements"]}
    satisfied_review = {str(item) for item in roadmap["satisfied_review_requirements"]}
    satisfied_eval = {str(item) for item in roadmap["satisfied_eval_requirements"]}

    completed_steps = [str(step["step_id"]) for step in steps if str(step["status"]) == "completed"]

    eligible_step_ids: list[str] = []
    blocked_steps: list[Dict[str, Any]] = []
    strategy_status_artifacts: list[Dict[str, Any]] = []

    for step in steps:
        step_id = str(step["step_id"])
        status = str(step["status"])

        if status == "completed":
            continue
        if status not in {"planned", "ready", "in_progress", "blocked"}:
            blocked_steps.append(
                {
                    "step_id": step_id,
                    "blocked_reasons": ["step_not_planned"],
                    "missing_dependency_step_ids": [],
                    "missing_dependency_artifact_refs": [],
                    "missing_trust_requirements": [],
                    "unmet_review_requirements": [],
                    "unmet_eval_requirements": [],
                }
            )
            continue

        result = _evaluate_step(
            step,
            step_by_id=step_by_id,
            available_artifacts=available_artifacts,
            satisfied_trust=satisfied_trust,
            satisfied_review=satisfied_review,
            satisfied_eval=satisfied_eval,
            review_signals=review_signals,
        )
        strategy_status = _strategy_status(step, steps=steps)
        strategy_status_artifacts.append(strategy_status)

        if strategy_status["strategy_gate_decision"] == "block":
            result["blocked_reasons"] = sorted(set(result["blocked_reasons"] + ["strategy_gate_block"]))
        elif strategy_status["strategy_gate_decision"] == "freeze":
            result["blocked_reasons"] = sorted(set(result["blocked_reasons"] + ["strategy_gate_freeze"]))

        if result["blocked_reasons"]:
            blocked_steps.append(result)
        else:
            eligible_step_ids.append(step_id)

    if eligible_step_ids:
        min_order = min(int(step_by_id[step_id]["order_index"]) for step_id in eligible_step_ids)
        recommended_next_step_ids = sorted(
            step_id for step_id in eligible_step_ids if int(step_by_id[step_id]["order_index"]) == min_order
        )
    else:
        recommended_next_step_ids = []

    roadmap_digest = _canonical_hash(roadmap)
    identity_basis = {
        "roadmap_artifact_id": str(roadmap["artifact_id"]),
        "roadmap_digest": roadmap_digest,
    }

    candidate = {
        "artifact_type": "roadmap_eligibility_artifact",
        "schema_version": "1.0.0",
        "artifact_version": "1.0.0",
        "roadmap_ref": str(roadmap["roadmap_ref"]),
        "evaluated_at": str(roadmap["generated_at"]),
        "identity_basis": identity_basis,
        "eligible_step_ids": sorted(eligible_step_ids),
        "recommended_next_step_ids": recommended_next_step_ids,
        "blocked_steps": sorted(blocked_steps, key=lambda item: item["step_id"]),
        "strategy_status_artifacts": sorted(strategy_status_artifacts, key=lambda item: item["roadmap_row_id"]),
        "summary": {
            "total_steps": len(steps),
            "completed_steps": len(completed_steps),
            "eligible_steps": len(eligible_step_ids),
            "blocked_steps": len(blocked_steps),
            "strategy_gate": {
                "allow": sum(1 for item in strategy_status_artifacts if item["strategy_gate_decision"] == "allow"),
                "warn": sum(1 for item in strategy_status_artifacts if item["strategy_gate_decision"] == "warn"),
                "freeze": sum(1 for item in strategy_status_artifacts if item["strategy_gate_decision"] == "freeze"),
                "block": sum(1 for item in strategy_status_artifacts if item["strategy_gate_decision"] == "block"),
            },
        },
    }
    candidate["artifact_id"] = _canonical_hash(candidate)

    _validate_schema(candidate, "roadmap_eligibility_artifact")
    return candidate


def evaluate_roadmap_eligibility_to_path(
    governed_roadmap_path: str | Path,
    output_path: str | Path,
) -> Dict[str, Any]:
    artifact = build_roadmap_eligibility(governed_roadmap_path)
    Path(output_path).write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact
