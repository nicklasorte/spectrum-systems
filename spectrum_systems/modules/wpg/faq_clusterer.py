from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from spectrum_systems.modules.wpg.common import (
    StageContext,
    control_decision_from_eval,
    ensure_contract,
    jaccard_similarity,
    make_eval_artifacts,
    normalize_text_tokens,
    stage_provenance,
)

THEMES = {
    "policy": ("policy", "compliance", "rule", "governance", "ntia", "fcc", "faa"),
    "technical": ("interference", "model", "data", "signal", "spectrum", "radar"),
    "operations": ("deploy", "operation", "timeline", "owner", "milestone"),
    "defense": ("dod", "mission", "security", "defense"),
    "weather": ("noaa", "forecast", "storm", "weather"),
}


def _theme_scores(question: str, answer: str) -> Dict[str, float]:
    text_tokens = normalize_text_tokens(f"{question} {answer}")
    scores: Dict[str, float] = {}
    for theme, words in THEMES.items():
        scores[theme] = jaccard_similarity(text_tokens, set(words))
    return scores


def cluster_faqs(faq_report_artifact: Dict, ctx: StageContext) -> Dict[str, Dict]:
    rows = faq_report_artifact.get("outputs", {}).get("report_rows", [])
    buckets: Dict[str, List[Dict]] = defaultdict(list)
    unknowns: List[Dict] = []
    for row in rows:
        scores = _theme_scores(row["question"], row["answer"])
        selected = [theme for theme, score in scores.items() if score > 0.0]
        if not selected:
            selected = ["general"]
        for theme in selected:
            buckets[theme].append({**row, "cluster_score": scores.get(theme, 0.0), "cluster_labels": selected})
        if row.get("unknown") or "unknown" in row["answer"].lower() or "no explicit" in row["answer"].lower():
            unknowns.append({"question": row["question"], "reason": "unresolved answer"})

    clusters = [
        {
            "cluster_id": f"cluster-{name}",
            "theme": name,
            "items": sorted(items, key=lambda item: (-item.get("cluster_score", 0.0), item.get("question", ""))),
        }
        for name, items in sorted(buckets.items())
    ]

    eval_pack = make_eval_artifacts(
        "faq_clustering",
        [
            {"description": "cluster output exists", "passed": len(clusters) > 0, "failure_mode": "no_content"},
            {"description": "no empty clusters", "passed": all(len(c["items"]) > 0 for c in clusters)},
            {
                "description": "mixed-topic rows carry multi-label evidence or general fallback",
                "passed": all(item.get("cluster_labels") for c in clusters for item in c.get("items", [])),
                "failure_mode": "cluster_label_missing",
            },
        ],
        ctx,
    )

    control = control_decision_from_eval(
        stage="faq_clustering",
        eval_summary=eval_pack["eval_summary"],
        no_content=len(clusters) == 0,
        unknown_count=len(unknowns),
    )

    cluster_artifact = ensure_contract(
        {
            "artifact_type": "faq_cluster_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "inputs_ref": ["faq_report_artifact"],
            "outputs": {"clusters": clusters},
            "provenance": stage_provenance("faq_clustering", ctx, ["faq_report_artifact"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
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
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "unknowns_artifact",
    )
    return {"faq_cluster_artifact": cluster_artifact, "unknowns_artifact": unknowns_artifact}
