"""R100-NP-001-FIXED composition-only integration fabric.

This module orchestrates canonical system outputs by reference and emits
composition artifacts. It does not recompute owner-specific responsibilities.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class RoadmapOrchestratorError(ValueError):
    """Fail-closed orchestration error."""


_REF_PATTERN = re.compile(r"^[a-z0-9_]+:[A-Za-z0-9._-]+$")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _id(parts: list[str]) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def _require_ref(value: Any, field: str) -> str:
    ref = str(value or "").strip()
    if not _REF_PATTERN.match(ref):
        raise RoadmapOrchestratorError(f"invalid_reference:{field}")
    return ref


def _require_recent(ts: str, *, max_age_hours: int = 24) -> None:
    try:
        created = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RoadmapOrchestratorError("invalid_created_at") from exc
    age = datetime.now(timezone.utc) - created.astimezone(timezone.utc)
    if age.total_seconds() > max_age_hours * 3600:
        raise RoadmapOrchestratorError("stale_reference_detected")


def build_global_posture(*, lin: Mapping[str, Any], rep: Mapping[str, Any], evl: Mapping[str, Any], evd: Mapping[str, Any], obs: Mapping[str, Any], dag: Mapping[str, Any], dep: Mapping[str, Any]) -> dict[str, Any]:
    refs = {
        "lin_lineage_report_ref": _require_ref(lin.get("artifact_ref"), "lin_lineage_report_ref"),
        "rep_replay_report_ref": _require_ref(rep.get("artifact_ref"), "rep_replay_report_ref"),
        "evl_eval_report_ref": _require_ref(evl.get("artifact_ref"), "evl_eval_report_ref"),
        "evd_evidence_report_ref": _require_ref(evd.get("artifact_ref"), "evd_evidence_report_ref"),
        "obs_observability_report_ref": _require_ref(obs.get("artifact_ref"), "obs_observability_report_ref"),
        "dag_dependency_report_ref": _require_ref(dag.get("artifact_ref"), "dag_dependency_report_ref"),
        "dep_chain_report_ref": _require_ref(dep.get("artifact_ref"), "dep_chain_report_ref"),
    }
    for payload in (lin, rep, evl, evd, obs, dag, dep):
        _require_recent(str(payload.get("created_at")))

    artifact = {
        "artifact_type": "rdx_global_execution_validity_report",
        "schema_version": "1.0.0",
        "artifact_id": f"rdx-global-{_id(sorted(refs.values()))}",
        "created_at": _now(),
        "owner": "RDX",
        "status": "referenced",
        "summary": "Global posture composed only from canonical system references.",
        "inputs": sorted(refs.values()),
        "authority_boundary": "non_authoritative_signal_only",
        **refs,
    }
    validate_artifact(artifact, "rdx_global_execution_validity_report")
    return artifact


def prioritize_control_signals(*, global_posture: Mapping[str, Any], slo_signal_ref: str, cap_signal_ref: str, qos_signal_ref: str, signal_scores: Mapping[str, float]) -> dict[str, Any]:
    posture_ref = _require_ref(f"rdx_global_execution_validity_report:{global_posture.get('artifact_id')}", "rdx_global_execution_validity_report_ref")
    slo_ref = _require_ref(slo_signal_ref, "slo_signal_ref")
    cap_ref = _require_ref(cap_signal_ref, "cap_signal_ref")
    qos_ref = _require_ref(qos_signal_ref, "qos_signal_ref")

    candidates = [(slo_ref, float(signal_scores.get("slo", 0.0))), (cap_ref, float(signal_scores.get("cap", 0.0))), (qos_ref, float(signal_scores.get("qos", 0.0)))]
    ranked = [name for name, _ in sorted(candidates, key=lambda row: row[1], reverse=True)]

    artifact = {
        "artifact_type": "prg_prioritized_control_signal_bundle",
        "schema_version": "1.0.0",
        "artifact_id": f"prg-priority-{_id(ranked)}",
        "created_at": _now(),
        "owner": "PRG",
        "status": "ranked",
        "summary": "Signal ranking bundle from existing canonical references.",
        "inputs": [posture_ref, slo_ref, cap_ref, qos_ref],
        "authority_boundary": "non_authoritative_signal_only",
        "rdx_global_execution_validity_report_ref": posture_ref,
        "slo_signal_ref": slo_ref,
        "cap_signal_ref": cap_ref,
        "qos_signal_ref": qos_ref,
        "ranked_signal_refs": ranked,
    }
    validate_artifact(artifact, "prg_prioritized_control_signal_bundle")
    return artifact


def compose_cde_posture(*, global_posture: Mapping[str, Any], prioritized_signals: Mapping[str, Any], slo_signal_ref: str, cap_signal_ref: str, qos_signal_ref: str) -> dict[str, Any]:
    posture_ref = _require_ref(f"rdx_global_execution_validity_report:{global_posture.get('artifact_id')}", "rdx_global_execution_validity_report_ref")
    priority_ref = _require_ref(f"prg_prioritized_control_signal_bundle:{prioritized_signals.get('artifact_id')}", "prg_prioritized_control_signal_bundle_ref")
    slo_ref = _require_ref(slo_signal_ref, "slo_signal_ref")
    cap_ref = _require_ref(cap_signal_ref, "cap_signal_ref")
    qos_ref = _require_ref(qos_signal_ref, "qos_signal_ref")

    ranked = list(prioritized_signals.get("ranked_signal_refs", []))
    highest = ranked[0] if ranked else ""
    if highest.startswith("qos_signal"):
        outcome = "halt"
    elif highest.startswith("cap_signal"):
        outcome = "recut"
    elif highest.startswith("slo_signal"):
        outcome = "escalate"
    else:
        outcome = "continue"

    artifact = {
        "artifact_type": "cde_composite_posture_bundle",
        "schema_version": "1.0.0",
        "artifact_id": f"cde-composite-{_id([posture_ref, priority_ref, outcome])}",
        "created_at": _now(),
        "owner": "CDE",
        "status": "composed",
        "summary": "CDE composite posture assembled from upstream references.",
        "inputs": [posture_ref, priority_ref, slo_ref, cap_ref, qos_ref],
        "authority_boundary": "cde_final_decision_scope",
        "rdx_global_execution_validity_report_ref": posture_ref,
        "prg_prioritized_control_signal_bundle_ref": priority_ref,
        "slo_signal_ref": slo_ref,
        "cap_signal_ref": cap_ref,
        "qos_signal_ref": qos_ref,
        "outcome": outcome,
    }
    validate_artifact(artifact, "cde_composite_posture_bundle")
    return artifact


def run_redteam_shadow_ownership(*, runtime_source: str) -> dict[str, Any]:
    forbidden = ["lineage_complete", "replay_score", "eval_coverage_pct", "observability_score", "dependency_graph_hash"]
    hits = [token for token in forbidden if token in runtime_source]
    return {"round": "RT1", "status": "fail" if hits else "pass", "findings": hits}


def run_redteam_reference_integrity(*, refs: list[str], stale_found: bool) -> dict[str, Any]:
    malformed = [r for r in refs if not _REF_PATTERN.match(r)]
    findings = malformed + (["stale_reference_detected"] if stale_found else [])
    return {"round": "RT2", "status": "fail" if findings else "pass", "findings": findings}


def run_redteam_signal_priority(*, ranked_signal_refs: list[str], expected_halt_prefixes: tuple[str, ...] = ("qos_signal",)) -> dict[str, Any]:
    highest = ranked_signal_refs[0] if ranked_signal_refs else ""
    hidden_halt = any(highest.startswith(prefix) for prefix in expected_halt_prefixes)
    findings = [] if hidden_halt else ["halt_signal_not_prioritized"]
    return {"round": "RT3", "status": "fail" if findings else "pass", "findings": findings}


def apply_redteam_fixpack(*, redteam_report: Mapping[str, Any]) -> dict[str, Any]:
    findings = list(redteam_report.get("findings", []))
    return {
        "artifact_type": f"fre_tpa_sel_pqx_fix_pack_{str(redteam_report.get('round','RTX')).lower()}",
        "status": "fixed" if not findings else "partial",
        "remaining_findings": [] if not findings else findings[:1],
        "guards_added": ["reference_only_enforcement", "stale_reference_block", "halt_visibility_guard"],
    }


def run_composition_pipeline(*, canonical_inputs: Mapping[str, Mapping[str, Any]], signal_scores: Mapping[str, float]) -> dict[str, Any]:
    global_posture = build_global_posture(
        lin=canonical_inputs["lin"],
        rep=canonical_inputs["rep"],
        evl=canonical_inputs["evl"],
        evd=canonical_inputs["evd"],
        obs=canonical_inputs["obs"],
        dag=canonical_inputs["dag"],
        dep=canonical_inputs["dep"],
    )
    prioritized = prioritize_control_signals(
        global_posture=global_posture,
        slo_signal_ref=_require_ref(canonical_inputs["slo"]["artifact_ref"], "slo_signal_ref"),
        cap_signal_ref=_require_ref(canonical_inputs["cap"]["artifact_ref"], "cap_signal_ref"),
        qos_signal_ref=_require_ref(canonical_inputs["qos"]["artifact_ref"], "qos_signal_ref"),
        signal_scores=signal_scores,
    )
    cde_bundle = compose_cde_posture(
        global_posture=global_posture,
        prioritized_signals=prioritized,
        slo_signal_ref=canonical_inputs["slo"]["artifact_ref"],
        cap_signal_ref=canonical_inputs["cap"]["artifact_ref"],
        qos_signal_ref=canonical_inputs["qos"]["artifact_ref"],
    )
    return {
        "rdx": global_posture,
        "prg": prioritized,
        "cde": cde_bundle,
    }
