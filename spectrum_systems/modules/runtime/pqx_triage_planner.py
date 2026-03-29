"""Deterministic review-triage rack-and-stack planning helpers for governed PQX bundle runs."""

from __future__ import annotations

from copy import deepcopy

from spectrum_systems.contracts import validate_artifact


class PQXTriagePlannerError(ValueError):
    """Raised when triage planning inputs or outputs violate fail-closed governed semantics."""


_SEVERITY_TO_PRIORITY = {
    "critical": "p0",
    "high": "p1",
    "medium": "p2",
    "low": "p3",
}

_PRIORITY_ORDER = {"p0": 0, "p1": 1, "p2": 2, "p3": 3}
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

_ALLOWED_SOURCE_TYPES = {"review_finding", "fix_gate"}
_ALLOWED_EXECUTION_IMPACT = {"block_now", "run_before_resume", "run_next", "defer"}
_ALLOWED_REQUIRED_ACTION = {"fix", "review", "roadmap_patch", "doc_only", "investigate"}
_ALLOWED_INSERTION_MODES = {
    "patch_current_bundle",
    "insert_next_bundle",
    "defer_to_future_bundle",
    "roadmap_update_required",
    "human_decision_required",
}


def validate_triage_plan_inputs(
    *,
    run_id: str,
    trace_id: str,
    bundle_run_id: str,
    bundle_id: str,
    roadmap_authority_ref: str,
    review_inputs: list[dict],
    fix_gate_inputs: list[dict],
    findings: list[dict],
) -> None:
    for label, value in {
        "run_id": run_id,
        "trace_id": trace_id,
        "bundle_run_id": bundle_run_id,
        "bundle_id": bundle_id,
        "roadmap_authority_ref": roadmap_authority_ref,
    }.items():
        if not isinstance(value, str) or not value:
            raise PQXTriagePlannerError(f"{label} is required")

    if roadmap_authority_ref != "docs/roadmaps/system_roadmap.md":
        raise PQXTriagePlannerError("roadmap_authority_ref must resolve to docs/roadmaps/system_roadmap.md")

    if not isinstance(review_inputs, list) or not isinstance(fix_gate_inputs, list):
        raise PQXTriagePlannerError("review_inputs and fix_gate_inputs must be lists")

    if not isinstance(findings, list):
        raise PQXTriagePlannerError("findings must be a list")

    for entry in findings:
        if not isinstance(entry, dict):
            raise PQXTriagePlannerError("findings entries must be objects")
        source_type = entry.get("source_type")
        if source_type not in _ALLOWED_SOURCE_TYPES:
            raise PQXTriagePlannerError(f"unsupported source_type in finding input: {source_type}")


def load_review_and_fix_inputs(
    *,
    review_artifacts: list[dict] | None,
    review_artifact_refs: list[str] | None,
    fix_gate_records: list[dict] | None,
    fix_gate_record_refs: list[str] | None,
) -> tuple[list[dict], list[dict], list[str], list[str]]:
    reviews = deepcopy(review_artifacts or [])
    review_refs = list(review_artifact_refs or [])
    fixes = deepcopy(fix_gate_records or [])
    fix_refs = list(fix_gate_record_refs or [])

    if len(reviews) != len(review_refs):
        raise PQXTriagePlannerError("review artifact refs must align 1:1 with loaded review artifacts")
    if len(fixes) != len(fix_refs):
        raise PQXTriagePlannerError("fix gate refs must align 1:1 with loaded fix gate records")

    validated_reviews: list[dict] = []
    for idx, artifact in enumerate(reviews):
        try:
            validate_artifact(artifact, "pqx_review_result")
        except Exception as exc:  # pragma: no cover - bounded wrapper
            raise PQXTriagePlannerError(f"invalid pqx_review_result at index {idx}: {exc}") from exc
        validated_reviews.append(artifact)

    validated_fixes: list[dict] = []
    for idx, artifact in enumerate(fixes):
        try:
            validate_artifact(artifact, "pqx_fix_gate_record")
        except Exception as exc:  # pragma: no cover - bounded wrapper
            raise PQXTriagePlannerError(f"invalid pqx_fix_gate_record at index {idx}: {exc}") from exc
        validated_fixes.append(artifact)

    return validated_reviews, validated_fixes, review_refs, fix_refs


def normalize_triage_inputs(
    *,
    review_artifacts: list[dict],
    review_artifact_refs: list[str],
    fix_gate_records: list[dict],
    fix_gate_record_refs: list[str],
    step_ids: list[str],
    bundle_id: str,
) -> list[dict]:
    known_steps = set(step_ids)
    findings: list[dict] = []

    for review, review_ref in zip(review_artifacts, review_artifact_refs, strict=True):
        for finding in review["findings"]:
            affected = list(finding["affected_step_ids"])
            unknown = [step for step in affected if step not in known_steps]
            if unknown:
                raise PQXTriagePlannerError(
                    f"finding '{finding['finding_id']}' references steps outside active bundle scope: {unknown}"
                )
            if len(affected) != 1:
                raise PQXTriagePlannerError(
                    f"ambiguous finding-to-step mapping for finding '{finding['finding_id']}' (must map to exactly one step)"
                )
            findings.append(
                {
                    "finding_id": finding["finding_id"],
                    "source_type": "review_finding",
                    "source_artifact_ref": review_ref,
                    "source_artifact_id": review["review_id"],
                    "related_step_id": affected[0],
                    "related_bundle_id": review["bundle_id"],
                    "issue_type": finding["category"],
                    "severity": finding["severity"],
                    "priority": _SEVERITY_TO_PRIORITY[finding["severity"]],
                    "blocking": bool(finding["blocking"]),
                    "recommended_action": finding["recommended_action"],
                    "dependency_refs": sorted(set(finding["source_refs"])),
                    "reason_codes": [review["overall_disposition"]],
                }
            )

    for gate_record, gate_ref in zip(fix_gate_records, fix_gate_record_refs, strict=True):
        adjudication = gate_record["adjudication_inputs"]
        anchor_step = adjudication["insertion_point"]["anchor_step_id"]
        if anchor_step not in known_steps:
            raise PQXTriagePlannerError(
                f"fix gate '{gate_record['fix_gate_id']}' references anchor step outside active bundle: {anchor_step}"
            )

        severity = _severity_from_fix_id(gate_record["fix_id"])
        findings.append(
            {
                "finding_id": gate_record["originating_finding_id"] or gate_record["fix_id"],
                "source_type": "fix_gate",
                "source_artifact_ref": gate_ref,
                "source_artifact_id": gate_record["fix_gate_id"],
                "related_step_id": anchor_step,
                "related_bundle_id": gate_record["bundle_id"],
                "issue_type": "fix_gate_block" if gate_record["gate_status"] == "blocked" else "fix_gate_pass",
                "severity": severity,
                "priority": _SEVERITY_TO_PRIORITY[severity],
                "blocking": gate_record["gate_status"] == "blocked",
                "recommended_action": gate_record["blocking_reason"] or "fix gate passed",
                "dependency_refs": sorted(set(adjudication["artifact_refs"] + [gate_record["fix_execution_record_ref"]])),
                "reason_codes": list(gate_record["comparison_summary"]["reason_codes"]),
            }
        )

    ordered = sorted(
        findings,
        key=lambda item: (
            _PRIORITY_ORDER[item["priority"]],
            _SEVERITY_ORDER[item["severity"]],
            item["related_step_id"],
            item["source_type"],
            item["finding_id"],
        ),
    )

    for entry in ordered:
        if entry["related_bundle_id"] != bundle_id:
            raise PQXTriagePlannerError(
                f"cross-bundle triage input rejected: finding '{entry['finding_id']}' targets '{entry['related_bundle_id']}'"
            )
    return ordered


def classify_triage_item(item: dict) -> dict:
    severity = item["severity"]
    priority = item["priority"]
    blocking = item["blocking"]
    if _SEVERITY_TO_PRIORITY[severity] != priority:
        raise PQXTriagePlannerError(
            f"conflicting severity/priority state for finding '{item['finding_id']}': {severity}/{priority}"
        )

    if blocking and priority in {"p0", "p1"}:
        execution_impact = "block_now"
        required_action = "fix"
    elif blocking:
        execution_impact = "run_before_resume"
        required_action = "fix"
    elif priority in {"p0", "p1"}:
        execution_impact = "run_next"
        required_action = "review"
    elif item["source_type"] == "fix_gate":
        execution_impact = "run_next"
        required_action = "investigate"
    else:
        execution_impact = "defer"
        required_action = "doc_only"

    if execution_impact not in _ALLOWED_EXECUTION_IMPACT or required_action not in _ALLOWED_REQUIRED_ACTION:
        raise PQXTriagePlannerError("classification produced invalid execution_impact or required_action")

    return {
        "execution_impact": execution_impact,
        "required_action": required_action,
    }


def determine_insertion_mode(item: dict, classification: dict, step_ids: list[str]) -> dict:
    if item["related_step_id"] not in step_ids:
        raise PQXTriagePlannerError(f"invalid insertion target step: {item['related_step_id']}")

    impact = classification["execution_impact"]
    if impact == "block_now":
        mode = "patch_current_bundle"
        patch_step = f"patch:{item['finding_id']}"
        future_step = None
    elif impact in {"run_before_resume", "run_next"}:
        mode = "insert_next_bundle"
        patch_step = None
        future_step = f"future:{item['finding_id']}"
    elif classification["required_action"] == "doc_only":
        mode = "defer_to_future_bundle"
        patch_step = None
        future_step = f"defer:{item['finding_id']}"
    else:
        mode = "human_decision_required"
        patch_step = None
        future_step = None

    if item["source_type"] == "fix_gate" and item["blocking"]:
        mode = "roadmap_update_required"

    if mode not in _ALLOWED_INSERTION_MODES:
        raise PQXTriagePlannerError("determine_insertion_mode produced unsupported insertion_mode")

    return {
        "insertion_mode": mode,
        "proposed_patch_step_id": patch_step,
        "proposed_future_step_id": future_step,
    }


def build_triage_plan_record(
    *,
    run_id: str,
    trace_id: str,
    bundle_run_id: str,
    bundle_id: str,
    roadmap_authority_ref: str,
    review_artifacts: list[dict] | None,
    review_artifact_refs: list[str] | None,
    fix_gate_records: list[dict] | None,
    fix_gate_record_refs: list[str] | None,
    step_ids: list[str],
    created_at: str,
) -> dict:
    reviews, gates, review_refs, gate_refs = load_review_and_fix_inputs(
        review_artifacts=review_artifacts,
        review_artifact_refs=review_artifact_refs,
        fix_gate_records=fix_gate_records,
        fix_gate_record_refs=fix_gate_record_refs,
    )
    findings = normalize_triage_inputs(
        review_artifacts=reviews,
        review_artifact_refs=review_refs,
        fix_gate_records=gates,
        fix_gate_record_refs=gate_refs,
        step_ids=step_ids,
        bundle_id=bundle_id,
    )

    validate_triage_plan_inputs(
        run_id=run_id,
        trace_id=trace_id,
        bundle_run_id=bundle_run_id,
        bundle_id=bundle_id,
        roadmap_authority_ref=roadmap_authority_ref,
        review_inputs=reviews,
        fix_gate_inputs=gates,
        findings=findings,
    )

    triaged_items: list[dict] = []
    for item in findings:
        classification = classify_triage_item(item)
        insertion = determine_insertion_mode(item, classification, step_ids)
        triaged_items.append(
            {
                "finding_id": item["finding_id"],
                "source_type": item["source_type"],
                "source_artifact_ref": item["source_artifact_ref"],
                "related_step_id": item["related_step_id"],
                "related_bundle_id": item["related_bundle_id"],
                "issue_type": item["issue_type"],
                "severity": item["severity"],
                "priority": item["priority"],
                "execution_impact": classification["execution_impact"],
                "required_action": classification["required_action"],
                "insertion_mode": insertion["insertion_mode"],
                "blocking_status": "blocking" if item["blocking"] else "non_blocking",
                "rationale": ";".join(sorted(set(item["reason_codes"]))),
                "proposed_patch_step_id": insertion["proposed_patch_step_id"],
                "proposed_future_step_id": insertion["proposed_future_step_id"],
                "dependency_refs": item["dependency_refs"],
            }
        )

    record = {
        "schema_version": "1.0.0",
        "triage_plan_id": f"triage-plan:{run_id}:{bundle_id}:{len(triaged_items)}",
        "run_id": run_id,
        "trace_id": trace_id,
        "bundle_run_id": bundle_run_id,
        "roadmap_authority_ref": roadmap_authority_ref,
        "bundle_id": bundle_id,
        "review_artifact_refs": sorted(set(review_refs)),
        "fix_gate_artifact_refs": sorted(set(gate_refs)),
        "findings_analyzed": [item["finding_id"] for item in triaged_items],
        "triaged_items": triaged_items,
        "insertion_recommendations": [
            {
                "finding_id": item["finding_id"],
                "insertion_mode": item["insertion_mode"],
                "proposed_patch_step_id": item["proposed_patch_step_id"],
                "proposed_future_step_id": item["proposed_future_step_id"],
            }
            for item in triaged_items
            if item["insertion_mode"] in {"patch_current_bundle", "insert_next_bundle", "roadmap_update_required"}
        ],
        "blocked_items": [item["finding_id"] for item in triaged_items if item["blocking_status"] == "blocking"],
        "deferred_items": [item["finding_id"] for item in triaged_items if item["execution_impact"] == "defer"],
        "execution_recommendations": {
            "must_run_next": [
                item["finding_id"]
                for item in triaged_items
                if item["execution_impact"] in {"block_now", "run_before_resume", "run_next"}
            ],
            "must_block_advancement": [item["finding_id"] for item in triaged_items if item["execution_impact"] == "block_now"],
            "can_defer": [item["finding_id"] for item in triaged_items if item["execution_impact"] == "defer"],
            "human_review_required": [
                item["finding_id"]
                for item in triaged_items
                if item["insertion_mode"] in {"roadmap_update_required", "human_decision_required"}
            ],
        },
        "summary_counts": {
            "findings_total": len(triaged_items),
            "blocking_total": len([item for item in triaged_items if item["blocking_status"] == "blocking"]),
            "deferred_total": len([item for item in triaged_items if item["execution_impact"] == "defer"]),
            "patch_current_bundle_total": len(
                [item for item in triaged_items if item["insertion_mode"] == "patch_current_bundle"]
            ),
            "insert_next_bundle_total": len(
                [item for item in triaged_items if item["insertion_mode"] == "insert_next_bundle"]
            ),
            "roadmap_update_required_total": len(
                [item for item in triaged_items if item["insertion_mode"] == "roadmap_update_required"]
            ),
        },
        "created_at": created_at,
    }
    assert_triage_plan_consistency(record)
    return record


def assert_triage_plan_consistency(record: dict) -> None:
    try:
        validate_artifact(record, "pqx_triage_plan_record")
    except Exception as exc:  # pragma: no cover - bounded wrapper
        raise PQXTriagePlannerError(f"invalid pqx_triage_plan_record artifact: {exc}") from exc

    items = record["triaged_items"]
    findings = [item["finding_id"] for item in items]
    if findings != sorted(findings, key=lambda fid: (record["findings_analyzed"].index(fid), fid)):
        # Keep explicit deterministic ordering check aligned to serialized ordering.
        if findings != record["findings_analyzed"]:
            raise PQXTriagePlannerError("triage plan findings_analyzed order drift detected")

    if set(record["blocked_items"]) - set(record["findings_analyzed"]):
        raise PQXTriagePlannerError("blocked_items must be a subset of findings_analyzed")
    if set(record["deferred_items"]) - set(record["findings_analyzed"]):
        raise PQXTriagePlannerError("deferred_items must be a subset of findings_analyzed")


def _severity_from_fix_id(fix_id: str) -> str:
    lowered = str(fix_id).lower()
    for severity in ("critical", "high", "medium", "low"):
        if f":{severity}" in lowered:
            return severity
    return "high"
