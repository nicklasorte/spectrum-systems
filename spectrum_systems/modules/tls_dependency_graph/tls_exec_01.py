"""TLS-EXEC-01 deterministic five-phase operationalization pipeline.

Primary type: BUILD

Pipeline:
- TLS-05 ranking red-team review
- TLS-06 scoring fix loop (score-logic only)
- TLS-07 action layer generation
- TLS-08 owner-input packet artifacts (TLS -> CDE -> SEL)
- TLS-09 learning + weight update artifacts

Fail-closed behavior: any phase failure raises ``TlsExecutionFailure`` and halts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


class TlsExecutionFailure(RuntimeError):
    """Raised when a phase cannot complete in fail-closed mode."""


REQUIRED_PRIORITY_KEYS = {"ranked_systems", "requested_candidate_ranking", "top_5"}
ACTIVE_CLASSES = {"active_system", "h_slice"}


@dataclass(frozen=True)
class AdjustmentWeights:
    dependency_order_penalty: int = 20
    missing_dependency_penalty: int = 10
    weak_explanation_penalty: int = 5


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise TlsExecutionFailure(f"missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _index_rank(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    return {row["system_id"]: int(row["rank"]) for row in rows}


def _find_misranked_systems(priority: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = priority.get("ranked_systems") or []
    rank_by_id = _index_rank(rows)
    class_by_id = {row["system_id"]: row.get("classification") for row in rows}
    findings: List[Dict[str, Any]] = []
    for row in rows:
        sid = row["system_id"]
        upstream = (row.get("dependencies") or {}).get("upstream") or []
        violating = [
            upstream_sid
            for upstream_sid in upstream
            if class_by_id.get(upstream_sid) in ACTIVE_CLASSES
            and rank_by_id.get(upstream_sid, 10**9) > rank_by_id.get(sid, 10**9)
        ]
        if violating:
            findings.append(
                {
                    "system_id": sid,
                    "rank": row["rank"],
                    "upstream_rank_violations": sorted(violating),
                    "explanation": "active upstream dependency ranked after dependent system",
                }
            )
    return sorted(findings, key=lambda item: (item["rank"], item["system_id"]))


def _find_missing_dependencies(priority: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = priority.get("ranked_systems") or []
    row_by_id = {row["system_id"]: row for row in rows}
    findings: List[Dict[str, Any]] = []
    for row in rows:
        sid = row["system_id"]
        deps = row.get("dependencies") or {}
        upstream = deps.get("upstream") or []
        downstream = deps.get("downstream") or []

        missing_upstream = []
        for up in upstream:
            peer = row_by_id.get(up)
            peer_downstream = ((peer or {}).get("dependencies") or {}).get("downstream") or []
            if sid not in peer_downstream:
                missing_upstream.append(up)

        missing_downstream = []
        for down in downstream:
            peer = row_by_id.get(down)
            peer_upstream = ((peer or {}).get("dependencies") or {}).get("upstream") or []
            if sid not in peer_upstream:
                missing_downstream.append(down)

        if missing_upstream or missing_downstream:
            findings.append(
                {
                    "system_id": sid,
                    "missing_upstream_backrefs": sorted(missing_upstream),
                    "missing_downstream_backrefs": sorted(missing_downstream),
                    "explanation": "dependency link not mirrored in peer dependency set",
                }
            )
    return sorted(findings, key=lambda item: item["system_id"])


def _find_premature_build_candidates(priority: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for row in priority.get("requested_candidate_ranking") or []:
        sid = row.get("system_id", "")
        assessment = row.get("build_now_assessment")
        if assessment in {"blocked_signal", "prerequisite_signal", "caution_signal"}:
            findings.append(
                {
                    "system_id": sid,
                    "build_now_assessment": assessment,
                    "safe_next_action": row.get("safe_next_action", ""),
                    "prerequisite_systems": sorted(row.get("prerequisite_systems") or []),
                    "explanation": "candidate should not proceed to execution until trust conditions are cleared",
                }
            )
    return sorted(findings, key=lambda item: item["system_id"])


def _find_weak_explanations(priority: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for row in priority.get("ranked_systems") or []:
        why_now = (row.get("why_now") or "").strip()
        if len(why_now) < 35 or "no immediate priority signal" in why_now:
            findings.append(
                {
                    "system_id": row["system_id"],
                    "why_now": why_now,
                    "explanation": "explanation quality is too weak for deterministic review traceability",
                }
            )
    return sorted(findings, key=lambda item: item["system_id"])


def phase_1_ranking_review(priority: Dict[str, Any]) -> Dict[str, Any]:
    missing = sorted(REQUIRED_PRIORITY_KEYS - set(priority))
    if missing:
        raise TlsExecutionFailure(f"priority report missing required keys: {missing}")

    misranked = _find_misranked_systems(priority)
    missing_dependencies = _find_missing_dependencies(priority)
    premature = _find_premature_build_candidates(priority)
    weak = _find_weak_explanations(priority)

    return {
        "schema_version": "tls-05.v1",
        "phase": "TLS-05",
        "deterministic": True,
        "review_findings": {
            "misranked_systems": misranked,
            "missing_dependencies": missing_dependencies,
            "premature_build_candidates": premature,
            "weak_explanations": weak,
        },
        "summary": {
            "misranked_count": len(misranked),
            "missing_dependency_count": len(missing_dependencies),
            "premature_build_count": len(premature),
            "weak_explanation_count": len(weak),
            "status": "needs_fix" if (misranked or missing_dependencies or weak) else "stable",
        },
    }


def _sort_ranked_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(row: Dict[str, Any]) -> Tuple[Any, ...]:
        spine_idx = int(row.get("spine_position_index", 10**6))
        return (-int(row["score"]), spine_idx, row["system_id"])

    out = sorted(rows, key=key)
    for i, row in enumerate(out, start=1):
        row["rank"] = i
    return out


def phase_2_fix_loop(
    priority: Dict[str, Any],
    review: Dict[str, Any],
    weights: AdjustmentWeights = AdjustmentWeights(),
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    rows = [dict(row) for row in (priority.get("ranked_systems") or [])]
    if not rows:
        raise TlsExecutionFailure("priority report has no ranked_systems")

    misranked_ids = {item["system_id"]: item for item in review["review_findings"]["misranked_systems"]}
    missing_dep_ids = {item["system_id"]: item for item in review["review_findings"]["missing_dependencies"]}
    weak_ids = {item["system_id"]: item for item in review["review_findings"]["weak_explanations"]}

    adjustment_log_rows: List[Dict[str, Any]] = []
    for row in rows:
        sid = row["system_id"]
        base_score = int(row.get("base_score", row["score"]))
        adjustments: List[Dict[str, Any]] = []

        if sid in misranked_ids:
            count = len(misranked_ids[sid]["upstream_rank_violations"])
            delta = -(weights.dependency_order_penalty * count)
            adjustments.append({"reason": "dependency_order_violation", "delta": delta})

        if sid in missing_dep_ids:
            miss = missing_dep_ids[sid]
            count = len(miss["missing_upstream_backrefs"]) + len(miss["missing_downstream_backrefs"])
            delta = -(weights.missing_dependency_penalty * count)
            adjustments.append({"reason": "missing_dependency_backrefs", "delta": delta})

        if sid in weak_ids:
            adjustments.append({"reason": "weak_explanation", "delta": -weights.weak_explanation_penalty})

        total_delta = sum(item["delta"] for item in adjustments)
        row["base_score"] = base_score
        row["score"] = base_score + total_delta
        row["score_adjustment_total"] = total_delta
        row["score_adjustments"] = adjustments

        adjustment_log_rows.append(
            {
                "system_id": sid,
                "original_score": base_score,
                "adjusted_score": row["score"],
                "adjustment_total": total_delta,
                "adjustments": adjustments,
            }
        )

    reranked = _sort_ranked_rows(rows)
    reranked_by_id = {row["system_id"]: row for row in reranked}

    updated_priority = dict(priority)
    updated_priority["schema_version"] = "tls-06.v1"
    updated_priority["phase"] = "TLS-06"
    updated_priority["fix_loop"] = {
        "deterministic": True,
        "rule": "score_logic_only_no_manual_overrides",
    }
    updated_priority["ranked_systems"] = reranked
    updated_priority["global_ranked_systems"] = reranked
    updated_priority["top_5"] = reranked[:5]

    req_rows: List[Dict[str, Any]] = []
    for req in priority.get("requested_candidate_ranking") or []:
        sid = req.get("system_id")
        updated = reranked_by_id.get(sid)
        req2 = dict(req)
        if updated:
            req2["global_rank"] = updated["rank"]
            req2["score"] = updated["score"]
        req_rows.append(req2)
    req_rows.sort(key=lambda row: (row.get("global_rank") is None, row.get("global_rank") or 10**9, row["system_id"]))
    for i, row in enumerate(req_rows, start=1):
        row["requested_rank"] = i
    updated_priority["requested_candidate_ranking"] = req_rows

    adjustment_log = {
        "schema_version": "tls-06-log.v1",
        "phase": "TLS-06",
        "weights": {
            "dependency_order_penalty": weights.dependency_order_penalty,
            "missing_dependency_penalty": weights.missing_dependency_penalty,
            "weak_explanation_penalty": weights.weak_explanation_penalty,
        },
        "rows": sorted(adjustment_log_rows, key=lambda item: item["system_id"]),
    }
    return updated_priority, adjustment_log


def _default_files_for(system_id: str, trust_gaps: List[str]) -> List[str]:
    base = [
        f"spectrum_systems/modules/{system_id.lower()}/",
        f"contracts/examples/{system_id.lower()}_*.json",
        f"tests/test_{system_id.lower()}*.py",
    ]
    if "missing_tests" in trust_gaps:
        base.append(f"tests/fixtures/{system_id.lower()}/")
    return base


def phase_3_action_layer(priority: Dict[str, Any]) -> Dict[str, Any]:
    systems: List[Dict[str, Any]] = []
    for row in priority.get("ranked_systems") or []:
        sid = row["system_id"]
        gaps = list(row.get("trust_gap_signals") or [])
        systems.append(
            {
                "system_id": sid,
                "rank": row["rank"],
                "next_prompt": row.get("next_prompt", f"Run TLS-FIX-{sid}"),
                "files_to_modify": _default_files_for(sid, gaps),
                "expected_artifacts": [
                    f"artifacts/{sid.lower()}_execution_record.json",
                    f"artifacts/{sid.lower()}_trust_gap_resolution.json",
                ],
                "stop_condition": (
                    "all trust_gap_signals cleared and owner review signals are present"
                    if gaps
                    else "no trust_gap_signals remain"
                ),
                "required_tests": [
                    f"pytest tests/test_{sid.lower()}*.py",
                    "pytest tests/test_contracts.py",
                ],
            }
        )

    return {
        "schema_version": "tls-07.v1",
        "phase": "TLS-07",
        "deterministic": True,
        "systems": systems,
    }


def phase_4_owner_input_packet(action_plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    owner_input_artifact = {
        "schema_version": "tls-08-owner-input-artifact.v1",
        "phase": "TLS-08",
        "routing_observation": "TLS->CDE->SEL",
        "recommendation_only": True,
        "owner_scope_observations": {
            "cde_review_input_present": True,
            "sel_policy_observation_present": True,
            "tpa_policy_observation_present": True,
            "gov_policy_observation_present": True,
        },
        "proposed_actions": [
            {"system_id": row["system_id"], "rank": row["rank"], "next_prompt": row["next_prompt"]}
            for row in action_plan.get("systems") or []
        ],
    }
    owner_input_packet = {
        "schema_version": "tls-08-owner-input-packet.v1",
        "phase": "TLS-08",
        "packet_type": "owner_input_packet",
        "recommendation_only": True,
        "owner_input_observation": "tls_owner_input_ready_for_review",
        "owner_outcome_present": False,
        "canonical_owner_statement": (
            "TLS is recommendation-only; CDE/TPA/SEL/GOV remain canonical owners; "
            "this packet is input for owner review and not an owner outcome."
        ),
    }
    return owner_input_artifact, owner_input_packet


def phase_5_learning_loop(
    review: Dict[str, Any],
    adjustment_log: Dict[str, Any],
    owner_input_packet: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    rows = adjustment_log.get("rows") or []
    corrected = sum(1 for row in rows if row.get("adjustment_total", 0) != 0)
    unchanged = sum(1 for row in rows if row.get("adjustment_total", 0) == 0)

    learning_record = {
        "schema_version": "tls-09-learning.v1",
        "phase": "TLS-09",
        "ranking_quality": {
            "correct_rankings": unchanged,
            "incorrect_rankings": corrected,
        },
        "execution_outcomes": {
            "owner_input_observation": owner_input_packet.get("owner_input_observation"),
            "recommendation_only": bool(owner_input_packet.get("recommendation_only")),
        },
        "delays_caused": {
            "premature_build_delays": len(review["review_findings"]["premature_build_candidates"]),
            "dependency_delay_count": len(review["review_findings"]["misranked_systems"]),
        },
    }

    total_rankings = max(1, corrected + unchanged)
    error_ratio = corrected / total_rankings
    weight_update_record = {
        "schema_version": "tls-09-weight-update.v1",
        "phase": "TLS-09",
        "update_rule": "deterministic_penalty_reweight",
        "observed_error_ratio": error_ratio,
        "recommended_weight_updates": {
            "dependency_order_penalty": 22 if error_ratio >= 0.2 else 20,
            "missing_dependency_penalty": 12 if error_ratio >= 0.2 else 10,
            "weak_explanation_penalty": 6 if error_ratio >= 0.2 else 5,
        },
    }
    return learning_record, weight_update_record


def run_tls_exec_01(priority_report_path: Path, out_dir: Path, top_level_priority_path: Path) -> Dict[str, Dict[str, Any]]:
    priority = _read_json(priority_report_path)

    review = phase_1_ranking_review(priority)
    _write_json(out_dir / "tls_ranking_review_report.json", review)

    updated_priority, adjustment_log = phase_2_fix_loop(priority, review)
    _write_json(out_dir / "system_dependency_priority_report.json", updated_priority)
    _write_json(top_level_priority_path, updated_priority)
    _write_json(out_dir / "ranking_adjustment_log.json", adjustment_log)

    action_plan = phase_3_action_layer(updated_priority)
    _write_json(out_dir / "tls_action_plan.json", action_plan)

    owner_input_artifact, owner_input_packet = phase_4_owner_input_packet(action_plan)
    _write_json(out_dir / "tls_control_input_artifact.json", owner_input_artifact)
    _write_json(out_dir / "tls_owner_input_packet.json", owner_input_packet)

    learning_record, weight_update_record = phase_5_learning_loop(review, adjustment_log, owner_input_packet)
    _write_json(out_dir / "tls_learning_record.json", learning_record)
    _write_json(out_dir / "tls_weight_update_record.json", weight_update_record)

    return {
        "review": review,
        "updated_priority": updated_priority,
        "adjustment_log": adjustment_log,
        "action_plan": action_plan,
        "owner_input_artifact": owner_input_artifact,
        "owner_input_packet": owner_input_packet,
        "learning_record": learning_record,
        "weight_update_record": weight_update_record,
    }
