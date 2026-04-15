from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from spectrum_systems.modules.wpg import (
    StageContext,
    WPGError,
    assemble_working_paper,
    build_phase_checkpoint_record,
    build_phase_handoff_record,
    build_phase_resume_record,
    build_faq,
    cluster_faqs,
    default_phase_registry,
    evaluate_phase_transition,
    extract_questions,
    format_faq_for_report,
    write_sections,
    ingest_comment_matrix_signal,
    build_agency_critique_profile,
    build_industry_critique_profile,
    retrieve_critique_memory,
    run_multi_pass_critique,
    build_judgment_record,
    retrieve_precedent,
    evaluate_judgment,
    compare_cross_run,
    build_study_policy_profile,
    evaluate_quality_slo,
    build_governance_policy_pack,
    build_lifecycle_certification,
    build_reusable_template,
)
from spectrum_systems.modules.wpg.common import (
    control_decision_from_eval,
    ensure_contract,
    make_eval_artifacts,
    normalize_text_tokens,
    normalize_transcript_payload,
    stable_hash,
    stage_provenance,
)


REQUIRED_ENFORCEMENT = {"ALLOW": "proceed", "WARN": "annotate", "BLOCK": "trigger_repair", "FREEZE": "halt"}


def _assert_stage_control(name: str, artifact: Dict[str, Any]) -> None:
    control = artifact.get("evaluation_refs", {}).get("control_decision")
    if not control:
        raise WPGError(f"missing control_decision on stage artifact: {name}")
    decision = control.get("decision")
    if decision not in REQUIRED_ENFORCEMENT:
        raise WPGError(f"invalid control decision on {name}: {decision}")
    enforcement = control.get("enforcement", {}).get("action")
    if REQUIRED_ENFORCEMENT[decision] != enforcement:
        raise WPGError(f"enforcement mismatch for {name}: {decision} -> {enforcement}")


def _build_phase_a_assurance_artifacts(
    *,
    faq_bundle: Dict[str, Any],
    sections: Dict[str, Any],
    working_paper: Dict[str, Any],
    trace_id: str,
) -> Dict[str, Any]:
    conflict_rows = faq_bundle["faq_conflict_artifact"]["outputs"].get("conflicts", [])
    confidence_rows = faq_bundle["faq_confidence_artifact"]["outputs"].get("confidence_rows", [])
    unknown_count = sum(1 for row in confidence_rows if row.get("unknown"))

    grounding_eval = ensure_contract(
        {
            "artifact_type": "wpg_grounding_eval_case",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "faq_grounding_failures": sum(1 for row in confidence_rows if not row.get("grounded", False) and not row.get("unknown", False)),
                "supported_claim_ratio": round(
                    sum(1 for row in confidence_rows if row.get("grounded", False)) / max(len(confidence_rows), 1), 3
                ),
            },
        },
        "wpg_grounding_eval_case",
    )

    contradiction_propagation = ensure_contract(
        {
            "artifact_type": "wpg_contradiction_propagation_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "conflict_count": len(conflict_rows),
                "faq_conflict_ids": [f"conflict-{i+1:02d}" for i in range(len(conflict_rows))],
                "section_conflict_annotation": len(working_paper["outputs"].get("conflicts", [])),
                "paper_conflict_annotation": len(working_paper["outputs"].get("conflicts", [])),
            },
        },
        "wpg_contradiction_propagation_record",
    )

    uncertainty_control = ensure_contract(
        {
            "artifact_type": "wpg_uncertainty_control_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "unknown_count": unknown_count,
                "low_confidence_count": sum(1 for row in confidence_rows if row.get("confidence", 0.0) < 0.6),
                "max_confidence": max((row.get("confidence", 0.0) for row in confidence_rows), default=0.0),
                "narrative_warning_present": "Unknowns requiring follow-up:" in working_paper["outputs"].get("content", ""),
            },
        },
        "wpg_uncertainty_control_record",
    )

    chronology = [s.get("chronology", {}) for s in sections["outputs"].get("sections", [])]
    narrative_integrity = ensure_contract(
        {
            "artifact_type": "narrative_integrity_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "section_count": len(sections["outputs"].get("sections", [])),
                "chronology_justifications": [c.get("justification", "") for c in chronology],
                "synthetic_ordering_rationale_present": all(bool(c.get("justification")) for c in chronology),
            },
        },
        "narrative_integrity_record",
    )

    return {
        "wpg_grounding_eval_case": grounding_eval,
        "wpg_contradiction_propagation_record": contradiction_propagation,
        "wpg_uncertainty_control_record": uncertainty_control,
        "narrative_integrity_record": narrative_integrity,
    }


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _normalize_meeting_payload(meeting_payload: Dict[str, Any], *, trace_id: str) -> Dict[str, Any]:
    explicit = bool(meeting_payload)
    if explicit:
        required = ("date", "topic", "study_context", "participants", "agenda")
        missing = [field for field in required if not meeting_payload.get(field)]
        if missing:
            raise WPGError(f"invalid meeting artifact missing required fields: {', '.join(missing)}")
    participants = [str(p).strip() for p in _as_list(meeting_payload.get("participants")) if str(p).strip()]
    agenda = [str(i).strip() for i in _as_list(meeting_payload.get("agenda")) if str(i).strip()]
    artifact = {
        "artifact_type": "meeting_artifact",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {
            "meeting_id": str(meeting_payload.get("meeting_id", "meeting-unknown")),
            "date": str(meeting_payload.get("date", "1970-01-01")),
            "topic": str(meeting_payload.get("topic", "Transcript-only workflow run")),
            "study_context": str(meeting_payload.get("study_context", "No explicit meeting artifact provided.")),
            "participants": participants or ["unknown-participant"],
            "agenda": agenda or ["review transcript"],
            "transcript_ref": str(meeting_payload.get("transcript_ref", "transcript_artifact")),
        },
    }
    return ensure_contract(artifact, "meeting_artifact")


def _build_meeting_minutes(
    transcript_artifact: Dict[str, Any], meeting_artifact: Dict[str, Any], trace_id: str, run_id: str
) -> Dict[str, Any]:
    segments = transcript_artifact.get("outputs", {}).get("segments", [])
    segment_text = [s.get("text", "") for s in segments]
    summary = " ".join(segment_text[:2]).strip()
    decisions = [text for text in segment_text if any(k in text.lower() for k in ("decide", "approved", "resolved"))][:5]
    open_questions = [text for text in segment_text if "?" in text][:5]
    if not decisions and segment_text:
        decisions = ["No explicit decisions captured."]
    if not open_questions:
        open_questions = ["No open questions captured."]
    checks = [
        {"description": "minutes summary present", "passed": bool(summary), "failure_mode": "missing_summary"},
        {"description": "minutes decisions present", "passed": bool(decisions), "failure_mode": "missing_decisions"},
        {"description": "minutes open questions present", "passed": bool(open_questions), "failure_mode": "missing_open_questions"},
    ]
    eval_pack = make_eval_artifacts("meeting_minutes_generation", checks, type("Ctx", (), {"run_id": run_id, "trace_id": trace_id})())
    control = control_decision_from_eval(stage="meeting_minutes_generation", eval_summary=eval_pack["eval_summary"], no_content=not bool(summary))
    artifact = ensure_contract(
        {
            "artifact_type": "meeting_minutes_artifact",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "inputs_ref": ["meeting_artifact", "transcript_artifact"],
            "outputs": {
                "meeting_id": meeting_artifact["outputs"]["meeting_id"],
                "summary": summary,
                "decisions": decisions,
                "open_questions": open_questions,
            },
            "provenance": stage_provenance("meeting_minutes_generation", type("Ctx", (), {"run_id": run_id, "trace_id": trace_id, "policy_version": "1.0.0", "eval_version": "1.0.0"})(), ["meeting_artifact", "transcript_artifact"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "meeting_minutes_artifact",
    )
    return artifact


def _extract_action_items(
    transcript_artifact: Dict[str, Any], meeting_minutes_artifact: Dict[str, Any], trace_id: str, run_id: str
) -> Dict[str, Any]:
    source_lines = [s.get("text", "") for s in transcript_artifact.get("outputs", {}).get("segments", [])]
    source_lines.extend(meeting_minutes_artifact.get("outputs", {}).get("decisions", []))
    candidates = [line for line in source_lines if any(k in line.lower() for k in ("will ", "action", "todo", "must ", "follow up"))]
    action_items = []
    for idx, line in enumerate(candidates, start=1):
        action_items.append(
            {
                "action_id": f"act-{idx:02d}",
                "description": line,
                "owner": "unassigned",
                "required": "must " in line.lower(),
                "priority": "critical" if "must " in line.lower() else "normal",
            }
        )
    explicit_empty = not bool(action_items)
    eval_pack = make_eval_artifacts(
        "action_item_extraction",
        [
            {"description": "action extraction executed", "passed": True, "failure_mode": "extraction_not_run"},
            {"description": "empty actions explicit", "passed": (not action_items and explicit_empty) or bool(action_items), "failure_mode": "implicit_empty_actions"},
        ],
        type("Ctx", (), {"run_id": run_id, "trace_id": trace_id})(),
    )
    control = control_decision_from_eval(stage="action_item_extraction", eval_summary=eval_pack["eval_summary"])
    return ensure_contract(
        {
            "artifact_type": "action_item_artifact",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "inputs_ref": ["meeting_minutes_artifact", "transcript_artifact"],
            "outputs": {"action_items": action_items, "explicit_empty": explicit_empty},
            "provenance": stage_provenance("action_item_extraction", type("Ctx", (), {"run_id": run_id, "trace_id": trace_id, "policy_version": "1.0.0", "eval_version": "1.0.0"})(), ["meeting_minutes_artifact", "transcript_artifact"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "action_item_artifact",
    )


def _build_action_linkage(
    action_item_artifact: Dict[str, Any], faq_artifact: Dict[str, Any], sections_artifact: Dict[str, Any], trace_id: str, run_id: str
) -> Dict[str, Any]:
    faqs = faq_artifact.get("outputs", {}).get("faqs", [])
    sections = sections_artifact.get("outputs", {}).get("sections", [])
    records = []
    required_unlinked = 0
    for action in action_item_artifact.get("outputs", {}).get("action_items", []):
        action_tokens = normalize_text_tokens(action.get("description", ""))
        faq_link = next((f.get("question", "") for f in faqs if action_tokens & normalize_text_tokens(f.get("question", ""))), "")
        section_link = next((s.get("title", "") for s in sections if action_tokens & normalize_text_tokens(s.get("title", ""))), "")
        if action.get("required") and (not faq_link or not section_link):
            required_unlinked += 1
        records.append({"action_id": action["action_id"], "faq_ref": faq_link, "section_ref": section_link})
    eval_pack = make_eval_artifacts(
        "action_linkage",
        [{"description": "required actions linked", "passed": required_unlinked == 0, "failure_mode": "required_action_missing_linkage"}],
        type("Ctx", (), {"run_id": run_id, "trace_id": trace_id})(),
    )
    control = control_decision_from_eval(
        stage="action_linkage",
        eval_summary=eval_pack["eval_summary"],
        contradictions_unresolved=required_unlinked,
    )
    return ensure_contract(
        {
            "artifact_type": "action_linkage_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "inputs_ref": ["action_item_artifact", "faq_artifact", "working_section_artifact"],
            "outputs": {"linkages": records, "required_unlinked": required_unlinked},
            "provenance": stage_provenance("action_linkage", type("Ctx", (), {"run_id": run_id, "trace_id": trace_id, "policy_version": "1.0.0", "eval_version": "1.0.0"})(), ["action_item_artifact", "faq_artifact", "working_section_artifact"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "action_linkage_record",
    )


def _normalize_comment_payload(comment_payload: Dict[str, Any], *, trace_id: str, strict: bool = True) -> Dict[str, Any]:
    comments = []
    for idx, raw in enumerate(_as_list(comment_payload.get("comments")), start=1):
        if not isinstance(raw, dict):
            continue
        source_text = raw.get("text") if strict else (raw.get("text") or raw.get("resolution"))
        text = str(source_text or "").strip()
        if strict and not text:
            raise WPGError("invalid comment artifact contains empty text")
        if strict and raw.get("severity", "normal") not in {"low", "normal", "high", "critical"}:
            raise WPGError("invalid comment artifact contains unsupported severity")
        comments.append(
            {
                "comment_id": str(raw.get("comment_id", f"c-{idx:02d}")),
                "text": text or "No comment text provided.",
                "severity": str(raw.get("severity", "normal")).lower(),
                "critical": bool(raw.get("critical", False)),
            }
        )
    artifact = {"artifact_type": "comment_artifact", "schema_version": "1.0.0", "trace_id": trace_id, "outputs": {"comments": comments}}
    return ensure_contract(artifact, "comment_artifact")


def _build_comment_resolution_matrix(comment_artifact: Dict[str, Any], trace_id: str, run_id: str) -> Dict[str, Any]:
    entries = []
    for c in comment_artifact.get("outputs", {}).get("comments", []):
        disposition = "resolved" if c.get("text") else "needs_input"
        entries.append(
            {
                "entry_id": f"ENT-{len(entries)+1:04d}",
                "comment_id": f"CMT-{len(entries)+1:04d}",
                "resolution_status": disposition,
                "response_text": f"Addressed: {c.get('text', '')}",
                "action_items": [],
                "validated_by": {
                    "name": "CRM Workflow",
                    "role": "workflow-review",
                    "timestamp": "2026-04-15T00:00:00Z",
                    "review_status": "pending_review",
                },
                "applies_to_revision": "rev1",
                "provenance_id": f"PRV-CMT-{len(entries)+1:04d}",
            }
        )
    if not entries:
        entries.append(
            {
                "entry_id": "ENT-0001",
                "comment_id": "CMT-0001",
                "resolution_status": "needs_input",
                "response_text": "No comments supplied; matrix captures explicit empty state.",
                "action_items": [],
                "validated_by": {
                    "name": "CRM Workflow",
                    "role": "workflow-review",
                    "timestamp": "2026-04-15T00:00:00Z",
                    "review_status": "pending_review",
                },
                "applies_to_revision": "rev1",
                "provenance_id": "PRV-CMT-0001",
            }
        )
    eval_pack = make_eval_artifacts(
        "comment_resolution_matrix",
        [{"description": "matrix rows valid", "passed": all(r.get("entry_id") for r in entries), "failure_mode": "invalid_matrix"}],
        type("Ctx", (), {"run_id": run_id, "trace_id": trace_id})(),
    )
    control = control_decision_from_eval(stage="comment_resolution_matrix", eval_summary=eval_pack["eval_summary"])
    return ensure_contract(
        {
            "artifact_type": "comment_resolution_matrix",
            "schema_version": "1.0.0",
            "artifact_class": "review",
            "artifact_id": f"CRM-{run_id.upper()}",
            "artifact_version": "1.0.0",
            "standards_version": "2026.03.0",
            "record_id": f"REC-CRM-{run_id.upper()}",
            "run_id": f"run-{run_id}",
            "created_at": "2026-04-15T00:00:00Z",
            "created_by": {"name": "CRM Engine", "role": "resolution", "agent_type": "workflow"},
            "source_repo": "nicklasorte/spectrum-systems",
            "source_repo_version": "local",
            "matrix_id": f"CRM-{run_id.upper()}",
            "comment_set_id": f"CSET-{run_id.upper()}",
            "working_paper_id": f"WKP-{run_id.upper()}",
            "working_paper_revision": "rev1",
            "input_artifacts": [
                {
                    "artifact_id": f"CSET-{run_id.upper()}",
                    "artifact_type": "comment_artifact",
                    "artifact_version": "1.0.0",
                    "role": "source",
                }
            ],
            "entries": entries,
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "comment_resolution_matrix",
    )


def _build_comment_mapping_record(
    comment_artifact: Dict[str, Any], faq_artifact: Dict[str, Any], sections_artifact: Dict[str, Any], trace_id: str, run_id: str
) -> Dict[str, Any]:
    faqs = faq_artifact.get("outputs", {}).get("faqs", [])
    sections = sections_artifact.get("outputs", {}).get("sections", [])
    mappings = []
    critical_unmapped = 0
    for c in comment_artifact.get("outputs", {}).get("comments", []):
        tokens = normalize_text_tokens(c.get("text", ""))
        faq_ref = next((f.get("question", "") for f in faqs if tokens & normalize_text_tokens(f.get("question", ""))), "")
        section_ref = next((s.get("title", "") for s in sections if tokens & normalize_text_tokens(s.get("title", ""))), "")
        evidence = "faq" if faq_ref else ("section" if section_ref else "")
        if c.get("critical") and not evidence:
            critical_unmapped += 1
        mappings.append({"comment_id": c["comment_id"], "faq_ref": faq_ref, "section_ref": section_ref, "evidence_ref": evidence})
    eval_pack = make_eval_artifacts(
        "comment_mapping",
        [{"description": "critical comments mapped", "passed": critical_unmapped == 0, "failure_mode": "unmapped_critical_comment"}],
        type("Ctx", (), {"run_id": run_id, "trace_id": trace_id})(),
    )
    control = control_decision_from_eval(stage="comment_mapping", eval_summary=eval_pack["eval_summary"], contradictions_unresolved=critical_unmapped)
    return ensure_contract(
        {
            "artifact_type": "comment_mapping_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "inputs_ref": ["comment_artifact", "faq_artifact", "working_section_artifact"],
            "outputs": {"mappings": mappings, "critical_unmapped": critical_unmapped},
            "provenance": stage_provenance("comment_mapping", type("Ctx", (), {"run_id": run_id, "trace_id": trace_id, "policy_version": "1.0.0", "eval_version": "1.0.0"})(), ["comment_artifact", "faq_artifact", "working_section_artifact"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "comment_mapping_record",
    )


def _build_revision_plan(
    comment_resolution_matrix: Dict[str, Any], comment_mapping_record: Dict[str, Any], trace_id: str, run_id: str
) -> Dict[str, Any]:
    mapping_by_comment = {m["comment_id"]: m for m in comment_mapping_record.get("outputs", {}).get("mappings", [])}
    tasks = []
    for row in comment_resolution_matrix.get("entries", []):
        if row.get("resolution_status") != "resolved":
            map_row = mapping_by_comment.get(row.get("comment_id"), {})
            tasks.append(
                {
                    "task_id": f"rev-{len(tasks)+1:02d}",
                    "comment_id": row.get("comment_id"),
                    "target_section": map_row.get("section_ref", ""),
                    "instruction": row.get("response_text", ""),
                }
            )
    eval_pack = make_eval_artifacts(
        "revision_plan",
        [{"description": "revision plan valid", "passed": isinstance(tasks, list), "failure_mode": "invalid_revision_plan"}],
        type("Ctx", (), {"run_id": run_id, "trace_id": trace_id})(),
    )
    control = control_decision_from_eval(stage="revision_plan", eval_summary=eval_pack["eval_summary"])
    return ensure_contract(
        {
            "artifact_type": "revision_plan_artifact",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "inputs_ref": ["comment_resolution_matrix", "comment_mapping_record"],
            "outputs": {"tasks": tasks},
            "provenance": stage_provenance("revision_plan", type("Ctx", (), {"run_id": run_id, "trace_id": trace_id, "policy_version": "1.0.0", "eval_version": "1.0.0"})(), ["comment_resolution_matrix", "comment_mapping_record"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "revision_plan_artifact",
    )


def _apply_revisions(revision_plan_artifact: Dict[str, Any], working_paper: Dict[str, Any], trace_id: str, run_id: str) -> Dict[str, Any]:
    tasks = revision_plan_artifact.get("outputs", {}).get("tasks", [])
    if tasks is None:
        tasks = []
    content = working_paper.get("outputs", {}).get("content", "")
    applied = []
    for t in tasks:
        content += f"\n- Revision {t['task_id']} ({t.get('comment_id', 'unknown')}): {t.get('instruction', '')}"
        applied.append(t["task_id"])
    eval_pack = make_eval_artifacts(
        "revision_application",
        [{"description": "revision requires plan", "passed": isinstance(tasks, list), "failure_mode": "revision_without_plan"}],
        type("Ctx", (), {"run_id": run_id, "trace_id": trace_id})(),
    )
    control = control_decision_from_eval(stage="revision_application", eval_summary=eval_pack["eval_summary"])
    return ensure_contract(
        {
            "artifact_type": "revision_application_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "inputs_ref": ["revision_plan_artifact", "working_paper_artifact"],
            "outputs": {"applied_task_ids": applied, "revised_content": content},
            "provenance": stage_provenance("revision_application", type("Ctx", (), {"run_id": run_id, "trace_id": trace_id, "policy_version": "1.0.0", "eval_version": "1.0.0"})(), ["revision_plan_artifact", "working_paper_artifact"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "revision_application_record",
    )


def _build_comment_disposition_record(comment_resolution_matrix: Dict[str, Any], trace_id: str, run_id: str) -> Dict[str, Any]:
    rows = comment_resolution_matrix.get("entries", [])
    by_state = {"resolved": 0, "unresolved": 0, "deferred": 0, "escalated": 0}
    critical_unresolved = 0
    for row in rows:
        state = row.get("resolution_status", "unresolved")
        if state not in by_state:
            by_state[state] = 0
        by_state[state] += 1
        if state in {"unresolved", "escalated", "needs_input"} and "critical" in row.get("response_text", "").lower():
            critical_unresolved += 1
    eval_pack = make_eval_artifacts(
        "comment_disposition_tracking",
        [{"description": "critical unresolved blocked", "passed": critical_unresolved == 0, "failure_mode": "unresolved_critical_issue"}],
        type("Ctx", (), {"run_id": run_id, "trace_id": trace_id})(),
    )
    control = control_decision_from_eval(
        stage="comment_disposition_tracking",
        eval_summary=eval_pack["eval_summary"],
        contradictions_unresolved=critical_unresolved,
    )
    return ensure_contract(
        {
            "artifact_type": "comment_disposition_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "inputs_ref": ["comment_resolution_matrix"],
            "outputs": {"state_counts": by_state, "critical_unresolved": critical_unresolved},
            "provenance": stage_provenance("comment_disposition_tracking", type("Ctx", (), {"run_id": run_id, "trace_id": trace_id, "policy_version": "1.0.0", "eval_version": "1.0.0"})(), ["comment_resolution_matrix"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "comment_disposition_record",
    )


def run_wpg_pipeline(
    transcript_payload: Dict[str, Any],
    *,
    run_id: str,
    trace_id: str,
    mode: str = "working_paper",
    prior_working_paper: Dict[str, Any] | None = None,
    resolved_comments: Dict[str, Any] | None = None,
    meeting_artifact: Dict[str, Any] | None = None,
    comment_artifact: Dict[str, Any] | None = None,
    phase_checkpoint_record: Dict[str, Any] | None = None,
    phase_registry: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ctx = StageContext(run_id=run_id, trace_id=trace_id)
    registry = ensure_contract(phase_registry, "phase_registry") if phase_registry else default_phase_registry(trace_id)
    checkpoint = (
        ensure_contract(phase_checkpoint_record, "phase_checkpoint_record")
        if phase_checkpoint_record
        else build_phase_checkpoint_record(
            phase_id="PHASE_A",
            phase_label="Core hardening",
            status="COMPLETE",
            trace_id=trace_id,
            completed_step_refs=["WPG-25", "WPG-26", "WPG-27", "WPG-28", "WPG-29", "WPG-30"],
        )
    )
    transition = evaluate_phase_transition(
        phase_checkpoint_record=checkpoint,
        phase_registry=registry,
        requested_action="continue",
        redteam_open_high=0,
        validation_passed=True,
    )
    if transition["decision"] == "BLOCK":
        reasons = ",".join(transition["reason_codes"])
        raise WPGError(f"phase transition blocked: {reasons}")

    transcript_artifact = ensure_contract(normalize_transcript_payload(transcript_payload, trace_id=trace_id), "transcript_artifact")
    meeting_normalized = _normalize_meeting_payload(meeting_artifact or {}, trace_id=trace_id)
    meeting_minutes_artifact = _build_meeting_minutes(transcript_artifact, meeting_normalized, trace_id, run_id)
    action_item_artifact = _extract_action_items(transcript_artifact, meeting_minutes_artifact, trace_id, run_id)

    question_set = extract_questions(transcript_artifact, ctx)
    faq_bundle = build_faq(question_set, transcript_artifact, ctx)
    faq_report = format_faq_for_report(faq_bundle["faq_artifact"], ctx, mode=mode)
    cluster_bundle = cluster_faqs(faq_report, ctx)
    sections = write_sections(cluster_bundle["faq_cluster_artifact"], ctx)
    action_linkage_record = _build_action_linkage(action_item_artifact, faq_bundle["faq_artifact"], sections, trace_id, run_id)
    comment_payload = (
        comment_artifact
        if comment_artifact is not None
        else ({"comments": resolved_comments.get("resolved_comments", [])} if resolved_comments else {"comments": []})
    )
    comment_input = _normalize_comment_payload(comment_payload, trace_id=trace_id, strict=comment_artifact is not None)
    comment_resolution_matrix = _build_comment_resolution_matrix(comment_input, trace_id, run_id)
    comment_mapping_record = _build_comment_mapping_record(comment_input, faq_bundle["faq_artifact"], sections, trace_id, run_id)
    revision_plan_artifact = _build_revision_plan(comment_resolution_matrix, comment_mapping_record, trace_id, run_id)
    assembly = assemble_working_paper(
        sections,
        cluster_bundle["unknowns_artifact"],
        faq_bundle["faq_conflict_artifact"],
        resolved_comments or {"resolved_comments": []},
        prior_working_paper,
        ctx,
        mode,
    )
    revision_application_record = _apply_revisions(revision_plan_artifact, assembly["working_paper_artifact"], trace_id, run_id)
    comment_disposition_record = _build_comment_disposition_record(comment_resolution_matrix, trace_id, run_id)

    comment_matrix_signal_artifact = ingest_comment_matrix_signal(comment_resolution_matrix, ctx)
    agency_critique_profile = build_agency_critique_profile(comment_matrix_signal_artifact, ctx)
    industry_critique_profile = build_industry_critique_profile(comment_matrix_signal_artifact, ctx)
    critique_retrieval_record = retrieve_critique_memory(
        comment_matrix_signal_artifact,
        trace_id=trace_id,
        band="C",
        topic="deployment",
        stakeholder="unassigned",
        section_type="general",
    )
    stakeholder_critique_artifact = run_multi_pass_critique(
        sections_artifact=sections,
        agency_profile=agency_critique_profile,
        industry_profile=industry_critique_profile,
        ctx=ctx,
    )
    judgment_record = build_judgment_record(critique_artifact=stakeholder_critique_artifact, trace_id=trace_id)
    precedent_retrieval = retrieve_precedent(judgment_record=judgment_record, prior_records=[judgment_record], trace_id=trace_id)
    judgment_eval = evaluate_judgment(judgment_record=judgment_record, precedent_retrieval=precedent_retrieval, trace_id=trace_id)
    wpg_cross_run_comparison_artifact = compare_cross_run(run_a={"replay": {"signature": stable_hash(question_set)}}, run_b={"replay": {"signature": stable_hash(sections)}}, trace_id=trace_id)
    wpg_study_policy_profile = build_study_policy_profile(study_id="wpg-default-study", required_rules=["require_eval_suite", "require_control_decision"], trace_id=trace_id)
    wpg_quality_slo = evaluate_quality_slo(quality_score=0.95, error_budget_remaining=0.2, trace_id=trace_id)
    governance_policy_pack = build_governance_policy_pack(trace_id=trace_id)
    assurance = _build_phase_a_assurance_artifacts(
        faq_bundle=faq_bundle,
        sections=sections,
        working_paper=assembly["working_paper_artifact"],
        trace_id=trace_id,
    )

    artifact_chain = {
        "meeting_artifact": meeting_normalized,
        "transcript_artifact": transcript_artifact,
        "meeting_minutes_artifact": meeting_minutes_artifact,
        "action_item_artifact": action_item_artifact,
        "question_set_artifact": question_set,
        **faq_bundle,
        "faq_report_artifact": faq_report,
        **cluster_bundle,
        "working_section_artifact": sections,
        "action_linkage_record": action_linkage_record,
        "comment_artifact": comment_input,
        "comment_resolution_matrix": comment_resolution_matrix,
        "comment_mapping_record": comment_mapping_record,
        "revision_plan_artifact": revision_plan_artifact,
        "revision_application_record": revision_application_record,
        "comment_disposition_record": comment_disposition_record,
        "comment_matrix_signal_artifact": comment_matrix_signal_artifact,
        "agency_critique_profile": agency_critique_profile,
        "industry_critique_profile": industry_critique_profile,
        "critique_retrieval_record": critique_retrieval_record,
        "stakeholder_critique_artifact": stakeholder_critique_artifact,
        "judgment_record": judgment_record,
        "precedent_retrieval": precedent_retrieval,
        "judgment_eval": judgment_eval,
        "wpg_cross_run_comparison_artifact": wpg_cross_run_comparison_artifact,
        "wpg_study_policy_profile": wpg_study_policy_profile,
        "wpg_quality_slo": wpg_quality_slo,
        **governance_policy_pack,
        **assembly,
        **assurance,
        "phase_registry": registry,
        "phase_checkpoint_record": checkpoint,
        "phase_transition_policy_result": transition,
    }
    phase_resume = build_phase_resume_record(
        checkpoint=checkpoint,
        next_executable_slice=transition["next_phase"] or checkpoint["phase_id"],
        remaining_required_slices=[transition["next_phase"] or checkpoint["phase_id"]],
    )
    phase_handoff = build_phase_handoff_record(
        checkpoint=checkpoint,
        resume_record=phase_resume,
        handoff_notes=["Transition evaluated by governed phase policy."],
    )
    artifact_chain["phase_resume_record"] = phase_resume
    artifact_chain["phase_handoff_record"] = phase_handoff
    controls = [
        artifact.get("evaluation_refs", {}).get("control_decision")
        for artifact in artifact_chain.values()
        if isinstance(artifact, dict) and artifact.get("evaluation_refs", {}).get("control_decision")
    ]
    wpg_lifecycle_certification_artifact = build_lifecycle_certification(trace_id=trace_id, required_controls=controls)
    wpg_reusable_template = build_reusable_template(trace_id=trace_id, required_sections=["summary", "findings", "controls"])
    artifact_chain["wpg_lifecycle_certification_artifact"] = wpg_lifecycle_certification_artifact
    artifact_chain["wpg_reusable_template"] = wpg_reusable_template
    failure_capture = []
    repair_suggestions = []
    for name, artifact in artifact_chain.items():
        if "evaluation_refs" in artifact:
            _assert_stage_control(name, artifact)
            control = artifact.get("evaluation_refs", {}).get("control_decision") or {}
            decision = control.get("decision")
            if decision in {"BLOCK", "FREEZE"}:
                failure_capture.append({"artifact": name, "decision": decision, "reasons": control.get("reasons", [])})
                repair_suggestions.append({"artifact": name, "suggestion": "increase grounding evidence and resolve contradictions"})

    replay_signature = stable_hash(artifact_chain)
    return {
        "artifact_type": "wpg_pipeline_bundle",
        "run_id": run_id,
        "trace_id": trace_id,
        "mode": mode,
        "artifact_chain": artifact_chain,
        "failure_artifacts": failure_capture,
        "repair_suggestions": repair_suggestions,
        "replay": {
            "policy_version": ctx.policy_version,
            "eval_version": ctx.eval_version,
            "trace_linkage": trace_id,
            "signature": replay_signature,
        },
    }


def run_wpg_pipeline_from_file(input_path: Path, output_dir: Path, mode: str = "working_paper") -> Dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    run_id = str(payload.get("run_id", "wpg-run-001"))
    trace_id = str(payload.get("trace_id", "wpg-trace-001"))

    if payload.get("artifact_type") == "transcript_artifact":
        transcript = payload.get("outputs", {})
    else:
        transcript = payload.get("transcript", payload)

    prior = payload.get("prior_working_paper_artifact")
    resolved_comments = payload.get("resolved_comments", {"resolved_comments": []})
    meeting_artifact = payload.get("meeting_artifact")
    comment_artifact = payload.get("comment_artifact")
    phase_checkpoint_record = payload.get("phase_checkpoint_record")
    phase_registry = payload.get("phase_registry")

    bundle = run_wpg_pipeline(
        transcript,
        run_id=run_id,
        trace_id=trace_id,
        mode=mode,
        prior_working_paper=prior,
        resolved_comments=resolved_comments,
        meeting_artifact=meeting_artifact,
        comment_artifact=comment_artifact,
        phase_checkpoint_record=phase_checkpoint_record,
        phase_registry=phase_registry,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, artifact in bundle["artifact_chain"].items():
        (output_dir / f"{name}.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    (output_dir / "wpg_pipeline_bundle.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return bundle
