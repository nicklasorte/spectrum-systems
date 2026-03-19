"""Deterministic failure enforcement and control decisions for BB+1."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple
import hashlib


DEFAULT_CONTROL_CONFIG: Dict[str, Any] = {
    "high_confidence_error_threshold": 0.05,
    "structural_failure_threshold": 0.10,
    "failure_mode_dominance_threshold": 0.60,
    "weak_component_repeat_threshold": 2,
    "component_suppression_health_threshold": 0.45,
}


_RESPONSE_PRIORITY = {
    "allow": 0,
    "suppress_component": 1,
    "require_human_review": 2,
    "hold": 3,
    "reject": 4,
    "incident_flag": 5,
}


def _merge_config(config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    merged = dict(DEFAULT_CONTROL_CONFIG)
    merged.update(config or {})
    return merged


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision_id(source_report_ref: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{source_report_ref}:{created_at}".encode("utf-8")).hexdigest()[:16]
    return f"fed_{digest}"


def _max_response(current: str, candidate: str) -> str:
    if _RESPONSE_PRIORITY.get(candidate, -1) > _RESPONSE_PRIORITY.get(current, -1):
        return candidate
    return current


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_failure_mode_distribution(metrics: Dict[str, Any]) -> Tuple[str | None, float]:
    concentration = metrics.get("repeated_failure_concentration") or []
    total_cases = max(int(metrics.get("total_cases") or 0), 0)
    if not concentration or total_cases <= 0:
        return None, 0.0

    dominant = concentration[0]
    dominant_name = str(dominant.get("pattern") or "unknown")
    dominant_count = int(dominant.get("count") or 0)
    return dominant_name, dominant_count / total_cases


def _extract_component_exposures(records: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    exposures: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for rec in records:
        failure_flags = rec.get("failure_flags") or {}
        high_conf = bool(rec.get("high_confidence_error"))
        dangerous = bool(rec.get("dangerous_promote"))
        structural_failure = bool(failure_flags.get("structural_failure") or rec.get("structural_failure"))
        repeated_failure = any(bool(v) for v in failure_flags.values())

        for pass_result in rec.get("pass_results", []):
            component = str(pass_result.get("pass_type") or "unknown")
            bucket = exposures[component]
            bucket["observations"] += 1
            if dangerous:
                bucket["dangerous_promotes"] += 1
            if high_conf:
                bucket["high_confidence_errors"] += 1
            if structural_failure:
                bucket["structural_failures"] += 1
            if repeated_failure:
                bucket["repeated_failures"] += 1

    return exposures


def _build_component_risks(metrics: Dict[str, Any], records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = metrics.get("pass_failure_concentration") or {}
    rank_counts = Counter({str(k): int(v) for k, v in ranked.items()})

    top_components = []
    for row in metrics.get("passes_components_most_at_risk", []) or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("pass_type") or "unknown")
        top_components.append(name)
        rank_counts[name] += int(row.get("failure_count") or 0)

    exposure = _extract_component_exposures(records)
    risks: List[Dict[str, Any]] = []
    for component in sorted(set(rank_counts) | set(exposure)):
        stats = exposure.get(component, {})
        observations = max(int(stats.get("observations", 0)), 1)
        weighted_risk = (
            stats.get("dangerous_promotes", 0) * 0.50
            + stats.get("high_confidence_errors", 0) * 0.25
            + stats.get("structural_failures", 0) * 0.20
            + stats.get("repeated_failures", 0) * 0.15
            + rank_counts.get(component, 0) * 0.10
        )
        normalized_risk = min(weighted_risk / observations, 1.0)
        health = round(max(0.0, 1.0 - normalized_risk), 3)

        risks.append(
            {
                "component": component,
                "repeat_weak_count": int(rank_counts.get(component, 0)),
                "observations": int(stats.get("observations", 0)),
                "dangerous_promotes": int(stats.get("dangerous_promotes", 0)),
                "high_confidence_errors": int(stats.get("high_confidence_errors", 0)),
                "structural_failures": int(stats.get("structural_failures", 0)),
                "repeated_failures": int(stats.get("repeated_failures", 0)),
                "component_health_score": health,
            }
        )
    return risks


def enforce_component_controls(component_risks: List[Dict[str, Any]], config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Suppress repeatedly weak / low-health components from final outputs."""
    cfg = _merge_config(config)
    repeat_threshold = int(cfg["weak_component_repeat_threshold"])
    health_threshold = _as_float(cfg["component_suppression_health_threshold"])

    suppressed: List[str] = []
    summaries: List[Dict[str, Any]] = []
    for risk in component_risks:
        component = str(risk.get("component") or "unknown")
        repeat_weak_count = int(risk.get("repeat_weak_count") or 0)
        health = _as_float(risk.get("component_health_score"), default=1.0)
        should_suppress = repeat_weak_count >= repeat_threshold or health <= health_threshold

        summaries.append(
            {
                **risk,
                "suppressed_for_final_outputs": should_suppress,
            }
        )
        if should_suppress:
            suppressed.append(component)

    return {
        "suppressed_components": sorted(set(suppressed)),
        "component_summaries": summaries,
    }


def derive_system_response(control_state: Dict[str, Any]) -> str:
    """Choose a deterministic single response from accumulated control conditions."""
    response = "allow"
    for candidate in control_state.get("candidate_responses", []):
        response = _max_response(response, str(candidate))
    return response


def classify_incident_severity(metrics: Dict[str, Any], control_state: Dict[str, Any], config: Dict[str, Any] | None = None) -> str:
    """Classify incident severity from deterministic threshold rules."""
    cfg = _merge_config(config)
    triggers = control_state.get("triggering_conditions", [])
    if not triggers:
        return "none"

    dangerous_count = int(metrics.get("dangerous_promote_count") or 0)
    pre_intervention_promotion_possible = bool(control_state.get("pre_intervention_promotion_possible"))
    high_conf_rate = _as_float(metrics.get("high_confidence_error_rate"))
    structural_rate = _as_float(metrics.get("structural_failure_rate"))
    _, failure_mode_dominance = _extract_failure_mode_distribution(metrics)

    if dangerous_count > 0 and pre_intervention_promotion_possible:
        return "critical"
    if high_conf_rate > _as_float(cfg["high_confidence_error_threshold"]) and structural_rate > _as_float(cfg["structural_failure_threshold"]):
        return "high"
    if failure_mode_dominance > _as_float(cfg["failure_mode_dominance_threshold"]):
        return "medium"
    return "low"


def evaluate_failure_controls(
    metrics: Dict[str, Any],
    records: List[Dict[str, Any]],
    *,
    source_report_ref: str = "unknown_report",
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Evaluate BB+1 enforcement controls and return a governed decision artifact."""
    cfg = _merge_config(config)
    triggering_conditions: List[str] = []
    required_actions: List[str] = []
    candidate_responses: List[str] = []

    dangerous_count = int(metrics.get("dangerous_promote_count") or 0)
    high_conf_rate = _as_float(metrics.get("high_confidence_error_rate"))
    structural_rate = _as_float(metrics.get("structural_failure_rate"))
    dominant_failure_mode, dominant_failure_rate = _extract_failure_mode_distribution(metrics)

    pre_intervention_promotion_possible = dangerous_count > 0 and _as_float(metrics.get("promote_rate")) > 0.0
    promotion_allowed = True

    if dangerous_count > 0:
        promotion_allowed = False
        triggering_conditions.append(f"dangerous_promote_count={dangerous_count}")
        required_actions.append("block_promotion_and_open_incident")
        candidate_responses.append("incident_flag")

    if high_conf_rate > _as_float(cfg["high_confidence_error_threshold"]):
        triggering_conditions.append(
            f"high_confidence_error_rate={high_conf_rate:.3f}>threshold={_as_float(cfg['high_confidence_error_threshold']):.3f}"
        )
        required_actions.append("require_human_review_before_promotion")
        candidate_responses.append("require_human_review")

    if structural_rate > _as_float(cfg["structural_failure_threshold"]):
        promotion_allowed = False
        triggering_conditions.append(
            f"structural_failure_rate={structural_rate:.3f}>threshold={_as_float(cfg['structural_failure_threshold']):.3f}"
        )
        required_actions.append("route_outputs_to_hold_or_reject")
        if structural_rate >= (_as_float(cfg["structural_failure_threshold"]) * 2):
            candidate_responses.append("reject")
        else:
            candidate_responses.append("hold")

    if dominant_failure_mode and dominant_failure_rate > _as_float(cfg["failure_mode_dominance_threshold"]):
        triggering_conditions.append(
            f"failure_mode_dominance={dominant_failure_mode}:{dominant_failure_rate:.3f}"
        )
        required_actions.append("priority_remediation_required")

    component_risks = _build_component_risks(metrics, records)
    component_controls = enforce_component_controls(component_risks, cfg)
    suppressed_components = component_controls["suppressed_components"]
    if suppressed_components:
        triggering_conditions.append(f"suppressed_components={','.join(suppressed_components)}")
        required_actions.append("suppress_low_trust_components_from_final_outputs")
        candidate_responses.append("suppress_component")

    control_state = {
        "candidate_responses": candidate_responses,
        "triggering_conditions": triggering_conditions,
        "pre_intervention_promotion_possible": pre_intervention_promotion_possible,
    }
    system_response = derive_system_response(control_state)
    incident_severity = classify_incident_severity(metrics, control_state, cfg)

    created_at = _now_iso()
    return {
        "decision_id": _decision_id(source_report_ref, created_at),
        "created_at": created_at,
        "source_report_ref": source_report_ref,
        "promotion_allowed": promotion_allowed,
        "system_response": system_response,
        "incident_severity": incident_severity,
        "triggering_conditions": triggering_conditions,
        "suppressed_components": suppressed_components,
        "required_actions": sorted(set(required_actions)),
        "notes": "Deterministic BB+1 enforcement decision.",
        "component_health": component_controls["component_summaries"],
    }
