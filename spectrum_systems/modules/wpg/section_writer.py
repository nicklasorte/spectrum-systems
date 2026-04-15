from __future__ import annotations

from typing import Dict, List

from spectrum_systems.modules.wpg.common import StageContext, ensure_contract, make_eval_artifacts, stage_provenance


def write_sections(faq_cluster_artifact: Dict, ctx: StageContext) -> Dict:
    clusters = faq_cluster_artifact.get("outputs", {}).get("clusters", [])
    sections: List[Dict] = []
    for idx, cluster in enumerate(clusters, start=1):
        theme = cluster["theme"]
        intro = f"Section {idx} introduces the {theme} perspective."
        bullets = [f"Q: {item['question']} A: {item['answer']}" for item in cluster.get("items", [])]
        transition = "This leads into the next section's dependencies." if idx < len(clusters) else "This closes the narrative chain."
        sections.append(
            {
                "section_id": f"S{idx:02d}",
                "title": f"{theme.title()} Synthesis",
                "intro": intro,
                "body_points": bullets,
                "transition": transition,
            }
        )

    eval_pack = make_eval_artifacts(
        "section_writing",
        [
            {"description": "section coherence", "passed": all(s["body_points"] for s in sections), "failure_mode": "section_empty"},
            {"description": "narrative flow", "passed": all(bool(s["transition"]) for s in sections), "failure_mode": "missing_transition"},
        ],
        ctx,
    )

    artifact = {
        "artifact_type": "working_section_artifact",
        "schema_version": "1.0.0",
        "trace_id": ctx.trace_id,
        "inputs_ref": ["faq_cluster_artifact"],
        "outputs": {"sections": sections},
        "provenance": stage_provenance("section_writing", ctx, ["faq_cluster_artifact"]),
        "evaluation_refs": eval_pack,
    }
    return ensure_contract(artifact, "working_section_artifact")
