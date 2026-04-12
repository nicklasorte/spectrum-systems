"""Deterministic governed eval runner for RAX semantic and control integrity."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import load_example, validate_artifact

RUNNER_NAME = "rax_eval_runner"
RUNNER_VERSION = "1.2.0"

_FAILURE_TO_EVAL_TYPE = {
    "semantic_contradiction": "rax_output_semantic_alignment",
    "weak_acceptance_check": "rax_acceptance_check_strength",
    "missing_trace": "rax_trace_integrity",
    "lineage_invalid": "rax_trace_integrity",
    "dependency_corruption": "rax_control_readiness",
    "over_expansion": "rax_output_semantic_alignment",
    "replay_inconsistency": "rax_control_readiness",
    "readiness_contradiction": "rax_control_readiness",
}

_REASON_TO_SEMANTIC_CATEGORY = {
    "semantic_intent_insufficient": "semantic_contradiction",
    "owner_intent_contradiction": "semantic_contradiction",
    "normalization_ambiguity": "semantic_contradiction",
    "semantic_target_mismatch": "semantic_contradiction",
    "weak_acceptance_check": "weak_acceptance_check",
    "missing_required_expansion_trace": "missing_trace",
    "artifact_not_trace_linked": "missing_trace",
    "trace_incomplete": "missing_trace",
    "artifact_lineage_invalid": "lineage_invalid",
    "dependency_graph_corrupt": "dependency_corruption",
    "dependency_graph_unresolved": "dependency_corruption",
    "output_over_expanded": "over_expansion",
    "cross_run_eval_signal_inconsistency": "replay_inconsistency",
    "tests_pass_eval_fail": "readiness_contradiction",
    "contradictory_eval_signals": "readiness_contradiction",
    "priority_inversion_detected": "semantic_contradiction",
    "dependency_omission_detected": "dependency_corruption",
    "owner_intent_mismatch_detected": "semantic_contradiction",
    "weak_counter_evidence_detected": "readiness_contradiction",
    "contradiction_unresolved": "readiness_contradiction",
    "semantic_expansion_mismatch": "over_expansion",
    "policy_meaning_drift_detected": "semantic_contradiction",
    "ambiguous_source_intent_detected": "semantic_contradiction",
    "hidden_scope_expansion_detected": "over_expansion",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_rax_eval_registry() -> dict[str, Any]:
    registry = load_example("rax_eval_registry")
    validate_artifact(registry, "rax_eval_registry")
    return registry


def load_rax_eval_case_set() -> dict[str, Any]:
    case_set = load_example("rax_eval_case_set")
    validate_artifact(case_set, "rax_eval_case_set")
    return case_set


def _load_policy(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    policy_path = root / "config" / "policy" / "rax_eval_policy.json"
    return json.loads(policy_path.read_text(encoding="utf-8"))


def _status_from_reason_codes(reason_codes: list[str], *, blocking_codes: set[str]) -> str:
    if any(code in blocking_codes for code in reason_codes):
        return "fail"
    return "pass"


def _score_from_status(status: str) -> float:
    return 1.0 if status == "pass" else 0.0


def _eval_type_from_result(item: dict[str, Any]) -> str | None:
    for mode in item.get("failure_modes", []):
        if isinstance(mode, str) and mode.startswith("eval_type:"):
            return mode.split(":", 1)[1]
    return None


def _reason_codes_from_results(eval_results: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            mode
            for item in eval_results
            for mode in item.get("failure_modes", [])
            if isinstance(mode, str) and mode and ":" not in mode
        }
    )


def _canonical_eval_signal(eval_results: list[dict[str, Any]]) -> tuple[str, ...]:
    rows: list[str] = []
    for item in eval_results:
        eval_type = _eval_type_from_result(item) or "unknown"
        status = str(item.get("result_status", "unknown"))
        reasons = sorted(
            mode
            for mode in item.get("failure_modes", [])
            if isinstance(mode, str) and mode and ":" not in mode
        )
        rows.append(f"{eval_type}|{status}|{','.join(reasons)}")
    return tuple(sorted(rows))


def _trace_lineage_from_eval_results(*, eval_results: list[dict[str, Any]], target_ref: str, expected_trace_id: str | None) -> dict[str, bool]:
    trace_linked = True
    trace_complete = True
    for item in eval_results:
        refs = [ref for ref in item.get("provenance_refs", []) if isinstance(ref, str)]
        if target_ref not in refs:
            trace_linked = False
        if not any(ref.startswith("trace://") for ref in refs):
            trace_complete = False
        if expected_trace_id and f"trace://{expected_trace_id}" not in refs:
            trace_complete = False
    return {"trace_linked": trace_linked, "trace_complete": trace_complete}


def _critical_failure_classification(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return bool(normalized and normalized not in {"none", "pass", "ok"})


def _counter_evidence_is_material(counter_evidence: Any) -> bool:
    if not isinstance(counter_evidence, list) or not counter_evidence:
        return False
    weak_markers = {
        "irrelevant",
        "non-material",
        "non material",
        "weak",
        "placeholder",
        "todo",
        "tbd",
    }
    for item in counter_evidence:
        text = str(item).strip().lower()
        if not text:
            continue
        if any(marker in text for marker in weak_markers):
            continue
        return True
    return False


def _make_failure_id(*, run_id: str, semantic_category: str, reason_codes: list[str], target_ref: str) -> str:
    digest = hashlib.sha256(f"{run_id}|{semantic_category}|{target_ref}|{','.join(sorted(reason_codes))}".encode("utf-8")).hexdigest()[:16]
    return f"rax-failure-{digest}"


def _classify_failure(*, reason_codes: list[str], failure_classification: str | None) -> tuple[str, str]:
    for code in reason_codes:
        semantic = _REASON_TO_SEMANTIC_CATEGORY.get(code)
        if semantic:
            return failure_classification or "runtime_failure", semantic
    normalized = (failure_classification or "runtime_failure").strip().lower()
    return normalized, "semantic_contradiction"


def _dedupe_eval_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uniq: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        uniq[candidate["candidate_id"]] = candidate
    return [uniq[key] for key in sorted(uniq)]


def generate_failure_eval_artifacts(
    *,
    run_id: str,
    target_ref: str,
    trace_id: str,
    source_artifact_refs: list[str],
    reason_codes: list[str],
    failure_classification: str | None,
    reproducibility_inputs: dict[str, Any],
    existing_candidate_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Generate failure pattern and deterministic eval candidate artifacts from failures."""
    if not reason_codes and not _critical_failure_classification(failure_classification):
        return {"failure_pattern_records": [], "eval_case_candidates": []}

    failure_class, semantic_category = _classify_failure(reason_codes=reason_codes, failure_classification=failure_classification)
    failure_id = _make_failure_id(run_id=run_id, semantic_category=semantic_category, reason_codes=reason_codes, target_ref=target_ref)
    candidate_eval_type = _FAILURE_TO_EVAL_TYPE.get(semantic_category, "rax_control_readiness")
    candidate_id = f"{failure_id}:eval-candidate"
    deduped = existing_candidate_ids is not None and candidate_id in existing_candidate_ids

    pattern_record = {
        "artifact_type": "rax_failure_pattern_record",
        "schema_version": "1.0.0",
        "failure_id": failure_id,
        "source_artifact_refs": sorted(set(source_artifact_refs + [target_ref, f"trace://{trace_id}"])),
        "failure_classification": failure_class,
        "failure_details": sorted(set(reason_codes)) or ["unclassified_failure"],
        "semantic_category": semantic_category,
        "trace_linkage": {
            "target_ref": target_ref,
            "trace_id": trace_id,
            "linked_refs": sorted(set(source_artifact_refs + [target_ref, f"trace://{trace_id}"])),
        },
        "reproducibility_inputs": reproducibility_inputs,
        "candidate_eval_generation_status": "already_exists" if deduped else "generated",
    }
    validate_artifact(pattern_record, "rax_failure_pattern_record")

    eval_candidate = {
        "artifact_type": "rax_failure_eval_candidate",
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "source_failure_id": failure_id,
        "eval_case_id": f"{run_id}:{candidate_eval_type}:{failure_id}",
        "eval_type": candidate_eval_type,
        "target_ref": target_ref,
        "expected_status": "fail",
        "reason_codes": sorted(set(reason_codes)) or ["unclassified_failure"],
        "trace_id": trace_id,
        "version": "1.0.0",
        "dedupe_key": f"{semantic_category}|{target_ref}|{candidate_eval_type}",
        "generation_status": "duplicate" if deduped else "generated",
    }
    validate_artifact(eval_candidate, "rax_failure_eval_candidate")

    candidates = [] if deduped else [eval_candidate]
    return {"failure_pattern_records": [pattern_record], "eval_case_candidates": _dedupe_eval_candidates(candidates)}


def build_feedback_loop_record(
    *,
    record_id: str,
    originating_failure_pattern_ref: str,
    fix_artifact_refs: list[str],
    eval_artifact_refs_added: list[str],
    historical_failure_classes: list[str],
    current_failure_class: str,
    recurrence_window: str,
    readiness_delta: float,
    confidence_delta: float,
) -> dict[str, Any]:
    recurrence = current_failure_class in historical_failure_classes
    outcome_status = "recurrence_detected" if recurrence else "non_recurrence_recorded"
    record = {
        "artifact_type": "rax_feedback_loop_record",
        "schema_version": "1.0.0",
        "record_id": record_id,
        "originating_failure_pattern_ref": originating_failure_pattern_ref,
        "fix_artifact_refs": sorted(set(fix_artifact_refs)),
        "eval_artifact_refs_added": sorted(set(eval_artifact_refs_added)),
        "recurrence_detected": recurrence,
        "recurrence_window": recurrence_window,
        "readiness_delta": readiness_delta,
        "confidence_delta": confidence_delta,
        "outcome_status": outcome_status,
    }
    validate_artifact(record, "rax_feedback_loop_record")
    return record


def build_rax_health_snapshot(
    *,
    snapshot_id: str,
    window_ref: str,
    metrics: dict[str, float],
    thresholds: dict[str, dict[str, float]],
) -> dict[str, Any]:
    severity = "healthy"
    violations: list[str] = []
    for metric_name, value in metrics.items():
        bounds = thresholds.get(metric_name, {})
        if "warn_max" in bounds:
            warn_max = float(bounds.get("warn_max", 1.0))
            freeze_max = float(bounds.get("freeze_candidate_max", 1.0))
            block_max = float(bounds.get("block_candidate_max", 1.0))
            if value > block_max:
                severity = "block_candidate"
                violations.append(f"{metric_name}:block")
            elif value > freeze_max and severity != "block_candidate":
                severity = "freeze_candidate"
                violations.append(f"{metric_name}:freeze")
            elif value > warn_max and severity not in {"block_candidate", "freeze_candidate"}:
                severity = "warn"
                violations.append(f"{metric_name}:warn")
        else:
            warn_min = float(bounds.get("warn_min", 0.0))
            freeze_min = float(bounds.get("freeze_candidate_min", 0.0))
            block_min = float(bounds.get("block_candidate_min", 0.0))
            if value < block_min:
                severity = "block_candidate"
                violations.append(f"{metric_name}:block")
            elif value < freeze_min and severity != "block_candidate":
                severity = "freeze_candidate"
                violations.append(f"{metric_name}:freeze")
            elif value < warn_min and severity not in {"block_candidate", "freeze_candidate"}:
                severity = "warn"
                violations.append(f"{metric_name}:warn")

    snapshot = {
        "artifact_type": "rax_health_snapshot",
        "schema_version": "1.0.0",
        "snapshot_id": snapshot_id,
        "window_ref": window_ref,
        "readiness_pass_rate": metrics["readiness_pass_rate"],
        "eval_coverage_rate": metrics["eval_coverage_rate"],
        "semantic_failure_rate": metrics["semantic_failure_rate"],
        "readiness_bypass_attempt_rate": metrics["readiness_bypass_attempt_rate"],
        "replay_consistency_rate": metrics["replay_consistency_rate"],
        "trace_completeness_rate": metrics["trace_completeness_rate"],
        "lineage_validity_rate": metrics["lineage_validity_rate"],
        "contradiction_rate": metrics["contradiction_rate"],
        "candidate_posture": severity,
        "threshold_violations": sorted(violations),
    }
    validate_artifact(snapshot, "rax_health_snapshot")
    return snapshot


def build_rax_drift_signal_record(
    *,
    signal_id: str,
    baseline_window_ref: str,
    current_window_ref: str,
    baseline_metrics: dict[str, float],
    current_metrics: dict[str, float],
    drift_thresholds: dict[str, float],
) -> dict[str, Any]:
    surfaces = {
        "eval_signal_drift": abs(current_metrics["eval_coverage_rate"] - baseline_metrics["eval_coverage_rate"]),
        "readiness_outcome_drift": abs(current_metrics["readiness_pass_rate"] - baseline_metrics["readiness_pass_rate"]),
        "semantic_classification_drift": abs(current_metrics["semantic_failure_rate"] - baseline_metrics["semantic_failure_rate"]),
        "version_authority_drift": abs((1.0 - current_metrics["lineage_validity_rate"]) - (1.0 - baseline_metrics["lineage_validity_rate"])),
        "trace_lineage_completeness_drift": abs(current_metrics["trace_completeness_rate"] - baseline_metrics["trace_completeness_rate"]),
    }

    posture = "healthy"
    exceeded: list[str] = []
    for key, drift in surfaces.items():
        threshold = float(drift_thresholds.get(key, 1.0))
        if drift > threshold * 1.5:
            posture = "block_candidate"
            exceeded.append(f"{key}:block")
        elif drift > threshold and posture != "block_candidate":
            posture = "freeze_candidate"
            exceeded.append(f"{key}:freeze")

    record = {
        "artifact_type": "rax_drift_signal_record",
        "schema_version": "1.0.0",
        "signal_id": signal_id,
        "baseline_window_ref": baseline_window_ref,
        "current_window_ref": current_window_ref,
        "eval_signal_drift": surfaces["eval_signal_drift"],
        "readiness_outcome_drift": surfaces["readiness_outcome_drift"],
        "semantic_classification_drift": surfaces["semantic_classification_drift"],
        "version_authority_drift": surfaces["version_authority_drift"],
        "trace_lineage_completeness_drift": surfaces["trace_lineage_completeness_drift"],
        "candidate_posture": posture,
        "threshold_exceeded": sorted(exceeded),
    }
    validate_artifact(record, "rax_drift_signal_record")
    return record


def build_rax_conflict_arbitration_record(
    *,
    arbitration_id: str,
    target_ref: str,
    trace_id: str,
    eval_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build deterministic cross-eval conflict arbitration artifact."""
    statuses: dict[str, str] = {}
    reasons_by_type: dict[str, set[str]] = {}
    for item in eval_results:
        eval_type = _eval_type_from_result(item) or "unknown"
        statuses[eval_type] = str(item.get("result_status", "unknown"))
        reasons_by_type[eval_type] = {
            mode for mode in item.get("failure_modes", []) if isinstance(mode, str) and mode and ":" not in mode
        }

    material_conflicts: list[str] = []
    if statuses.get("rax_control_readiness") == "pass" and any(
        statuses.get(name) == "fail"
        for name in (
            "rax_input_semantic_sufficiency",
            "rax_owner_intent_alignment",
            "rax_output_semantic_alignment",
            "rax_trace_integrity",
            "rax_version_authority_alignment",
        )
    ):
        material_conflicts.append("readiness_vs_required_eval")

    if "source_version_drift" in reasons_by_type.get("rax_version_authority_alignment", set()) and statuses.get("rax_control_readiness") == "pass":
        material_conflicts.append("version_authority_vs_readiness")

    if "contradiction_unresolved" in reasons_by_type.get("rax_control_readiness", set()) and statuses.get("rax_output_semantic_alignment") == "pass":
        material_conflicts.append("contradiction_vs_semantic_alignment")

    if "missing_required_expansion_trace" in reasons_by_type.get("rax_trace_integrity", set()) and statuses.get("rax_control_readiness") == "pass":
        material_conflicts.append("trace_integrity_vs_readiness")

    record = {
        "artifact_type": "rax_conflict_arbitration_record",
        "schema_version": "1.0.0",
        "arbitration_id": arbitration_id,
        "target_ref": target_ref,
        "trace_id": trace_id,
        "signal_status": {k: statuses[k] for k in sorted(statuses)},
        "material_conflicts": sorted(set(material_conflicts)),
        "resolution_status": "unresolved_fail_closed" if material_conflicts else "no_conflict",
        "fail_closed": bool(material_conflicts),
    }
    validate_artifact(record, "rax_conflict_arbitration_record")
    return record


def build_rax_trend_report(*, report_id: str, window_ref: str, run_records: list[dict[str, Any]]) -> dict[str, Any]:
    total = max(len(run_records), 1)
    exploit_hits = sum(1 for run in run_records if run.get("exploit_hit"))
    blocks = sum(1 for run in run_records if run.get("blocked"))
    contradictions = sum(1 for run in run_records if run.get("contradiction"))
    overrides = sum(1 for run in run_records if run.get("override_or_escalation"))
    false_blocks = sum(1 for run in run_records if run.get("false_block_proxy"))
    false_allows = sum(1 for run in run_records if run.get("false_allow_proxy"))
    confidence_values = [float(run["confidence"]) for run in run_records if isinstance(run.get("confidence"), (int, float))]
    confidence_mean = (sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0

    report = {
        "artifact_type": "rax_trend_report",
        "schema_version": "1.0.0",
        "report_id": report_id,
        "window_ref": window_ref,
        "exploit_hit_rate": exploit_hits / total,
        "block_rate": blocks / total,
        "contradiction_rate": contradictions / total,
        "override_escalation_proxy_rate": overrides / total,
        "false_block_proxy_rate": false_blocks / total,
        "false_allow_proxy_rate": false_allows / total,
        "confidence_mean": confidence_mean,
        "sample_size": len(run_records),
    }
    validate_artifact(report, "rax_trend_report")
    return report


def build_rax_trust_posture_snapshot(*, snapshot_id: str, trend_report: dict[str, Any]) -> dict[str, Any]:
    posture = "stable"
    if trend_report["block_rate"] > 0.4 or trend_report["contradiction_rate"] > 0.2:
        posture = "degraded"
    if trend_report["false_allow_proxy_rate"] > 0.1:
        posture = "critical"

    snapshot = {
        "artifact_type": "rax_trust_posture_snapshot",
        "schema_version": "1.0.0",
        "snapshot_id": snapshot_id,
        "trend_report_ref": trend_report["report_id"],
        "posture": posture,
        "primary_signals": [
            f"block_rate:{trend_report['block_rate']:.3f}",
            f"contradiction_rate:{trend_report['contradiction_rate']:.3f}",
            f"false_allow_proxy_rate:{trend_report['false_allow_proxy_rate']:.3f}",
        ],
    }
    validate_artifact(snapshot, "rax_trust_posture_snapshot")
    return snapshot


def build_rax_improvement_recommendation_record(
    *,
    recommendation_id: str,
    posture_snapshot: dict[str, Any],
    trend_report: dict[str, Any],
) -> dict[str, Any]:
    recs: list[str] = []
    if trend_report["contradiction_rate"] > 0:
        recs.append("tighten_conflict_arbitration_eval_coverage")
    if trend_report["false_allow_proxy_rate"] > 0:
        recs.append("increase_semantic_blocking_regression_cases")
    if trend_report["exploit_hit_rate"] > 0.2:
        recs.append("expand_mutation_combinatorial_discovery_pack")

    record = {
        "artifact_type": "rax_improvement_recommendation_record",
        "schema_version": "1.0.0",
        "recommendation_id": recommendation_id,
        "posture_snapshot_ref": posture_snapshot["snapshot_id"],
        "trend_report_ref": trend_report["report_id"],
        "recommendations": sorted(set(recs)) or ["maintain_current_hardening"],
        "authority_note": "non_authoritative_advisory_only",
    }
    validate_artifact(record, "rax_improvement_recommendation_record")
    return record


def admit_failure_eval_candidate(
    *,
    candidate: dict[str, Any],
    admission_policy: dict[str, Any],
    canonical_registry: dict[str, Any],
) -> dict[str, Any]:
    validate_artifact(candidate, "rax_failure_eval_candidate")
    min_reasons = int(admission_policy.get("min_reason_codes", 1))
    allowed_eval_types = set(admission_policy.get("allowed_eval_types") or [])

    reasons = candidate.get("reason_codes", [])
    admitted = True
    denial_reasons: list[str] = []
    if len(reasons) < min_reasons:
        admitted = False
        denial_reasons.append("insufficient_reason_codes")
    if allowed_eval_types and candidate.get("eval_type") not in allowed_eval_types:
        admitted = False
        denial_reasons.append("eval_type_not_admissible")

    existing_ids = {item.get("candidate_id") for item in canonical_registry.get("admitted_candidates", [])}
    if candidate["candidate_id"] in existing_ids:
        admitted = False
        denial_reasons.append("duplicate_candidate")

    if admitted:
        canonical_registry.setdefault("admitted_candidates", []).append({
            "candidate_id": candidate["candidate_id"],
            "eval_case_id": candidate["eval_case_id"],
            "eval_type": candidate["eval_type"],
            "version": candidate.get("version", "1.0.0"),
        })

    record = {
        "artifact_type": "rax_eval_candidate_admission_record",
        "schema_version": "1.0.0",
        "candidate_id": candidate["candidate_id"],
        "admitted": admitted,
        "denial_reasons": sorted(set(denial_reasons)),
    }
    validate_artifact(record, "rax_eval_candidate_admission_record")
    return record


def compile_rax_judgment_record(
    *,
    judgment_id: str,
    target_ref: str,
    conflict_record: dict[str, Any],
    readiness_record: dict[str, Any],
) -> dict[str, Any]:
    if conflict_record.get("fail_closed"):
        outcome = "more_evidence_needed"
    elif readiness_record.get("ready_for_control"):
        outcome = "ready"
    else:
        outcome = "revise"

    record = {
        "artifact_type": "rax_judgment_record",
        "schema_version": "1.0.0",
        "judgment_id": judgment_id,
        "target_ref": target_ref,
        "judgment_outcome": outcome,
        "rationale": sorted(set(readiness_record.get("blocking_reasons", [])))[:10],
        "conflict_ref": conflict_record["arbitration_id"],
        "authority_note": "judgment_only_non_authoritative",
    }
    validate_artifact(record, "rax_judgment_record")
    return record


def enforce_rax_promotion_hard_gate(
    *,
    gate_id: str,
    readiness_record: dict[str, Any],
    replay_evidence_present: bool,
    eval_evidence_present: bool,
    observability_evidence_present: bool,
    policy_regression_evidence_present: bool,
) -> dict[str, Any]:
    missing: list[str] = []
    if not replay_evidence_present:
        missing.append("replay_evidence_missing")
    if not eval_evidence_present:
        missing.append("eval_evidence_missing")
    if not observability_evidence_present:
        missing.append("observability_evidence_missing")
    if not policy_regression_evidence_present:
        missing.append("policy_regression_evidence_missing")
    if readiness_record.get("ready_for_control") is not True:
        missing.append("readiness_not_ready")

    out = {
        "artifact_type": "rax_promotion_hard_gate_record",
        "schema_version": "1.0.0",
        "gate_id": gate_id,
        "passed": len(missing) == 0,
        "missing_evidence": sorted(set(missing)),
        "decision": "promote" if len(missing) == 0 else "block",
    }
    validate_artifact(out, "rax_promotion_hard_gate_record")
    return out


def build_rax_unknown_state_record(
    *,
    record_id: str,
    target_ref: str,
    unknown_reasons: list[str],
    evidence_refs: list[str],
) -> dict[str, Any]:
    status = "unknown_blocking" if unknown_reasons else "known"
    record = {
        "artifact_type": "rax_unknown_state_record",
        "schema_version": "1.0.0",
        "record_id": record_id,
        "target_ref": target_ref,
        "unknown_reasons": sorted(set(unknown_reasons)),
        "candidate_ready": False if unknown_reasons else True,
        "advancement_allowed": False if unknown_reasons else True,
        "evidence_refs": sorted(set(evidence_refs)),
        "status": status,
    }
    validate_artifact(record, "rax_unknown_state_record")
    return record


def generate_adversarial_pattern_candidates(*, seed: str, target_ref: str, count: int = 10) -> list[dict[str, Any]]:
    classes = [
        "schema_valid_semantic_boundary",
        "mutated_literal_variant",
        "nested_variant",
        "cross_step_contamination_variant",
        "partial_signal_contradiction",
        "semantic_drift_variant",
        "provenance_weakness_variant",
        "replay_weakness_variant",
        "ambiguity_variant",
        "weak_counter_evidence_variant",
        "hidden_scope_expansion_variant",
        "multi_signal_exploit_combo",
    ]
    base = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    out: list[dict[str, Any]] = []
    for index in range(count):
        class_name = classes[index % len(classes)]
        variant_id = f"rax-adv-{hashlib.sha256(f'{seed}:{index}'.encode('utf-8')).hexdigest()[:12]}"
        candidate = {
            "artifact_type": "rax_adversarial_pattern_candidate",
            "schema_version": "1.0.0",
            "variant_id": variant_id,
            "seed": seed,
            "variant_class": class_name,
            "target_ref": target_ref,
            "payload": {
                "mutator_index": index,
                "deterministic_token": (base + index) % 100000,
            },
            "consumable_by_eval": True,
        }
        validate_artifact(candidate, "rax_adversarial_pattern_candidate")
        out.append(candidate)
    return out


def run_rax_eval_runner(
    *,
    run_id: str,
    target_ref: str,
    trace_id: str,
    input_assurance: dict[str, Any],
    output_assurance: dict[str, Any],
    tests_passed: bool,
    baseline_regression_detected: bool,
    version_authority_aligned: bool,
    omit_eval_types: list[str] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run deterministic required RAX evals and emit eval_result/eval_summary artifacts."""
    policy = _load_policy(repo_root)
    required_eval_types = list(policy["required_eval_types"])
    blocking_codes = set(policy["blocking_failure_reason_codes"])
    omit = set(omit_eval_types or [])

    reason_map: dict[str, list[str]] = {
        "rax_input_semantic_sufficiency": [],
        "rax_owner_intent_alignment": [],
        "rax_normalization_integrity": [],
        "rax_output_semantic_alignment": [],
        "rax_acceptance_check_strength": [],
        "rax_trace_integrity": [],
        "rax_version_authority_alignment": [],
        "rax_regression_against_baseline": [],
        "rax_control_readiness": [],
    }

    for detail in input_assurance.get("details", []):
        if "semantic_intent_insufficient" in detail:
            reason_map["rax_input_semantic_sufficiency"].append("semantic_intent_insufficient")
        if "owner_intent_contradiction" in detail:
            reason_map["rax_owner_intent_alignment"].append("owner_intent_contradiction")
        if "normalization_ambiguity" in detail:
            reason_map["rax_normalization_integrity"].append("normalization_ambiguity")
        if "missing_required_expansion_trace" in detail or "trace " in detail:
            reason_map["rax_trace_integrity"].append("missing_required_expansion_trace")
        if "source_version_drift" in detail:
            reason_map["rax_version_authority_alignment"].append("source_version_drift")
        if "priority_inversion" in detail:
            reason_map["rax_normalization_integrity"].append("priority_inversion_detected")
        if "dependency_omission" in detail:
            reason_map["rax_control_readiness"].append("dependency_omission_detected")
        if "owner_intent_mismatch" in detail:
            reason_map["rax_owner_intent_alignment"].append("owner_intent_mismatch_detected")
        if "ambiguous_source_intent" in detail:
            reason_map["rax_input_semantic_sufficiency"].append("ambiguous_source_intent_detected")
        if "policy_meaning_drift" in detail:
            reason_map["rax_output_semantic_alignment"].append("policy_meaning_drift_detected")

    for detail in output_assurance.get("details", []):
        if "owner_target_contradiction" in detail:
            reason_map["rax_output_semantic_alignment"].append("semantic_target_mismatch")
        if "weak_acceptance_check" in detail:
            reason_map["rax_acceptance_check_strength"].append("weak_acceptance_check")
        if "semantic_expansion_mismatch" in detail:
            reason_map["rax_output_semantic_alignment"].append("semantic_expansion_mismatch")
        if "hidden_scope_expansion" in detail:
            reason_map["rax_output_semantic_alignment"].append("hidden_scope_expansion_detected")
        if "contradiction_unresolved" in detail:
            reason_map["rax_control_readiness"].append("contradiction_unresolved")
        if "weak_counter_evidence" in detail:
            reason_map["rax_control_readiness"].append("weak_counter_evidence_detected")

    if not tests_passed:
        reason_map["rax_control_readiness"].append("tests_failed")

    if baseline_regression_detected:
        reason_map["rax_regression_against_baseline"].append("baseline_regression_detected")

    if not version_authority_aligned and "source_version_drift" not in reason_map["rax_version_authority_alignment"]:
        reason_map["rax_version_authority_alignment"].append("source_version_drift")

    if tests_passed and any(reason_map[eval_type] for eval_type in required_eval_types if eval_type != "rax_control_readiness"):
        reason_map["rax_control_readiness"].append("tests_pass_eval_fail")

    eval_results: list[dict[str, Any]] = []
    for eval_type in required_eval_types:
        if eval_type in omit:
            continue
        reason_codes = sorted(set(reason_map[eval_type]))
        status = _status_from_reason_codes(reason_codes, blocking_codes=blocking_codes)
        result = {
            "artifact_type": "eval_result",
            "schema_version": "1.0.0",
            "eval_case_id": f"{run_id}:{eval_type}",
            "run_id": run_id,
            "trace_id": trace_id,
            "result_status": status,
            "score": _score_from_status(status),
            "failure_modes": [f"eval_type:{eval_type}", *list(reason_codes), f"runner:{RUNNER_NAME}:{RUNNER_VERSION}"],
            "provenance_refs": [target_ref, f"trace://{trace_id}", f"eval_type://{eval_type}"],
        }
        validate_artifact(result, "eval_result")
        eval_results.append(result)

    present_eval_types = sorted({etype for item in eval_results if (etype := _eval_type_from_result(item))})
    missing_required_eval_types = sorted(set(required_eval_types) - set(present_eval_types))
    fail_closed = bool(missing_required_eval_types)

    failures = [item for item in eval_results if item["result_status"] != "pass"]
    overall_fail = bool(failures) or fail_closed

    eval_summary = {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "eval_run_id": run_id,
        "pass_rate": 0.0 if not eval_results else sum(item["score"] for item in eval_results) / len(eval_results),
        "failure_rate": 1.0 if not eval_results else len(failures) / len(eval_results),
        "drift_rate": 1.0 if baseline_regression_detected else 0.0,
        "reproducibility_score": 1.0,
        "system_status": "failing" if overall_fail else "healthy",
    }
    validate_artifact(eval_summary, "eval_summary")

    all_reasons = sorted(set(_reason_codes_from_results(eval_results)))
    generated = generate_failure_eval_artifacts(
        run_id=run_id,
        target_ref=target_ref,
        trace_id=trace_id,
        source_artifact_refs=[f"eval_run://{run_id}", f"eval_summary://{run_id}"],
        reason_codes=all_reasons,
        failure_classification=(input_assurance.get("failure_classification") if input_assurance.get("failure_classification") != "none" else output_assurance.get("failure_classification")),
        reproducibility_inputs={
            "tests_passed": tests_passed,
            "baseline_regression_detected": baseline_regression_detected,
            "version_authority_aligned": version_authority_aligned,
            "omit_eval_types": sorted(omit),
        },
    )

    adversarial = generate_adversarial_pattern_candidates(seed=run_id, target_ref=target_ref)

    return {
        "eval_results": eval_results,
        "eval_summary": eval_summary,
        "required_eval_coverage": {
            "required_eval_types": required_eval_types,
            "present_eval_types": present_eval_types,
            "missing_required_eval_types": missing_required_eval_types,
            "overall_result": "fail" if overall_fail else "pass",
            "missing_required_eval_handling": policy.get("missing_required_eval_handling", "fail_closed"),
        },
        "failure_pattern_records": generated["failure_pattern_records"],
        "eval_case_candidates": generated["eval_case_candidates"],
        "adversarial_pattern_candidates": adversarial,
    }


def build_rax_control_readiness_record(
    *,
    batch: str,
    target_ref: str,
    eval_summary: dict[str, Any],
    eval_results: list[dict[str, Any]],
    required_eval_coverage: dict[str, Any],
    assurance_audit: dict[str, Any] | None = None,
    trace_integrity_evidence: dict[str, Any] | None = None,
    lineage_provenance_evidence: dict[str, Any] | None = None,
    dependency_state: dict[str, Any] | None = None,
    authority_records: dict[str, Any] | None = None,
    replay_baseline_store: dict[str, Any] | None = None,
    replay_key: str | None = None,
    health_snapshot: dict[str, Any] | None = None,
    drift_signal_record: dict[str, Any] | None = None,
    unknown_state_record: dict[str, Any] | None = None,
    pre_certification_alignment_record: dict[str, Any] | None = None,
    policy_version: str = "1.0.0",
    semantic_rule_version: str = "1.0.0",
    eval_config_version: str = "1.0.0",
    contradiction_logic_version: str = "1.0.0",
) -> dict[str, Any]:
    policy = _load_policy()
    required_eval_types = list(policy.get("required_eval_types", []))

    present_eval_types = sorted({etype for item in eval_results if (etype := _eval_type_from_result(item))})
    missing_required_eval_types = sorted(set(required_eval_types) - set(present_eval_types))
    reason_codes = _reason_codes_from_results(eval_results)

    blocking_reasons: list[str] = []
    if not required_eval_types:
        blocking_reasons.append("required_eval_types_unavailable")
    if missing_required_eval_types:
        blocking_reasons.append("missing_required_eval_types")
        blocking_reasons.extend(f"missing_eval:{name}" for name in missing_required_eval_types)

    declared_required = set(required_eval_coverage.get("required_eval_types") or [])
    if declared_required and declared_required != set(required_eval_types):
        blocking_reasons.append("required_eval_types_mismatch_with_governed_policy")

    summary_present = set(required_eval_coverage.get("present_eval_types") or [])
    if summary_present != set(present_eval_types):
        blocking_reasons.append("required_eval_coverage_summary_mismatch")

    declared_missing = set(required_eval_coverage.get("missing_required_eval_types") or [])
    if declared_missing != set(missing_required_eval_types):
        blocking_reasons.append("required_eval_coverage_missing_set_mismatch")

    overall_fail = bool(missing_required_eval_types)
    has_eval_failures = False
    for item in eval_results:
        eval_type = _eval_type_from_result(item)
        if eval_type in required_eval_types and item.get("result_status") != "pass":
            has_eval_failures = True
            blocking_reasons.append(f"required_eval_failed:{eval_type}")
            overall_fail = True

    if has_eval_failures:
        blocking_reasons.append("contradictory_eval_signals")

    if required_eval_coverage.get("overall_result") != ("pass" if not overall_fail else "fail"):
        blocking_reasons.append("required_eval_coverage_overall_result_mismatch")

    if eval_summary.get("system_status") == "healthy" and (overall_fail or has_eval_failures):
        blocking_reasons.append("eval_summary_contradicts_eval_results")

    if reason_codes:
        blocking_reasons.extend(reason_codes)

    if assurance_audit is None:
        blocking_reasons.append("missing_assurance_audit_artifact")
    else:
        if assurance_audit.get("acceptance_decision") != "accept_candidate":
            blocking_reasons.append("assurance_audit_not_accept_candidate")
        if _critical_failure_classification(assurance_audit.get("failure_classification")):
            blocking_reasons.append("critical_failure_classification_present")
        if assurance_audit.get("counter_evidence") == [] and _critical_failure_classification(assurance_audit.get("failure_classification")):
            blocking_reasons.append("failure_without_counter_evidence")
        if not _counter_evidence_is_material(assurance_audit.get("counter_evidence")):
            blocking_reasons.append("weak_counter_evidence_detected")

    derived_trace = _trace_lineage_from_eval_results(
        eval_results=eval_results,
        target_ref=target_ref,
        expected_trace_id=eval_summary.get("trace_id") if isinstance(eval_summary, dict) else None,
    )
    if not derived_trace["trace_linked"]:
        blocking_reasons.append("artifact_not_trace_linked")
    if not derived_trace["trace_complete"]:
        blocking_reasons.append("trace_incomplete")

    if trace_integrity_evidence is None:
        blocking_reasons.append("missing_trace_integrity_evidence")
    else:
        if trace_integrity_evidence.get("trace_linked") is not True:
            blocking_reasons.append("artifact_not_trace_linked")
        if trace_integrity_evidence.get("trace_complete") is not True:
            blocking_reasons.append("trace_incomplete")

    if lineage_provenance_evidence is None:
        blocking_reasons.append("missing_lineage_provenance_evidence")
    else:
        if lineage_provenance_evidence.get("lineage_valid") is not True:
            blocking_reasons.append("artifact_lineage_invalid")
        if lineage_provenance_evidence.get("lineage_chain_complete") is not True:
            blocking_reasons.append("artifact_lineage_incomplete")

    if dependency_state is None:
        blocking_reasons.append("missing_dependency_state")
    else:
        if dependency_state.get("graph_integrity") is not True:
            blocking_reasons.append("dependency_graph_corrupt")
        unresolved = dependency_state.get("unresolved_dependencies") or []
        if unresolved:
            blocking_reasons.append("dependency_graph_unresolved")

    if authority_records is None or not authority_records:
        blocking_reasons.append("missing_version_authority_evidence")

    baseline_regression_detected = "baseline_regression_detected" in reason_codes
    if baseline_regression_detected:
        blocking_reasons.append("baseline_regression_detected")

    version_authority_aligned = "source_version_drift" not in reason_codes and "missing_version_authority_evidence" not in blocking_reasons

    cross_run_inconsistency = False
    if (replay_baseline_store is None) ^ (replay_key is None):
        blocking_reasons.append("replay_consistency_evidence_incomplete")
    if replay_baseline_store is not None and replay_key:
        signal = _canonical_eval_signal(eval_results)
        previous = replay_baseline_store.get(replay_key)
        if previous is not None and tuple(previous.get("signal", ())) != signal:
            cross_run_inconsistency = True
            blocking_reasons.append("cross_run_eval_signal_inconsistency")
        replay_baseline_store[replay_key] = {"signal": signal, "target_ref": target_ref}

    unknown_reasons: list[str] = []
    if not eval_results:
        unknown_reasons.append("required_signal_missing")
    if assurance_audit is None:
        unknown_reasons.append("required_artifact_missing")
    if eval_summary.get("system_status") == "healthy" and reason_codes:
        unknown_reasons.append("contradictory_derived_fields")
    if authority_records is None or not authority_records:
        unknown_reasons.append("incomplete_authority_evidence")
    if (replay_baseline_store is None) ^ (replay_key is None):
        unknown_reasons.append("partial_replay_evidence")
    if cross_run_inconsistency:
        unknown_reasons.append("inconsistent_replay_state")
    if not derived_trace["trace_complete"]:
        unknown_reasons.append("unverifiable_readiness_basis")

    if unknown_state_record is None:
        unknown_state_record = build_rax_unknown_state_record(
            record_id=f"unknown:{batch}:{eval_summary.get('trace_id', 'missing')}",
            target_ref=target_ref,
            unknown_reasons=unknown_reasons,
            evidence_refs=[target_ref, f"trace://{eval_summary.get('trace_id', 'missing')}", f"eval_run://{eval_summary.get('eval_run_id', 'missing')}"] if isinstance(eval_summary, dict) else [target_ref],
        )

    if unknown_state_record.get("status") == "unknown_blocking":
        blocking_reasons.append("unknown_state_detected")

    conflict_arbitration_record = build_rax_conflict_arbitration_record(
        arbitration_id=f"conflict:{batch}:{eval_summary.get('trace_id', 'missing')}",
        target_ref=target_ref,
        trace_id=str(eval_summary.get("trace_id", "missing")),
        eval_results=eval_results,
    )
    if conflict_arbitration_record["fail_closed"]:
        blocking_reasons.append("material_conflict_unresolved")

    replay_identity_fingerprint = hashlib.sha256(
        f"{target_ref}|{policy_version}|{semantic_rule_version}|{eval_config_version}|{contradiction_logic_version}".encode("utf-8")
    ).hexdigest()[:24]

    trace_complete = (
        "rax_trace_integrity" in present_eval_types
        and "rax_trace_integrity" not in missing_required_eval_types
        and derived_trace["trace_complete"] is True
        and derived_trace["trace_linked"] is True
        and (trace_integrity_evidence or {}).get("trace_complete") is True
        and (trace_integrity_evidence or {}).get("trace_linked") is True
    )

    readiness_conditions: list[dict[str, Any]] = []
    mapping = {
        "missing_required_eval_types": "missing_eval_becomes_present",
        "dependency_graph_corrupt": "dependency_state_changes",
        "trace_incomplete": "trace_becomes_complete",
        "artifact_lineage_invalid": "lineage_repaired",
        "missing_version_authority_evidence": "authority_version_evidence_present",
        "baseline_regression_detected": "baseline_regression_resolved",
        "cross_run_eval_signal_inconsistency": "drift_signal_clears",
    }
    for reason in sorted(set(blocking_reasons)):
        category = mapping.get(reason)
        if not category:
            continue
        readiness_conditions.append(
            {
                "condition_category": category,
                "blocking_reason": reason,
                "evidence_refs": [target_ref, f"trace://{eval_summary.get('trace_id', 'missing')}"],
                "required_signal": reason,
            }
        )

    # If caller provides artifacts, consume them without granting authority.
    if health_snapshot is not None:
        if health_snapshot.get("candidate_posture") in {"freeze_candidate", "block_candidate"}:
            blocking_reasons.append("health_threshold_degraded")
    if drift_signal_record is not None:
        if drift_signal_record.get("candidate_posture") in {"freeze_candidate", "block_candidate"}:
            blocking_reasons.append("drift_threshold_exceeded")

    if pre_certification_alignment_record is None:
        pre_certification_alignment_record = {
            "artifact_type": "rax_pre_certification_alignment_record",
            "schema_version": "1.0.0",
            "record_id": f"precert:{batch}:{eval_summary.get('trace_id', 'missing')}",
            "target_ref": target_ref,
            "eval_completeness_aligned": not missing_required_eval_types,
            "replay_consistency_aligned": not cross_run_inconsistency,
            "trace_completeness_aligned": trace_complete,
            "lineage_validity_aligned": (lineage_provenance_evidence or {}).get("lineage_valid") is True,
            "fail_closed_aligned": bool(blocking_reasons),
            "semantic_correctness_aligned": "semantic_target_mismatch" not in reason_codes,
            "ready_candidate_allowed": False,
            "blocking_reasons": sorted(set(blocking_reasons)),
        }
        validate_artifact(pre_certification_alignment_record, "rax_pre_certification_alignment_record")

    if pre_certification_alignment_record.get("ready_candidate_allowed") is not True:
        blocking_reasons.append("pre_certification_alignment_not_ready")

    blocking_reasons = sorted(set(blocking_reasons))
    ready_for_control = len(blocking_reasons) == 0 and unknown_state_record.get("status") != "unknown_blocking"
    if ready_for_control:
        decision = "ready"
    elif cross_run_inconsistency:
        decision = "hold"
    else:
        decision = "block"

    if blocking_reasons and decision == "ready":
        decision = "block"
        ready_for_control = False

    record = {
        "artifact_type": "rax_control_readiness_record",
        "schema_version": "1.1.0",
        "batch": batch,
        "target_ref": target_ref,
        "ready_for_control": ready_for_control,
        "decision": decision,
        "blocking_reasons": blocking_reasons,
        "required_eval_types": required_eval_types,
        "present_eval_types": present_eval_types,
        "missing_required_eval_types": missing_required_eval_types,
        "trace_complete": trace_complete,
        "baseline_regression_detected": baseline_regression_detected,
        "version_authority_aligned": version_authority_aligned,
        "conditions_under_which_ready_changes": readiness_conditions,
        "unknown_state_ref": unknown_state_record["record_id"],
        "pre_certification_alignment_ref": pre_certification_alignment_record["record_id"],
        "conflict_arbitration_ref": conflict_arbitration_record["arbitration_id"],
        "non_authority_assertions": [
            "readiness_is_non_authoritative",
            "no_promotion_or_release_authority",
            "control_transition_requires_downstream_control_artifact",
        ],
        "replay_identity": {
            "policy_version": policy_version,
            "semantic_rule_version": semantic_rule_version,
            "eval_config_version": eval_config_version,
            "contradiction_logic_version": contradiction_logic_version,
            "fingerprint": replay_identity_fingerprint,
        },
    }
    validate_artifact(record, "rax_control_readiness_record")

    return {
        **record,
        "unknown_state_record": deepcopy(unknown_state_record),
        "pre_certification_alignment_record": deepcopy(pre_certification_alignment_record),
        "conflict_arbitration_record": deepcopy(conflict_arbitration_record),
    }


def enforce_rax_control_advancement(*, readiness_record: dict[str, Any] | None) -> dict[str, Any]:
    """Mandatory fail-closed control-readiness gate for advancement."""
    reasons: list[str] = []
    if readiness_record is None:
        reasons.append("missing_control_readiness_artifact")
    else:
        try:
            validate_artifact(readiness_record, "rax_control_readiness_record")
        except Exception:
            reasons.append("malformed_control_readiness_artifact")
        else:
            if readiness_record.get("ready_for_control") is not True:
                reasons.append("control_readiness_not_ready")
            if readiness_record.get("decision") != "ready":
                reasons.append("control_readiness_decision_not_ready")
            if readiness_record.get("blocking_reasons"):
                reasons.append("control_readiness_has_blocking_reasons")

    return {
        "allowed": len(reasons) == 0,
        "decision": "ready" if len(reasons) == 0 else "block",
        "ready_for_control": len(reasons) == 0,
        "blocking_reasons": sorted(set(reasons)),
    }


def enforce_required_rax_eval_coverage(*, eval_results: list[dict[str, Any]], required_eval_coverage: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed enforcement record for missing or incomplete required RAX eval coverage."""
    required_eval_types = set(required_eval_coverage.get("required_eval_types") or [])
    present_eval_types = {_eval_type_from_result(item) for item in eval_results}
    present_eval_types.discard(None)
    missing_from_results = sorted(required_eval_types - present_eval_types)
    missing_from_summary = sorted(required_eval_types - set(required_eval_coverage.get("present_eval_types") or []))

    blocked = bool(missing_from_results or missing_from_summary or required_eval_coverage.get("overall_result") != "pass")
    reasons: list[str] = []
    if missing_from_results:
        reasons.append("missing_required_eval_artifact")
    if missing_from_summary:
        reasons.append("eval_summary_missing_required_eval_reference")
    if required_eval_coverage.get("overall_result") != "pass":
        reasons.append("eval_summary_not_pass")

    return {
        "blocked": blocked,
        "reasons": sorted(set(reasons)),
        "missing_from_results": missing_from_results,
        "missing_from_summary": missing_from_summary,
    }
