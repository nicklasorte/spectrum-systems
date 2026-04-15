from __future__ import annotations

from typing import Dict, List

from spectrum_systems.modules.wpg.common import (
    StageContext,
    control_decision_from_eval,
    ensure_contract,
    make_eval_artifacts,
    stage_provenance,
)


def write_sections(faq_cluster_artifact: Dict, ctx: StageContext) -> Dict:
    clusters = faq_cluster_artifact.get("outputs", {}).get("clusters", [])
    sections: List[Dict] = []
    previous_theme = None
    for idx, cluster in enumerate(clusters, start=1):
        theme = cluster["theme"]
        sorted_items = sorted(cluster.get("items", []), key=lambda item: item.get("question", ""))
        intro = f"Section {idx} introduces the {theme} perspective with evidence-ordered claims."
        bullets = [f"Q: {item['question']} A: {item['answer']}" for item in sorted_items]
        transition = (
            f"Causal handoff: {theme} constraints shape {clusters[idx]['theme']} execution risk."
            if idx < len(clusters)
            else "This closes the narrative chain and preserves chronology to the end-state."
        )
        chronology = {
            "position": idx,
            "previous_theme": previous_theme,
            "current_theme": theme,
            "justification": "Ordered by cluster evidence and cross-theme dependency.",
        }
        sections.append(
            {
                "section_id": f"S{idx:02d}",
                "title": f"{theme.title()} Synthesis",
                "intro": intro,
                "body_points": bullets,
                "transition": transition,
                "chronology": chronology,
            }
        )
        previous_theme = theme

    eval_pack = make_eval_artifacts(
        "section_writing",
        [
            {
                "description": "section coherence",
                "passed": all(s["body_points"] for s in sections),
                "failure_mode": "section_empty",
            },
            {
                "description": "narrative flow",
                "passed": all(bool(s["transition"]) for s in sections),
                "failure_mode": "missing_transition",
            },
            {
                "description": "chronology includes explicit justification",
                "passed": all(bool(s.get("chronology", {}).get("justification")) for s in sections),
                "failure_mode": "missing_chronology_justification",
            },
        ],
        ctx,
    )
    control = control_decision_from_eval(
        stage="section_writing",
        eval_summary=eval_pack["eval_summary"],
        no_content=len(sections) == 0,
    )

    artifact = {
        "artifact_type": "working_section_artifact",
        "schema_version": "1.0.0",
        "trace_id": ctx.trace_id,
        "inputs_ref": ["faq_cluster_artifact"],
        "outputs": {"sections": sections},
        "provenance": stage_provenance("section_writing", ctx, ["faq_cluster_artifact"]),
        "evaluation_refs": {**eval_pack, "control_decision": control},
    }
    return ensure_contract(artifact, "working_section_artifact")
