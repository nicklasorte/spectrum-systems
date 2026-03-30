"""Deterministic judgment evaluation runner for fail-closed control gating."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from spectrum_systems.contracts import validate_artifact


class JudgmentEvalRunnerError(ValueError):
    """Raised when judgment evaluation cannot be completed deterministically."""


_SUPPORTED_EVAL_TYPES = {
    "evidence_coverage",
    "policy_alignment",
    "replay_consistency",
    "uncertainty_calibration",
    "longitudinal_calibration",
    "judgment_outcome_drift_signal",
}


def _canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _claim_entries(judgment_record: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for idx, claim in enumerate(judgment_record.get("claims_considered", [])):
        if isinstance(claim, str):
            entries.append(
                {
                    "claim_id": f"claim-{idx + 1:03d}",
                    "claim_text": claim,
                    "is_material": True,
                    "supported_by_evidence_ids": [],
                }
            )
            continue
        if isinstance(claim, dict):
            entries.append(
                {
                    "claim_id": claim.get("claim_id") or f"claim-{idx + 1:03d}",
                    "claim_text": claim.get("claim_text") or "",
                    "is_material": bool(claim.get("is_material", True)),
                    "supported_by_evidence_ids": sorted(
                        [str(x) for x in claim.get("supported_by_evidence_ids", []) if isinstance(x, str) and x]
                    ),
                }
            )
    return entries


def _evaluate_evidence_coverage(*, judgment_record: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    cfg = (policy.get("judgment_eval_requirements") or {}).get("evidence_coverage") or {}
    minimum_score = float(cfg.get("minimum_score", 1.0))
    fail_closed_on_missing_material = bool(cfg.get("fail_closed_on_missing_material", True))

    evidence_set = {str(x) for x in judgment_record.get("evidence_refs", []) if isinstance(x, str) and x}
    claims = _claim_entries(judgment_record)
    material_claims = [claim for claim in claims if claim["is_material"]]

    supported_material = 0
    unsupported_material_ids: list[str] = []
    for claim in material_claims:
        linked = [ref for ref in claim["supported_by_evidence_ids"] if ref in evidence_set]
        if linked:
            supported_material += 1
        else:
            unsupported_material_ids.append(claim["claim_id"])

    total_material = len(material_claims)
    score = 1.0 if total_material == 0 else round(supported_material / total_material, 6)
    passed = score >= minimum_score
    if fail_closed_on_missing_material and unsupported_material_ids:
        passed = False

    return {
        "eval_type": "evidence_coverage",
        "passed": passed,
        "score": score,
        "threshold": minimum_score,
        "details": {
            "material_claims_total": total_material,
            "material_claims_supported": supported_material,
            "unsupported_material_claim_ids": unsupported_material_ids,
            "fail_closed_on_missing_material": fail_closed_on_missing_material,
        },
    }


def _evaluate_policy_alignment(*, judgment_record: dict[str, Any], application_record: dict[str, Any]) -> dict[str, Any]:
    selected_outcome = judgment_record.get("selected_outcome")
    policy_outcome = application_record.get("final_outcome")

    deviations = [str(x) for x in application_record.get("deviations", []) if isinstance(x, str)]
    has_explicit_deviation = any(msg.startswith("policy_deviation:") for msg in deviations)
    aligned = selected_outcome == policy_outcome
    passed = aligned or has_explicit_deviation

    return {
        "eval_type": "policy_alignment",
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "threshold": 1.0,
        "details": {
            "judgment_selected_outcome": selected_outcome,
            "policy_final_outcome": policy_outcome,
            "aligned": aligned,
            "explicit_deviation_recorded": has_explicit_deviation,
            "deviation_entries": deviations,
        },
    }


def _build_replay_fingerprint(*, judgment_record: dict[str, Any], application_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "judgment_type": judgment_record.get("judgment_type"),
        "selected_outcome": judgment_record.get("selected_outcome"),
        "policy_ref": judgment_record.get("policy_ref"),
        "rules_applied": list(judgment_record.get("rules_applied", [])),
        "context_fingerprint": dict(judgment_record.get("context_fingerprint", {})),
        "application_final_outcome": application_record.get("final_outcome"),
    }


def _evaluate_replay_consistency(
    *,
    judgment_record: dict[str, Any],
    application_record: dict[str, Any],
    replay_reference: dict[str, Any] | None,
) -> dict[str, Any]:
    current_fingerprint = _build_replay_fingerprint(judgment_record=judgment_record, application_record=application_record)
    current_hash = _canonical_hash(current_fingerprint)

    if replay_reference is None:
        return {
            "eval_type": "replay_consistency",
            "passed": True,
            "score": 1.0,
            "threshold": 1.0,
            "details": {
                "comparison_mode": "self_consistency",
                "current_fingerprint_hash": current_hash,
            },
        }

    ref = replay_reference.get("replay_reference") if isinstance(replay_reference, dict) else None
    reference_hash = ref.get("fingerprint_hash") if isinstance(ref, dict) else None
    passed = isinstance(reference_hash, str) and reference_hash == current_hash
    return {
        "eval_type": "replay_consistency",
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "threshold": 1.0,
        "details": {
            "comparison_mode": "artifact_reference",
            "reference_fingerprint_hash": reference_hash,
            "current_fingerprint_hash": current_hash,
        },
    }


def _evaluate_uncertainty_calibration(*, judgment_record: dict[str, Any]) -> dict[str, Any]:
    uncertainties = [str(x) for x in judgment_record.get("uncertainties", []) if isinstance(x, str)]
    return {
        "eval_type": "uncertainty_calibration",
        "passed": True,
        "score": 1.0,
        "threshold": 0.0,
        "details": {
            "status": "scaffold_only",
            "uncertainty_count": len(uncertainties),
            "labeling_required_next_phase": True,
        },
    }


def _evaluate_longitudinal_calibration() -> dict[str, Any]:
    return {
        "eval_type": "longitudinal_calibration",
        "passed": True,
        "score": 1.0,
        "threshold": 0.0,
        "details": {
            "status": "scaffold_only",
            "calibration_window_defined": False,
            "requires_labeled_outcomes": True,
        },
    }


def _evaluate_drift_signal(*, judgment_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "eval_type": "judgment_outcome_drift_signal",
        "passed": True,
        "score": 1.0,
        "threshold": 0.0,
        "details": {
            "status": "scaffold_only",
            "judgment_outcome": judgment_record.get("selected_outcome"),
            "drift_metric_placeholder": "outcome_frequency_delta",
        },
    }


def run_judgment_evals(
    *,
    cycle_id: str,
    created_at: str,
    judgment_record: dict[str, Any],
    application_record: dict[str, Any],
    policy: dict[str, Any],
    replay_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evals = [
        _evaluate_evidence_coverage(judgment_record=judgment_record, policy=policy),
        _evaluate_policy_alignment(judgment_record=judgment_record, application_record=application_record),
        _evaluate_replay_consistency(
            judgment_record=judgment_record,
            application_record=application_record,
            replay_reference=replay_reference,
        ),
        _evaluate_uncertainty_calibration(judgment_record=judgment_record),
        _evaluate_longitudinal_calibration(),
        _evaluate_drift_signal(judgment_record=judgment_record),
    ]

    failed_required = [item["eval_type"] for item in evals if item["eval_type"] in {"evidence_coverage", "policy_alignment", "replay_consistency"} and not item["passed"]]
    determinism_passed = len(failed_required) == 0

    payload = {
        "artifact_type": "judgment_eval_result",
        "artifact_id": f"judgment-eval-{cycle_id}",
        "artifact_version": "1.1.0",
        "schema_version": "1.1.0",
        "standards_version": "1.0.93",
        "judgment_type": judgment_record.get("judgment_type"),
        "determinism_check": "passed" if determinism_passed else "failed",
        "required_eval_types": ["evidence_coverage", "policy_alignment", "replay_consistency"],
        "eval_results": evals,
        "calibration_scaffolding": {
            "outcome_label_input_path": "judgment_outcome_labels",
            "longitudinal_artifact_path": "judgment_calibration_runs",
        },
        "drift_signal_scaffolding": {
            "signal_type": "judgment_outcome_distribution_shift",
            "metric_inputs": ["judgment_type", "selected_outcome", "policy_ref", "created_at"],
        },
        "replay_reference": {
            "fingerprint_hash": _canonical_hash(_build_replay_fingerprint(judgment_record=judgment_record, application_record=application_record))
        },
        "notes": [
            "deterministic evidence/policy/replay eval ordering is fixed",
            "calibration and drift sections are intentionally scaffold-level",
        ],
        "created_at": created_at,
    }

    eval_types = {entry["eval_type"] for entry in payload["eval_results"]}
    if eval_types != _SUPPORTED_EVAL_TYPES:
        raise JudgmentEvalRunnerError("judgment eval runner emitted unsupported eval type set")

    validate_artifact(payload, "judgment_eval_result")
    return payload
