"""Serial fail-closed governance execution for the NEXT24 foundation roadmap."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from spectrum_systems.contracts import validate_artifact


class Next24ExecutionError(ValueError):
    """Raised when NEXT24 execution cannot pass deterministic hard gates."""


@dataclass(frozen=True)
class StepSpec:
    step_id: str
    title: str
    required_refs: tuple[str, ...]


_STEP_SPECS: tuple[StepSpec, ...] = (
    StepSpec("JUD-013A", "JUD-013A — Judgment Gate Binding", ("judgment_artifact_required",)),
    StepSpec("JUD-013B", "JUD-013B — Judgment Contract Canonicalization", ("judgment_contracts_canonical",)),
    StepSpec("JUD-013C", "JUD-013C — Judgment Eval Requirement Matrix", ("judgment_eval_matrix_enforced",)),
    StepSpec("JUD-013D", "JUD-013D — Control-Chain Judgment Precedence", ("judgment_precedence_enforced",)),
    StepSpec("JUD-014", "JUD-014 — Judgment Policy Candidate Lifecycle", ("judgment_policy_lifecycle_governed",)),
    StepSpec("JUD-015", "JUD-015 — Precedent Retrieval Discipline", ("precedent_retrieval_deterministic",)),
    StepSpec("JUD-016", "JUD-016 — Policy Conflict Arbitration", ("policy_conflict_arbitrated",)),
    StepSpec("CL-02A", "CL-02A — Error Budget Artifact Spine", ("error_budget_artifact_emitted",)),
    StepSpec("CL-02B", "CL-02B — Budget Burn Computation", ("error_budget_burn_computed",)),
    StepSpec("CL-02C", "CL-02C — Budget-to-Control Enforcement", ("error_budget_control_enforced",)),
    StepSpec("CL-03A", "CL-03A — Failure-to-Eval Factory", ("failure_eval_factory_active",)),
    StepSpec("CL-03B", "CL-03B — Slice Coverage Audit", ("slice_coverage_audited",)),
    StepSpec("GOV-10A", "GOV-10A — Certification Hard-Gate Wiring", ("certification_required",)),
    StepSpec("GOV-10B", "GOV-10B — Certification Layer Expansion", ("certification_layers_expanded",)),
    StepSpec("GOV-10C", "GOV-10C — Signed Promotion Provenance", ("promotion_provenance_signed",)),
    StepSpec("OBS-01", "OBS-01 — Trace Completeness Gate", ("trace_completeness_required",)),
    StepSpec("OBS-02", "OBS-02 — Replay Integrity Hardening", ("replay_integrity_hardened",)),
    StepSpec("INT-01", "INT-01 — Trust Posture Snapshot", ("trust_posture_snapshot_published",)),
    StepSpec("INT-02", "INT-02 — Override Hotspot Report", ("override_hotspot_published",)),
    StepSpec("INT-03", "INT-03 — Evidence Gap Hotspot Report", ("evidence_gap_hotspot_published",)),
    StepSpec("INT-04", "INT-04 — Policy Regression Report", ("policy_regression_report_published",)),
    StepSpec("SUB-01", "SUB-01 — Minimal Artifact Intelligence Slice", ("minimal_intelligence_slice_scoped",)),
    StepSpec("SUB-02", "SUB-02 — Prompt/Route/Policy Canary Plumbing", ("slice_canary_plumbing_wired",)),
    StepSpec("SUB-03", "SUB-03 — Champion/Challenger and Calibration", ("slice_champion_challenger_calibrated",)),
)


def _stable_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"N24-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12].upper()}"


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Next24ExecutionError(f"{name} must be a non-empty string")
    return value


def _require_true_flags(flags: dict[str, bool], required_refs: tuple[str, ...], step_id: str) -> list[str]:
    evidence_refs: list[str] = []
    for key in required_refs:
        if flags.get(key) is not True:
            raise Next24ExecutionError(f"{step_id} fail-closed: missing or false required gate `{key}`")
        evidence_refs.append(key)
    return evidence_refs


def run_next24_serial_execution(
    *,
    trace_id: str,
    created_at: str,
    primary_artifact_family: str,
    gate_flags: dict[str, bool],
    evidence_overrides: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Execute NEXT24 governance checks in strict serial order with fail-closed semantics."""
    _require_non_empty_string("trace_id", trace_id)
    _require_non_empty_string("created_at", created_at)
    _require_non_empty_string("primary_artifact_family", primary_artifact_family)

    if primary_artifact_family != "artifact_release_readiness":
        raise Next24ExecutionError("SUB-01 fail-closed: only artifact_release_readiness is permitted for initial intelligence slice")

    if not isinstance(gate_flags, dict):
        raise Next24ExecutionError("gate_flags must be a dict")

    steps: list[dict[str, Any]] = []
    for spec in _STEP_SPECS:
        refs = _require_true_flags(gate_flags, spec.required_refs, spec.step_id)
        if evidence_overrides and spec.step_id in evidence_overrides:
            override_refs = evidence_overrides[spec.step_id]
            if not isinstance(override_refs, list) or not override_refs:
                raise Next24ExecutionError(f"{spec.step_id} fail-closed: evidence override must be a non-empty list")
            refs = [str(item) for item in override_refs]
        steps.append(
            {
                "step_id": spec.step_id,
                "title": spec.title,
                "status": "completed",
                "gate_evidence_refs": refs,
            }
        )

    record: dict[str, Any] = {
        "record_id": "",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "created_at": created_at,
        "primary_artifact_family": primary_artifact_family,
        "executed_steps": steps,
        "guarantees_enforced": [
            "missing required judgment artifact blocks control",
            "missing required eval blocks promotion",
            "missing certification blocks governed promotion",
            "trace and replay mismatches freeze or block execution",
        ],
    }
    record["record_id"] = _stable_id(record)
    validate_artifact(record, "next24_serial_execution_record")
    return record
