"""Governed context foundation flow (AEX -> TLC -> TPA -> PQX) with ownership-clean seams."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.repo_write_lineage_guard import RepoWriteLineageGuardError, validate_repo_write_lineage
from spectrum_systems.modules.runtime.top_level_conductor import _build_tlc_handoff_record


class ContextGovernedFlowError(ValueError):
    """Raised when governed context flow invariants are violated."""


def _canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _require_mapping(payload: Any, field: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ContextGovernedFlowError(f"{field}_required")
    return dict(payload)


def create_tlc_context_handoff(
    *,
    run_id: str,
    objective: str,
    branch_ref: str,
    emitted_at: str,
    build_admission_record: Mapping[str, Any],
    normalized_execution_request: Mapping[str, Any],
) -> dict[str, Any]:
    """TLC-owned routing artifact creation for admitted context-capability repo writes."""
    admission = _require_mapping(build_admission_record, "build_admission_record")
    normalized = _require_mapping(normalized_execution_request, "normalized_execution_request")

    reason_codes = [str(code) for code in admission.get("reason_codes") or []]
    if "context_capability_repo_mutation" not in reason_codes:
        raise ContextGovernedFlowError("context_capability_not_admitted")

    handoff = _build_tlc_handoff_record(
        run_id=run_id,
        objective=objective,
        branch_ref=branch_ref,
        emitted_at=emitted_at,
        repo_write_lineage={
            "trace_id": str(admission.get("trace_id") or ""),
            "request_id": str(normalized.get("request_id") or ""),
            "admission_id": str(admission.get("admission_id") or ""),
            "normalized_execution_request_ref": str(admission.get("normalized_execution_request_ref") or ""),
        },
    )
    validate_artifact(handoff, "tlc_handoff_record")
    return handoff


def route_context_slice_to_tpa(
    *,
    build_admission_record: Mapping[str, Any],
    normalized_execution_request: Mapping[str, Any],
    tlc_handoff_record: Mapping[str, Any],
) -> dict[str, Any]:
    """TLC routing only: validates lineage continuity and routes to TPA."""
    admission = _require_mapping(build_admission_record, "build_admission_record")
    normalized = _require_mapping(normalized_execution_request, "normalized_execution_request")
    handoff = _require_mapping(tlc_handoff_record, "tlc_handoff_record")
    try:
        validate_repo_write_lineage(
            build_admission_record=admission,
            normalized_execution_request=normalized,
            tlc_handoff_record=handoff,
            expected_trace_id=str(admission.get("trace_id") or ""),
            enforce_replay_protection=False,
        )
    except RepoWriteLineageGuardError as exc:
        raise ContextGovernedFlowError(f"lineage_invalid:{exc}") from exc

    return {
        "route_status": "accepted",
        "next_system": "TPA",
        "tlc_handoff_record": handoff,
        "trace_id": str(handoff.get("trace_id") or ""),
    }


def evaluate_tpa_context_admissibility(
    *,
    normalized_execution_request: Mapping[str, Any],
    tlc_handoff_record: Mapping[str, Any],
    context_recipe_spec: Mapping[str, Any],
    source_metadata: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """TPA-owned deterministic context admissibility checks (no execution)."""
    normalized = _require_mapping(normalized_execution_request, "normalized_execution_request")
    handoff = _require_mapping(tlc_handoff_record, "tlc_handoff_record")
    recipe = _require_mapping(context_recipe_spec, "context_recipe_spec")

    required_source_types = set(str(v) for v in recipe.get("required_source_types") or [])
    ttl_seconds = int(((recipe.get("freshness_rules") or {}).get("ttl_seconds") or 0))
    allow_stale = bool(((recipe.get("freshness_rules") or {}).get("allow_stale") is True))
    max_sources = int(((recipe.get("source_requirements") or {}).get("max_sources") or 0))

    reasons: list[str] = []
    admitted_sources: list[dict[str, Any]] = []
    for source in source_metadata:
        src = dict(source)
        source_type = str(src.get("source_type") or "")
        source_schema_ref = str(src.get("source_schema_ref") or "")
        trust_class = str(src.get("trust_class") or "")
        freshness_seconds = int(src.get("freshness_age_seconds") or 0)
        classification = str(src.get("classification") or "")

        source_reasons: list[str] = []
        if source_type not in required_source_types:
            source_reasons.append("source_type_not_allowed")
        if not source_schema_ref:
            source_reasons.append("source_schema_ref_missing")
        if freshness_seconds > ttl_seconds and not allow_stale:
            source_reasons.append("source_stale")
        if trust_class not in {"trusted", "restricted"}:
            source_reasons.append("trust_class_rejected")
        if classification in {"restricted"}:
            source_reasons.append("classification_rejected")

        if source_reasons:
            reasons.extend(source_reasons)
            continue
        admitted_sources.append(src)

    if len(source_metadata) > max_sources:
        reasons.append("scope_over_budget")
    for key in ("trace_id", "run_id"):
        if not str((handoff.get("tlc_run_context") or {}).get("run_id") or "") and key == "run_id":
            reasons.append("missing_trace_or_lineage")
        if not str(handoff.get("trace_id") or "") and key == "trace_id":
            reasons.append("missing_trace_or_lineage")

    reasons = sorted(set(reasons))
    allowed = len(reasons) == 0

    tpa_scope_policy = {
        "policy_id": f"tpa-scope-{str(recipe.get('recipe_id') or 'context')}",
        "allow": allowed,
        "reason_codes": reasons,
        "max_sources": max_sources,
        "ttl_seconds": ttl_seconds,
    }
    tpa_slice_artifact = {
        "artifact_type": "tpa_slice_artifact",
        "artifact_id": f"tpa-slice-{_canonical_hash({'trace': handoff.get('trace_id'), 'recipe': recipe.get('recipe_id')})[:12]}",
        "trace_id": str(handoff.get("trace_id") or ""),
        "run_id": str((handoff.get("tlc_run_context") or {}).get("run_id") or ""),
        "decision": "allow" if allowed else "deny",
        "reason_codes": reasons,
        "approved_source_refs": sorted(str(src.get("source_ref") or "") for src in admitted_sources),
        "lineage": {
            "normalized_execution_request_ref": str(handoff.get("normalized_execution_request_ref") or ""),
            "tlc_handoff_ref": f"tlc_handoff_record:{handoff.get('handoff_id')}",
        },
    }
    tpa_observability_summary = {
        "artifact_type": "tpa_observability_summary",
        "trace_id": str(handoff.get("trace_id") or ""),
        "run_id": str((handoff.get("tlc_run_context") or {}).get("run_id") or ""),
        "admitted_source_count": len(admitted_sources),
        "rejected_reason_codes": reasons,
    }
    return {
        "tpa_scope_policy": tpa_scope_policy,
        "tpa_slice_artifact": tpa_slice_artifact,
        "tpa_observability_summary": tpa_observability_summary,
    }


def execute_bounded_context_assembly(
    *,
    build_admission_record: Mapping[str, Any],
    normalized_execution_request: Mapping[str, Any],
    tlc_handoff_record: Mapping[str, Any],
    tpa_slice_artifact: Mapping[str, Any],
    context_recipe_spec: Mapping[str, Any],
    approved_sources: list[Mapping[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    """PQX-owned bounded context assembly; fail-closed on missing AEX/TLC/TPA lineage."""
    admission = _require_mapping(build_admission_record, "build_admission_record")
    normalized = _require_mapping(normalized_execution_request, "normalized_execution_request")
    handoff = _require_mapping(tlc_handoff_record, "tlc_handoff_record")
    tpa_slice = _require_mapping(tpa_slice_artifact, "tpa_slice_artifact")
    recipe = _require_mapping(context_recipe_spec, "context_recipe_spec")

    try:
        lineage = validate_repo_write_lineage(
            build_admission_record=admission,
            normalized_execution_request=normalized,
            tlc_handoff_record=handoff,
            expected_trace_id=str(admission.get("trace_id") or ""),
            enforce_replay_protection=False,
        )
    except RepoWriteLineageGuardError as exc:
        raise ContextGovernedFlowError(f"repo_write_lineage_missing_or_invalid:{exc}") from exc

    if str(tpa_slice.get("decision") or "") != "allow":
        raise ContextGovernedFlowError("missing_or_denied_tpa_slice_artifact")

    approved_refs = sorted(str(src.get("source_ref") or "") for src in approved_sources)
    source_digest = _canonical_hash([dict(src) for src in sorted(approved_sources, key=lambda x: str(x.get("source_ref") or ""))])
    bundle_id = f"ctxbundle-{_canonical_hash({'trace_id': lineage['trace_id'], 'request_id': lineage['request_id'], 'source_digest': source_digest})[:16]}"
    bundle_manifest_hash = f"sha256:{_canonical_hash({'bundle_id': bundle_id, 'sources': approved_refs, 'recipe': recipe})}"

    context_bundle_record = {
        "artifact_kind": "context_bundle_record",
        "artifact_id": f"ctxbrec-{bundle_id}",
        "created_at": created_at,
        "schema_ref": "contracts/schemas/context_bundle_record.schema.json",
        "trace": {
            "trace_id": lineage["trace_id"],
            "run_id": str((handoff.get("tlc_run_context") or {}).get("run_id") or ""),
        },
        "bundle_id": bundle_id,
        "recipe_id": str(recipe.get("recipe_id") or ""),
        "recipe_version": str(recipe.get("recipe_version") or ""),
        "bundle_manifest_hash": bundle_manifest_hash,
        "source_refs": approved_refs,
        "provenance_summary": {
            "source_count": len(approved_refs),
            "provenance_refs": approved_refs,
        },
        "trust_summary": {
            "min_trust_class": "trusted",
            "blocked_source_count": 0,
            "policy_ref": str((tpa_slice.get("lineage") or {}).get("tlc_handoff_ref") or "policy:tpa:missing"),
        },
        "admissibility_status": "approved",
        "assembly_budget": {
            "max_sources": int(((recipe.get("source_requirements") or {}).get("max_sources") or len(approved_refs) or 1)),
            "max_tokens": int(((recipe.get("budget_policy") or {}).get("max_tokens") or 4096)),
            "consumed_sources": len(approved_refs),
            "consumed_tokens": min(4096, 256 * len(approved_refs)),
        },
        "lineage": {
            "aex_admission_ref": f"build_admission_record:{lineage['admission_id']}",
            "normalized_request_ref": lineage["normalized_execution_request_ref"],
            "tlc_handoff_ref": f"tlc_handoff_record:{handoff.get('handoff_id')}",
            "tpa_slice_ref": f"tpa_slice_artifact:{tpa_slice.get('artifact_id')}",
        },
    }
    validate_artifact(context_bundle_record, "context_bundle_record")

    pqx_slice_execution_record = {
        "artifact_type": "pqx_slice_execution_record",
        "run_id": str((handoff.get("tlc_run_context") or {}).get("run_id") or ""),
        "trace_id": lineage["trace_id"],
        "step_id": "CTX-06",
        "status": "completed",
        "bundle_ref": f"context_bundle_record:{context_bundle_record['artifact_id']}",
    }
    pqx_bundle_execution_record = {
        "artifact_type": "pqx_bundle_execution_record",
        "bundle_execution_id": f"pqxbundle-{bundle_id}",
        "bundle_id": bundle_id,
        "run_id": str((handoff.get("tlc_run_context") or {}).get("run_id") or ""),
        "status": "completed",
        "output_artifact_refs": [f"context_bundle_record:{context_bundle_record['artifact_id']}"],
    }
    pqx_execution_closure_record = {
        "artifact_type": "pqx_execution_closure_record",
        "closure_id": _canonical_hash({"bundle_id": bundle_id, "trace_id": lineage["trace_id"]}),
        "run_id": str((handoff.get("tlc_run_context") or {}).get("run_id") or ""),
        "trace_id": lineage["trace_id"],
        "status": "closed",
    }

    return {
        "context_bundle_record": context_bundle_record,
        "pqx_slice_execution_record": pqx_slice_execution_record,
        "pqx_bundle_execution_record": pqx_bundle_execution_record,
        "pqx_execution_closure_record": pqx_execution_closure_record,
    }


__all__ = [
    "ContextGovernedFlowError",
    "create_tlc_context_handoff",
    "route_context_slice_to_tpa",
    "evaluate_tpa_context_admissibility",
    "execute_bounded_context_assembly",
]
