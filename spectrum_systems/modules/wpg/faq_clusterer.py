from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from spectrum_systems.modules.wpg.common import StageContext, ensure_contract, make_eval_artifacts, stage_provenance


THEMES = {
    "policy": ("policy", "compliance", "rule"),
    "technical": ("interference", "model", "data", "signal"),
    "operations": ("deploy", "operation", "timeline", "owner"),
}


def _theme(question: str) -> str:
    low = question.lower()
    for name, words in THEMES.items():
        if any(w in low for w in words):
            return name
    return "general"


def cluster_faqs(faq_report_artifact: Dict, ctx: StageContext) -> Dict[str, Dict]:
    rows = faq_report_artifact.get("outputs", {}).get("report_rows", [])
    buckets: Dict[str, List[Dict]] = defaultdict(list)
    unknowns: List[Dict] = []
    for row in rows:
        theme = _theme(row["question"])
        buckets[theme].append(row)
        if "unknown" in row["answer"].lower() or "no explicit" in row["answer"].lower():
            unknowns.append({"question": row["question"], "reason": "unresolved answer"})

    clusters = [{"cluster_id": f"cluster-{name}", "theme": name, "items": items} for name, items in sorted(buckets.items())]

    eval_pack = make_eval_artifacts(
        "faq_clustering",
        [
            {"description": "cluster output exists", "passed": len(clusters) > 0, "failure_mode": "no_content"},
            {"description": "no empty clusters", "passed": all(len(c["items"]) > 0 for c in clusters)},
        ],
        ctx,
    )

    cluster_artifact = ensure_contract(
        {
            "artifact_type": "faq_cluster_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "inputs_ref": ["faq_report_artifact"],
            "outputs": {"clusters": clusters},
            "provenance": stage_provenance("faq_clustering", ctx, ["faq_report_artifact"]),
            "evaluation_refs": eval_pack,
        },
        "faq_cluster_artifact",
    )

    unknowns_artifact = ensure_contract(
        {
            "artifact_type": "unknowns_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "inputs_ref": ["faq_cluster_artifact"],
            "outputs": {"unknowns": unknowns},
            "provenance": stage_provenance("unknowns_generation", ctx, ["faq_cluster_artifact"]),
            "evaluation_refs": eval_pack,
        },
        "unknowns_artifact",
    )
    return {"faq_cluster_artifact": cluster_artifact, "unknowns_artifact": unknowns_artifact}
