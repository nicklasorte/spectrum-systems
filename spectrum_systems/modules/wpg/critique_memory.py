from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List

from spectrum_systems.modules.wpg.common import StageContext, WPGError, control_decision_from_eval, ensure_contract, make_eval_artifacts, normalize_text_tokens


def ingest_comment_matrix_signal(comment_matrix_artifact: Dict[str, Any], ctx: StageContext) -> Dict[str, Any]:
    rows = comment_matrix_artifact.get("outputs", {}).get("rows")
    if not isinstance(rows, list):
        rows = comment_matrix_artifact.get("entries")
    if not isinstance(rows, list):
        raise WPGError("malformed matrix: rows must be present")

    signals: List[Dict[str, Any]] = []
    malformed_count = 0
    for row in rows:
        if not isinstance(row, dict):
            malformed_count += 1
            continue
        normalized = {
            "issue_class": row.get("issue_class") or row.get("resolution_status") or "general",
            "stakeholder": row.get("stakeholder") or row.get("validated_by", {}).get("role") or "unassigned",
            "section_type": row.get("section_type") or "general",
            "resolution_pattern": row.get("resolution_pattern") or row.get("response_text") or "manual_resolution",
            "severity": row.get("severity") or ("high" if row.get("resolution_status") in {"blocked", "rejected"} else "medium"),
        }
        required = ["issue_class", "stakeholder", "section_type", "resolution_pattern", "severity"]
        if any(not normalized.get(field) for field in required):
            malformed_count += 1
            continue
        signals.append({key: str(normalized[key]) for key in required})

    checks = [
        {"description": "matrix rows parse", "passed": malformed_count == 0, "failure_mode": "malformed_matrix"},
        {"description": "signals extracted", "passed": len(signals) > 0, "failure_mode": "empty_signal_set"},
    ]
    eval_pack = make_eval_artifacts("comment_matrix_ingestion", checks, ctx)
    control = control_decision_from_eval(stage="comment_matrix_ingestion", eval_summary=eval_pack["eval_summary"])
    if malformed_count > 0:
        control["decision"] = "BLOCK"
        control["reasons"] = sorted(set(control.get("reasons", []) + ["malformed_matrix"]))
        control["enforcement"] = {"action": "trigger_repair"}

    artifact = {
        "artifact_type": "comment_matrix_signal_artifact",
        "schema_version": "1.0.0",
        "trace_id": ctx.trace_id,
        "outputs": {
            "signal_count": len(signals),
            "malformed_count": malformed_count,
            "signals": signals,
        },
        "evaluation_refs": {**eval_pack, "control_decision": control},
    }
    return ensure_contract(artifact, "comment_matrix_signal_artifact")


def build_agency_critique_profile(signal_artifact: Dict[str, Any], ctx: StageContext) -> Dict[str, Any]:
    signals = signal_artifact.get("outputs", {}).get("signals", [])
    per_agency: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in signals:
        agency = str(row.get("stakeholder", "unknown"))
        pattern = str(row.get("resolution_pattern", "unknown"))
        per_agency[agency][pattern] += 1

    profiles = []
    for agency, counts in sorted(per_agency.items()):
        recurring = [name for name, value in counts.items() if value >= 1]
        profiles.append({"agency": agency, "recurring_objections": recurring, "top_resolution_pattern": counts.most_common(1)[0][0]})

    eval_pack = make_eval_artifacts("agency_critique_profile", [{"description": "agency profiles present", "passed": len(profiles) > 0, "failure_mode": "missing_agency_profiles"}], ctx)
    control = control_decision_from_eval(stage="agency_critique_profile", eval_summary=eval_pack["eval_summary"])
    return ensure_contract(
        {
            "artifact_type": "agency_critique_profile",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "outputs": {"profiles": profiles},
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "agency_critique_profile",
    )


def build_industry_critique_profile(signal_artifact: Dict[str, Any], ctx: StageContext) -> Dict[str, Any]:
    signals = signal_artifact.get("outputs", {}).get("signals", [])
    themes = {"deployment": 0, "ambiguity": 0, "burden": 0}
    for row in signals:
        tokens = normalize_text_tokens(" ".join([str(row.get("issue_class", "")), str(row.get("resolution_pattern", ""))]))
        if {"deploy", "deployment", "release"} & tokens:
            themes["deployment"] += 1
        if {"ambiguity", "ambiguous", "unclear"} & tokens:
            themes["ambiguity"] += 1
        if {"burden", "cost", "compliance"} & tokens:
            themes["burden"] += 1

    objections = [{"theme": key, "count": value} for key, value in themes.items()]
    eval_pack = make_eval_artifacts("industry_critique_profile", [{"description": "industry objections emitted", "passed": True, "failure_mode": "missing_industry_objections"}], ctx)
    control = control_decision_from_eval(stage="industry_critique_profile", eval_summary=eval_pack["eval_summary"])
    return ensure_contract(
        {
            "artifact_type": "industry_critique_profile",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "outputs": {"objections": objections},
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "industry_critique_profile",
    )


def retrieve_critique_memory(
    signal_artifact: Dict[str, Any],
    *,
    trace_id: str,
    band: str,
    topic: str,
    stakeholder: str,
    section_type: str,
) -> Dict[str, Any]:
    signals = signal_artifact.get("outputs", {}).get("signals", [])
    evidence = [
        row
        for row in signals
        if row.get("stakeholder") == stakeholder and row.get("section_type") == section_type
    ]
    decision = "WARN" if not evidence else "ALLOW"
    artifact = {
        "artifact_type": "critique_retrieval_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "query": {
            "band": band,
            "topic": topic,
            "stakeholder": stakeholder,
            "section_type": section_type,
        },
        "evidence": evidence,
        "evaluation_refs": {
            "control_decision": {
                "stage": "critique_retrieval",
                "decision": decision,
                "reasons": ["no_evidence"] if not evidence else ["evidence_found"],
                "enforcement": {"action": "annotate" if decision == "WARN" else "proceed"},
            }
        },
    }
    return ensure_contract(artifact, "critique_retrieval_record")


def index_signals_by_topic(signals: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        index[str(signal.get("issue_class", "unknown"))].append(dict(signal))
    return dict(index)
