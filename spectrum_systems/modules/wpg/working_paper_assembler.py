from __future__ import annotations

from typing import Dict, List

from spectrum_systems.modules.wpg.common import StageContext, ensure_contract, make_eval_artifacts, stable_hash, stage_provenance


def _render_mode(mode: str, sections: List[Dict]) -> str:
    if mode == "executive_summary":
        return "\n".join(f"- {s['title']}: {s['intro']}" for s in sections)
    if mode == "FAQ_brief":
        return "\n".join(f"- {s['title']} ({len(s['body_points'])} points)" for s in sections)
    if mode == "slide_outline":
        return "\n".join(f"Slide {i+1}: {s['title']}" for i, s in enumerate(sections))
    parts = []
    for s in sections:
        parts.append(f"{s['title']}\n{s['intro']}\n" + "\n".join(s["body_points"]) + f"\n{s['transition']}")
    return "\n\n".join(parts)


def assemble_working_paper(
    section_artifact: Dict,
    unknowns_artifact: Dict,
    faq_conflict_artifact: Dict,
    resolved_comments: Dict,
    prior_working_paper_artifact: Dict | None,
    ctx: StageContext,
    mode: str,
) -> Dict[str, Dict]:
    sections = section_artifact.get("outputs", {}).get("sections", [])
    resolved = resolved_comments.get("resolved_comments", []) if isinstance(resolved_comments, dict) else []
    unknowns = unknowns_artifact.get("outputs", {}).get("unknowns", [])
    conflicts = faq_conflict_artifact.get("outputs", {}).get("conflicts", [])

    content = _render_mode(mode, sections)
    if resolved:
        content += "\n\nResolved comments incorporated:\n" + "\n".join(f"- {c['comment_id']}: {c['resolution']}" for c in resolved)

    eval_pack = make_eval_artifacts(
        "working_paper_assembly",
        [{"description": "narrative content exists", "passed": bool(content.strip()), "failure_mode": "no_content"}],
        ctx,
    )

    working_paper = ensure_contract(
        {
            "artifact_type": "working_paper_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "inputs_ref": ["working_section_artifact", "unknowns_artifact", "faq_conflict_artifact"],
            "outputs": {
                "mode": mode,
                "title": "Governed Working Paper",
                "content": content,
                "sections": sections,
                "unknowns": unknowns,
                "conflicts": conflicts,
                "resolved_comments": resolved,
            },
            "provenance": stage_provenance("working_paper_assembly", ctx, ["working_section_artifact"]),
            "evaluation_refs": eval_pack,
        },
        "working_paper_artifact",
    )

    prev_hash = stable_hash(prior_working_paper_artifact["outputs"]) if prior_working_paper_artifact else ""
    curr_hash = stable_hash(working_paper["outputs"])
    delta = ensure_contract(
        {
            "artifact_type": "wpg_delta_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "inputs_ref": ["working_paper_artifact"],
            "outputs": {
                "previous_hash": prev_hash,
                "current_hash": curr_hash,
                "changed": prev_hash != curr_hash,
            },
            "provenance": stage_provenance("delta_tracking", ctx, ["working_paper_artifact"]),
            "evaluation_refs": eval_pack,
        },
        "wpg_delta_artifact",
    )
    return {"working_paper_artifact": working_paper, "wpg_delta_artifact": delta}
