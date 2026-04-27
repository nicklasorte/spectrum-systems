from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .next_step_artifact import blocked_payload, utc_now_iso, validate_artifact_shape
from .next_step_dependency_rules import LOCKED_SEQUENCE, first_unmet, status_from_done
from .next_step_inputs import NextStepInputs, load_inputs
from .next_step_redteam import run_redteam


def _source_refs(inputs: NextStepInputs) -> list[dict[str, Any]]:
    return [{"path": row.path, "required": row.required, "present": row.present, "content_hash": row.content_hash} for row in inputs.source_refs]


def _is_complete(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status", "")).lower()
    if status in {"pass", "implemented", "complete", "ready", "success"}:
        return True
    readiness = payload.get("h01_readiness")
    if isinstance(readiness, dict) and readiness.get("ready") is True:
        return True
    review_outcome = str(payload.get("review_decision", "")).lower()
    return review_outcome in {"pass", "approve", "approved"}


def _derive_done(inputs: NextStepInputs) -> set[str]:
    done: set[str] = set()
    payloads = inputs.payloads
    if _is_complete(payloads.get("artifacts/blf_01_baseline_failure_fix/delivery_report.json")):
        done.add("BLF-01")
    if _is_complete(payloads.get("artifacts/rfx_04_loop_07_08/delivery_report.json")):
        done.add("RFX-04")
    rmp_delivery = payloads.get("artifacts/rmp_01_delivery_report.json")
    rmp_drift = payloads.get("artifacts/rmp_drift_report.json")
    if _is_complete(rmp_delivery) and isinstance(rmp_drift, dict) and rmp_drift.get("drift_detected") is False:
        done.add("RMP-SUPER-01")

    h01_present = any(ref.present and ref.path.startswith("contracts/review_artifact/H01") for ref in inputs.source_refs) and any(
        ref.present and ref.path.startswith("docs/reviews/H01") for ref in inputs.source_refs
    )
    if h01_present and {"BLF-01", "RFX-04", "RMP-SUPER-01"}.issubset(done):
        done.add("H01")
    return done


def build_next_step_report(repo_root: Path) -> tuple[dict[str, Any], bool]:
    inputs = load_inputs(repo_root)
    source_refs = _source_refs(inputs)
    missing_required = [row.path for row in inputs.source_refs if row.required and not row.present]
    if missing_required:
        return blocked_payload(
            [f"missing_required_artifact:{path}" for path in missing_required],
            source_refs,
            ["Next-step recommendation blocked due to missing required artifact inputs."],
        ), True

    done = _derive_done(inputs)
    selected = first_unmet(done)
    advisory = inputs.payloads.get("artifacts/system_dependency_priority_report.json")
    advisory_top = [row["system_id"] for row in advisory.get("top_5", []) if isinstance(row, dict) and isinstance(row.get("system_id"), str)] if isinstance(advisory, dict) else []

    remaining: list[dict[str, Any]] = []
    ranked: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for idx, item in enumerate(LOCKED_SEQUENCE, start=1):
        deps_missing = [dep for dep in item.depends_on if dep not in done]
        status = status_from_done(item.id, done)
        remaining.append({
            "priority": idx,
            "work_item": item.work_item,
            "status": status,
            "why_it_matters": item.why_it_matters,
            "depends_on": item.depends_on,
            "risk_if_done_out_of_order": item.risk_if_done_out_of_order,
            "required_missing_artifacts_or_tests": deps_missing,
        })
        ranked.append({"priority": idx, "id": item.id, "work_item": item.work_item, "blocked_by": deps_missing, "eligible_now": not deps_missing and status != "complete"})
        if deps_missing and status != "complete":
            rejected.append({"work_item": item.id, "reason": f"{item.id} must wait for dependencies: {', '.join(deps_missing)}."})

    selected_recommendation = None
    reason_codes: list[str] = []
    if selected:
        selected_recommendation = {
            "id": selected.id,
            "work_item": selected.work_item,
            "why": selected.why_it_matters,
            "unlocks": [item.id for item in LOCKED_SEQUENCE if selected.id in item.depends_on],
            "depends_on": selected.depends_on,
            "execution_prompt_hint": "Build Fix Integrity Proof and proof-bound closure gate." if selected.id == "RFX-PROOF-01" else f"Execute {selected.id} with strict dependency closure evidence.",
        }
    else:
        reason_codes.append("no_remaining_eligible_steps")

    h01_claimed = any(ref.present and ref.path.startswith("contracts/review_artifact/H01") for ref in inputs.source_refs) and any(ref.present and ref.path.startswith("docs/reviews/H01") for ref in inputs.source_refs)
    red_team_findings = run_redteam(done, selected.id if selected else None, missing_required, advisory_top, h01_claimed=h01_claimed)

    payload = {
        "artifact_type": "next_step_recommendation_report",
        "schema_version": "1.0.0",
        "generated_at": utc_now_iso(),
        "status": "blocked" if not selected_recommendation else "pass",
        "readiness_state": "blocked" if not selected_recommendation else "ready",
        "source_refs": source_refs,
        "completed_work": [item.work_item for item in LOCKED_SEQUENCE if item.id in done],
        "partial_work": [],
        "remaining_work_table": remaining,
        "ranked_priorities": ranked,
        "selected_recommendation": selected_recommendation,
        "rejected_next_steps": rejected,
        "dependency_observations": [
            "Locked sequence enforces BLF -> RFX-04 -> RMP-SUPER-01 -> H01 -> RFX-PROOF-01 -> EVL -> TPA -> CDE -> SEL -> MET -> HOP.",
            "Advisory TLS ranking is non-owning and cannot bypass locked dependencies.",
        ],
        "red_team_findings": red_team_findings,
        "warnings": [],
        "reason_codes": sorted(set(reason_codes + inputs.reason_codes)),
    }
    validate_artifact_shape(payload)
    return payload, False


def write_next_step_report(repo_root: Path, out_path: Path | None = None) -> tuple[dict[str, Any], bool]:
    report, hard_failure = build_next_step_report(repo_root)
    target = out_path or (repo_root / "artifacts" / "next_step_recommendation_report.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report, hard_failure
