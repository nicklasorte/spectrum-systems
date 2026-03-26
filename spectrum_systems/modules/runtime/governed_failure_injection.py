"""Deterministic governed chaos/failure injection for core runtime seams.

This slice validates fail-closed behavior and audit artifact emission across
existing runtime boundaries without altering runtime policy or control logic.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.context_admission import run_context_admission
from spectrum_systems.modules.runtime.evaluation_monitor import (
    EvaluationMonitorError,
    build_monitor_record,
    run_evaluation_monitor,
)
from spectrum_systems.modules.runtime.evidence_binding import (
    EvidenceBindingError,
    EvidenceBindingPolicy,
    build_evidence_binding_record,
)
from spectrum_systems.modules.runtime.replay_engine import ReplayEngineError, run_replay
from spectrum_systems.modules.runtime.trace_engine import clear_trace_store, start_trace, validate_trace_context
from spectrum_systems.utils.artifact_envelope import build_artifact_envelope
from spectrum_systems.utils.deterministic_id import deterministic_id

SCHEMA_VERSION = "1.0.0"
ARTIFACT_TYPE = "governed_failure_injection_summary"
CASE_RESULT_ARTIFACT_TYPE = "governed_failure_injection_case_result"


class GovernedFailureInjectionError(RuntimeError):
    """Raised when case selection or summary validation fails."""


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    seam: str
    failure_mode: str
    expected_outcome: str
    fn: Callable[[], Dict[str, Any]]


def _validate(payload: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def _deterministic_timestamp(seed_payload: Dict[str, Any]) -> str:
    canonical = json.dumps(seed_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (366 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fixture(name: str) -> Dict[str, Any]:
    path = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "evaluation_monitor" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _context_bundle() -> Dict[str, Any]:
    return {
        "artifact_type": "context_bundle",
        "schema_version": "2.3.0",
        "context_id": "ctx-001",
        "context_bundle_id": "ctx-001",
        "task_type": "meeting_minutes",
        "context_items": [
            {
                "item_id": "ctxi-aaaaaaaaaaaaaaaa",
                "item_type": "input_payload",
                "content": "hello",
                "trust_level": "trusted",
                "source_classification": "user_provided",
                "provenance_refs": ["ART-001"],
                "provenance_ref": "ART-001",
            }
        ],
        "trace": {"trace_id": "trace-001", "run_id": "agent-run-001"},
        "prior_artifacts": [{"artifact_id": "ART-001", "kind": "decision"}],
        "retrieved_context": [{"artifact_id": "ART-001", "provenance": {"source_id": "ART-001"}}],
        "policy_constraints": {"required_fields": []},
        "metadata": {"source_artifact_ids": ["ART-001"]},
        "glossary": {"terms": []},
    }


def _eval_summary() -> Dict[str, Any]:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "trace-replay-001",
        "eval_run_id": "eval-run-001",
        "pass_rate": 0.95,
        "failure_rate": 0.05,
        "drift_rate": 0.01,
        "reproducibility_score": 0.92,
        "system_status": "healthy",
    }


def _decision() -> Dict[str, Any]:
    return {
        "artifact_type": "evaluation_control_decision",
        "schema_version": "1.1.0",
        "decision_id": "dec-001",
        "eval_run_id": "eval-run-001",
        "system_status": "healthy",
        "system_response": "allow",
        "triggered_signals": [],
        "threshold_snapshot": {
            "pass_rate_min": 0.8,
            "drift_rate_max": 0.2,
            "reproducibility_min": 0.85,
            "error_budget_policy_id": "ebp-001",
            "replay_governance_policy_id": "rgp-001",
            "replay_status": "consistent",
            "replay_consistency_sli": 1.0,
            "replay_governed": True,
        },
        "trace_id": "trace-replay-001",
        "created_at": "2026-01-01T00:00:00Z",
        "decision": "promote",
        "rationale_code": "all_signals_healthy",
        "input_signal_reference": {
            "signal_type": "eval_summary",
            "source_artifact_id": "eval-run-001",
        },
        "run_id": "run-001",
    }


def _enforcement() -> Dict[str, Any]:
    return {
        "artifact_type": "enforcement_result",
        "schema_version": "1.1.0",
        "enforcement_result_id": "enf-001",
        "timestamp": "2026-01-01T00:00:00Z",
        "trace_id": "trace-replay-001",
        "run_id": "run-001",
        "input_decision_reference": "dec-001",
        "enforcement_action": "allow_execution",
        "final_status": "allow",
        "rationale_code": "promote_maps_to_allow_execution",
        "fail_closed": False,
        "enforcement_path": "direct_mapping",
        "provenance": {
            "source_artifact": "evaluation_control_decision",
            "source_decision_id": "dec-001",
            "source_schema_version": "1.1.0",
        },
    }


def _case_context_missing_upstream_refs() -> Dict[str, Any]:
    result = run_context_admission(context_bundle=None, stage="observe")
    decision = result["context_admission_decision"]
    blocked = decision.get("decision_status") == "block"
    violations = [code for code in decision.get("reason_codes", []) if code == "missing_context_bundle"]
    return {
        "observed_outcome": "block" if blocked else "allow",
        "passed": blocked and bool(violations),
        "blocking_reason": "missing_context_bundle" if violations else "unexpected_context_admission_behavior",
        "invariant_violations": violations or ["expected_missing_context_bundle_not_emitted"],
        "provenance_refs": [f"context_admission_decision:{decision.get('admission_decision_id', 'missing')}"],
        "run_linkage": {
            "run_id": decision.get("trace", {}).get("run_id") or "run-chaos-context",
            "trace_id": decision.get("trace", {}).get("trace_id") or "trace-chaos-context",
        },
    }


def _case_contradictory_status_invariants() -> Dict[str, Any]:
    artifact = deepcopy(_fixture("healthy_run_1.json"))
    artifact["blocked"] = True
    artifact["regression_status"] = "pass"
    try:
        build_monitor_record(artifact)
        return {
            "observed_outcome": "open",
            "passed": False,
            "blocking_reason": "contradictory_regression_status_not_blocked",
            "invariant_violations": ["blocked_true_requires_regression_status_fail"],
            "provenance_refs": ["evaluation_monitor:build_monitor_record"],
            "run_linkage": {"run_id": artifact["run_id"], "trace_id": "trace-monitor"},
        }
    except EvaluationMonitorError as exc:
        return {
            "observed_outcome": "block",
            "passed": "blocked=true requires regression_status='fail'" in str(exc),
            "blocking_reason": str(exc),
            "invariant_violations": ["blocked_true_requires_regression_status_fail"],
            "provenance_refs": ["evaluation_monitor:build_monitor_record"],
            "run_linkage": {"run_id": artifact["run_id"], "trace_id": "trace-monitor"},
        }


def _case_malformed_digest_fields() -> Dict[str, Any]:
    artifact = deepcopy(_fixture("healthy_run_1.json"))
    artifact["results"][0]["comparison_digest"] = "bad-digest"
    try:
        build_monitor_record(artifact)
        blocked = False
        reason = "malformed_digest_accepted"
    except EvaluationMonitorError as exc:
        blocked = True
        reason = str(exc)
    return {
        "observed_outcome": "block" if blocked else "open",
        "passed": blocked,
        "blocking_reason": reason,
        "invariant_violations": ["comparison_digest_must_be_sha256_hex"],
        "provenance_refs": ["evaluation_monitor:build_monitor_record"],
        "run_linkage": {"run_id": artifact["run_id"], "trace_id": "trace-monitor"},
    }


def _case_placeholder_ids_forbidden() -> Dict[str, Any]:
    try:
        run_replay(
            _eval_summary(),
            _decision(),
            _enforcement(),
            {"trace_id": "unknown"},
        )
        blocked = False
        reason = "placeholder_trace_id_accepted"
    except ReplayEngineError as exc:
        blocked = True
        reason = str(exc)
    return {
        "observed_outcome": "block" if blocked else "open",
        "passed": blocked,
        "blocking_reason": reason,
        "invariant_violations": ["placeholder_trace_id_forbidden"],
        "provenance_refs": ["replay_engine:run_replay"],
        "run_linkage": {"run_id": "run-001", "trace_id": "unknown"},
    }


def _case_missing_trace_context() -> Dict[str, Any]:
    try:
        run_replay(_eval_summary(), _decision(), _enforcement(), {})
        blocked = False
        reason = "missing_trace_context_not_blocked"
    except ReplayEngineError as exc:
        blocked = True
        reason = str(exc)
    return {
        "observed_outcome": "block" if blocked else "open",
        "passed": blocked,
        "blocking_reason": reason,
        "invariant_violations": ["trace_context_trace_id_required"],
        "provenance_refs": ["replay_engine:run_replay"],
        "run_linkage": {"run_id": "run-001", "trace_id": "missing-trace"},
    }


def _case_required_grounded_empty_claim_candidates() -> Dict[str, Any]:
    try:
        build_evidence_binding_record(
            run_id="agent-run-001",
            trace_id="trace-001",
            final_artifact={"claims": []},
            validated_context_bundle=_context_bundle(),
            parent_multi_pass_record_id="mpg-1111111111111111",
            policy=EvidenceBindingPolicy(mode="required_grounded"),
        )
        blocked = False
        reason = "required_grounded_empty_claims_accepted"
    except EvidenceBindingError as exc:
        blocked = True
        reason = str(exc)
    return {
        "observed_outcome": "block" if blocked else "open",
        "passed": blocked,
        "blocking_reason": reason,
        "invariant_violations": ["required_grounded_requires_governable_claim_candidates"],
        "provenance_refs": ["evidence_binding:build_evidence_binding_record"],
        "run_linkage": {"run_id": "agent-run-001", "trace_id": "trace-001"},
    }


def _case_non_claim_applicable_allowed_required_grounded() -> Dict[str, Any]:
    record = build_evidence_binding_record(
        run_id="agent-run-001",
        trace_id="trace-001",
        final_artifact={"context_id": "ctx-1", "task_type": "analysis"},
        validated_context_bundle=_context_bundle(),
        parent_multi_pass_record_id="mpg-2222222222222222",
        policy=EvidenceBindingPolicy(mode="required_grounded"),
    )
    allowed = isinstance(record.get("claims"), list) and len(record["claims"]) == 0
    return {
        "observed_outcome": "allow" if allowed else "block",
        "passed": allowed,
        "blocking_reason": "non_claim_artifact_allowed" if allowed else "unexpected_non_claim_block",
        "invariant_violations": [],
        "provenance_refs": [f"evidence_binding_record:{record.get('record_id', 'missing')}"],
        "run_linkage": {"run_id": "agent-run-001", "trace_id": "trace-001"},
    }


def _case_monitor_ingestion_malformed_regression() -> Dict[str, Any]:
    malformed = {"artifact_type": "regression_result", "schema_version": "1.1.0", "run_id": "run-bad"}
    with TemporaryDirectory(prefix="chaos-monitor-") as tmp_dir:
        path = Path(tmp_dir) / "invalid_regression_result.json"
        path.write_text(json.dumps(malformed), encoding="utf-8")
        try:
            run_evaluation_monitor([path])
            blocked = False
            reason = "malformed_regression_ingestion_accepted"
        except EvaluationMonitorError as exc:
            blocked = True
            reason = str(exc)
    return {
        "observed_outcome": "block" if blocked else "open",
        "passed": blocked,
        "blocking_reason": reason,
        "invariant_violations": ["regression_result_schema_validation_required"],
        "provenance_refs": ["evaluation_monitor:run_evaluation_monitor"],
        "run_linkage": {"run_id": "run-bad", "trace_id": "trace-monitor-ingestion"},
    }


def _case_replay_lineage_chain_mismatch() -> Dict[str, Any]:
    bad_enforcement = _enforcement()
    bad_enforcement["input_decision_reference"] = "dec-other"
    try:
        run_replay(_eval_summary(), _decision(), bad_enforcement, {"trace_id": "trace-replay-001"})
        blocked = False
        reason = "replay_lineage_chain_mismatch_accepted"
    except ReplayEngineError as exc:
        blocked = True
        reason = str(exc)
    return {
        "observed_outcome": "block" if blocked else "open",
        "passed": blocked,
        "blocking_reason": reason,
        "invariant_violations": ["enforcement_input_decision_reference_must_match_decision_id"],
        "provenance_refs": ["replay_engine:_validate_replay_lineage_or_raise"],
        "run_linkage": {"run_id": "run-001", "trace_id": "trace-replay-001"},
    }


def _case_orphaned_lineage_parent_refs() -> Dict[str, Any]:
    clear_trace_store()
    trace_id = start_trace({"trace_id": "trace-chaos-orphan", "run_id": "run-chaos-orphan"})
    errors = validate_trace_context(trace_id, span_id="span-missing-parent")
    blocked = any("not found in trace" in item for item in errors)
    return {
        "observed_outcome": "block" if blocked else "open",
        "passed": blocked,
        "blocking_reason": errors[0] if errors else "orphan_span_not_detected",
        "invariant_violations": ["orphan_parent_span_refs_forbidden"],
        "provenance_refs": ["trace_engine:validate_trace_context"],
        "run_linkage": {"run_id": "run-chaos-orphan", "trace_id": trace_id},
    }


_CASES: List[CaseSpec] = [
    CaseSpec("context_missing_upstream_refs", "context_admission", "missing_required_upstream_refs", "block", _case_context_missing_upstream_refs),
    CaseSpec("monitor_contradictory_status", "evaluation_monitor", "contradictory_status_invariants", "block", _case_contradictory_status_invariants),
    CaseSpec("monitor_malformed_digest", "evaluation_monitor", "malformed_digest_fields", "block", _case_malformed_digest_fields),
    CaseSpec("replay_placeholder_ids", "replay_engine", "placeholder_ids_where_canonical_required", "block", _case_placeholder_ids_forbidden),
    CaseSpec("replay_missing_trace_context", "replay_engine", "missing_trace_context", "block", _case_missing_trace_context),
    CaseSpec("evidence_required_grounded_empty_claims", "evidence_binding", "claim_bearing_empty_governable_candidates", "block", _case_required_grounded_empty_claim_candidates),
    CaseSpec("evidence_non_claim_applicable_allowed", "evidence_binding", "non_claim_applicable_allowed_in_required_grounded", "allow", _case_non_claim_applicable_allowed_required_grounded),
    CaseSpec("monitor_ingestion_malformed_regression", "evaluation_monitor", "malformed_regression_ingestion", "block", _case_monitor_ingestion_malformed_regression),
    CaseSpec("replay_lineage_chain_mismatch", "replay_engine", "replay_lineage_chain_mismatch", "block", _case_replay_lineage_chain_mismatch),
    CaseSpec("trace_orphaned_parent_refs", "trace_engine", "orphaned_lineage_parent_refs", "block", _case_orphaned_lineage_parent_refs),
]


def list_case_ids() -> List[str]:
    return [case.case_id for case in _CASES]


def run_governed_failure_injection(
    *,
    case_filter: Optional[List[str]] = None,
    chaos_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    selected_ids = set(case_filter or list_case_ids())
    unknown = sorted(selected_ids - set(list_case_ids()))
    if unknown:
        raise GovernedFailureInjectionError(f"Unknown case id(s): {unknown}")

    selected_cases = [case for case in _CASES if case.case_id in selected_ids]
    if not selected_cases:
        raise GovernedFailureInjectionError("No failure injection cases selected")

    run_identity_payload = {
        "selected_case_ids": [case.case_id for case in selected_cases],
        "schema_version": SCHEMA_VERSION,
    }
    run_id = chaos_run_id or deterministic_id(
        prefix="gfi",
        namespace="governed_failure_injection_run",
        payload=run_identity_payload,
    )

    results: List[Dict[str, Any]] = []
    for case in selected_cases:
        outcome = case.fn()
        case_identity = {
            "run_id": run_id,
            "case_id": case.case_id,
            "seam": case.seam,
            "failure_mode": case.failure_mode,
            "expected_outcome": case.expected_outcome,
            "observed_outcome": outcome["observed_outcome"],
            "blocking_reason": outcome["blocking_reason"],
            "invariant_violations": sorted(set(outcome.get("invariant_violations") or [])),
        }
        case_result = {
            "artifact_type": CASE_RESULT_ARTIFACT_TYPE,
            "schema_version": SCHEMA_VERSION,
            "artifact_id": deterministic_id(
                prefix="gficr",
                namespace="governed_failure_injection_case",
                payload=case_identity,
            ),
            "trace_refs": {
                "primary": outcome["run_linkage"]["trace_id"],
                "related": [run_id],
            },
            "run_linkage": {
                "run_id": outcome["run_linkage"]["run_id"],
                "trace_id": outcome["run_linkage"]["trace_id"],
            },
            "injection_case_id": case.case_id,
            "seam": case.seam,
            "failure_mode": case.failure_mode,
            "expected_outcome": case.expected_outcome,
            "observed_outcome": outcome["observed_outcome"],
            "passed": bool(outcome["passed"]),
            "blocking_reason": outcome["blocking_reason"],
            "invariant_violations": sorted(set(outcome.get("invariant_violations") or [])),
            "provenance_refs": sorted(set(outcome.get("provenance_refs") or [])),
            "created_at": _deterministic_timestamp(case_identity),
        }
        results.append(case_result)

    pass_count = sum(1 for item in results if item["passed"])
    fail_count = len(results) - pass_count
    envelope = build_artifact_envelope(
        artifact_id=run_id,
        timestamp=_deterministic_timestamp({"run_id": run_id, "kind": "summary"}),
        schema_version=SCHEMA_VERSION,
        primary_trace_ref=run_id,
        related_trace_refs=[item["trace_refs"]["primary"] for item in results],
    )
    summary = {
        "artifact_type": ARTIFACT_TYPE,
        **envelope,
        "chaos_run_id": run_id,
        "case_count": len(results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "results": results,
    }
    _validate(summary, "governed_failure_injection_summary")
    return summary


def write_summary(output_dir: Path, summary: Dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "governed_failure_injection_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


__all__ = [
    "GovernedFailureInjectionError",
    "list_case_ids",
    "run_governed_failure_injection",
    "write_summary",
]
