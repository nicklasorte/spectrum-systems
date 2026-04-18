from __future__ import annotations

from collections import Counter
from typing import Any

from spectrum_systems.contracts import validate_artifact


class BNE02BlockError(RuntimeError):
    """Fail-closed hard-stop error for BNE-02 governance checks."""


def _validate(instance: dict[str, Any], schema_name: str) -> dict[str, Any]:
    validate_artifact(instance, schema_name)
    return instance


def enforce_global_invariants(*, gate: str, trace_id: str, run_id: str, artifact: dict[str, Any]) -> dict[str, Any]:
    eval_present = bool(artifact.get("eval"))
    control_signal_present = bool(artifact.get("control_signal"))
    lineage_present = bool(artifact.get("lineage"))
    schema_valid = bool(artifact.get("schema_valid", False))
    critical_status = artifact.get("critical_eval_status")
    critical_eval_determinate = critical_status in {"pass", "fail"}

    reasons: list[str] = []
    gate_status = "pass"
    if not eval_present:
        reasons.append("missing_eval")
    if not control_signal_present:
        reasons.append("missing_control_signal")
    if not lineage_present:
        reasons.append("missing_lineage")
    if not schema_valid:
        reasons.append("schema_validation_failed")
    if critical_status == "indeterminate":
        reasons.append("critical_eval_indeterminate")
        gate_status = "indeterminate"
    elif critical_status is None:
        reasons.append("critical_eval_status_missing")
        gate_status = "fail"
    elif critical_status not in {"pass", "fail"}:
        reasons.append("critical_eval_status_unknown")
        gate_status = "fail"

    if reasons and gate_status == "pass":
        gate_status = "fail"

    result = {
        "artifact_type": "global_invariant_check_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "run_id": run_id,
        "gate": gate,
        "gate_status": gate_status,
        "blocking_reasons": sorted(set(reasons)),
        "requirements_satisfied": {
            "eval_present": eval_present,
            "control_signal_present": control_signal_present,
            "lineage_present": lineage_present,
            "schema_valid": schema_valid,
            "critical_eval_determinate": critical_eval_determinate,
        },
        "authority_required": True,
    }
    return _validate(result, "global_invariant_check_record")


def enforce_artifact_eval_requirement_profile(
    *, artifact_family: str, requirement_profile: dict[str, list[str]] | None
) -> tuple[list[str], list[str]]:
    if requirement_profile is None:
        raise BNE02BlockError("missing eval requirement profile")
    if artifact_family not in requirement_profile:
        raise BNE02BlockError(f"missing eval requirement profile for artifact family: {artifact_family}")
    required_eval_ids = [eval_id for eval_id in requirement_profile[artifact_family] if isinstance(eval_id, str) and eval_id]
    if not required_eval_ids:
        raise BNE02BlockError(f"empty eval requirement profile for artifact family: {artifact_family}")
    return sorted(set(required_eval_ids)), sorted(required_eval_ids)


def compute_eval_coverage_artifact(
    *,
    trace_id: str,
    artifact_family: str,
    stage: str,
    required_eval_ids: list[str],
    observed_eval_ids: list[str],
) -> dict[str, Any]:
    required = sorted(set(required_eval_ids))
    observed = sorted(set(observed_eval_ids))
    missing = sorted(set(required) - set(observed))
    coverage_ratio = 1.0 if not required else (len(required) - len(missing)) / len(required)
    gate_status = "fail" if missing else "pass"
    blocking_reasons = ["required_eval_missing"] if missing else []
    artifact = {
        "artifact_type": "eval_coverage_artifact",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "artifact_family": artifact_family,
        "stage": stage,
        "required_eval_ids": required,
        "observed_eval_ids": observed,
        "missing_eval_ids": missing,
        "coverage_ratio": coverage_ratio,
        "gate_status": gate_status,
        "blocking_reasons": blocking_reasons,
        "authority_required": True,
    }
    return _validate(artifact, "eval_coverage_artifact")


def build_eval_slice_summary(*, eval_cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_agency = Counter(str(case.get("agency", "unknown")) for case in eval_cases)
    by_risk = Counter(str(case.get("risk", "unknown")) for case in eval_cases)
    by_topic = Counter(str(case.get("topic", "unknown")) for case in eval_cases)
    missing = [case for case in eval_cases if case.get("status") != "pass"]
    return {
        "artifact_type": "eval_slice_summary",
        "total_cases": len(eval_cases),
        "failing_cases": len(missing),
        "slices": {
            "agency": dict(by_agency),
            "risk": dict(by_risk),
            "topic": dict(by_topic),
        },
        "gate_status": "fail" if missing else "pass",
        "authority_required": True,
    }


def run_eval_redteam_blind_spots(*, eval_cases: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for idx, case in enumerate(eval_cases, start=1):
        fake_green = case.get("status") == "pass" and case.get("grounded") is False
        if fake_green:
            findings.append(
                {
                    "finding_id": f"RTX-13-{idx}",
                    "failure_mode": "fake_green",
                    "eval_id": str(case.get("eval_id", "unknown")),
                    "severity": "high",
                    "status": "open",
                }
            )
    return {"artifact_type": "eval_redteam_findings", "findings": findings}


def fix_eval_blind_spots(*, findings: list[dict[str, Any]], existing_eval_ids: list[str]) -> dict[str, Any]:
    fixes = []
    regression_eval_ids = set(existing_eval_ids)
    for finding in findings:
        finding_id = str(finding["finding_id"])
        eval_id = f"regression.{finding_id.lower()}"
        regression_eval_ids.add(eval_id)
        fixes.append({"finding_id": finding_id, "fix_id": f"FIX-13-{finding_id}", "regression_eval_id": eval_id})
    return {
        "artifact_type": "eval_blind_spot_fix_result",
        "fixes": fixes,
        "regression_eval_ids": sorted(regression_eval_ids),
    }


def evaluate_promotion_gate(
    *,
    trace_id: str,
    run_id: str,
    eval_pass: bool,
    lineage_complete: bool,
    judgment_present: bool,
    policy_aligned: bool,
) -> dict[str, Any]:
    reqs = {
        "eval_complete": bool(eval_pass),
        "lineage_complete": bool(lineage_complete),
        "judgment_present": bool(judgment_present),
        "policy_aligned": bool(policy_aligned),
    }
    reasons = [f"missing_{name}" for name, status in reqs.items() if not status]
    gate_status = "fail" if reasons else "pass"
    artifact = {
        "artifact_type": "readiness_gate_evidence_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "run_id": run_id,
        "gate_status": gate_status,
        "requirements_satisfied": reqs,
        "blocking_reasons": reasons,
        "authority_required": True,
    }
    return _validate(artifact, "promotion_gate_evidence_record")


def build_certification_record(
    *,
    trace_id: str,
    run_id: str,
    checks: dict[str, bool],
    redteam_findings: list[dict[str, Any]],
    fixes: list[dict[str, Any]],
    remaining_risks: list[str],
) -> dict[str, Any]:
    fix_ids_by_finding = {str(entry.get("finding_id")) for entry in fixes}
    normalized_findings = []
    unresolved = []
    for finding in redteam_findings:
        finding_id = str(finding["finding_id"])
        is_fixed = finding_id in fix_ids_by_finding
        normalized_findings.append({"finding_id": finding_id, "status": "fixed" if is_fixed else "open"})
        if not is_fixed:
            unresolved.append(finding_id)

    required_checks = ["eval_coverage", "promotion_prereqs", "policy_coverage", "context_integrity", "drift_control"]
    check_status = {name: bool(checks.get(name, False)) for name in required_checks}
    normalized_remaining_risks = [risk.strip() for risk in remaining_risks if isinstance(risk, str) and risk.strip()]
    checks_ok = all(check_status.values())
    gate_status = "pass" if checks_ok and not unresolved and not normalized_remaining_risks else "fail"

    artifact = {
        "artifact_type": "readiness_closeout_evidence_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "run_id": run_id,
        "gate_status": gate_status,
        "requirements_satisfied": check_status,
        "redteam_findings": normalized_findings,
        "fixes": [
            {"finding_id": str(entry["finding_id"]), "fix_id": str(entry["fix_id"])}
            for entry in fixes
        ],
        "remaining_risks": normalized_remaining_risks,
        "authority_required": True,
    }
    return _validate(artifact, "certification_evidence_record")
