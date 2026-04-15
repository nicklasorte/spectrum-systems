from __future__ import annotations

from typing import Dict

from spectrum_systems.modules.wpg.common import StageContext, ensure_contract, make_eval_artifacts, stage_provenance


VALID_MODES = {"working_paper", "executive_summary", "FAQ_brief", "slide_outline"}


def format_faq_for_report(faq_artifact: Dict, ctx: StageContext, mode: str = "working_paper") -> Dict:
    if mode not in VALID_MODES:
        raise ValueError(f"unsupported mode: {mode}")

    faqs = faq_artifact.get("outputs", {}).get("faqs", [])
    rows = []
    for item in faqs:
        rows.append(
            {
                "question": item["question"],
                "answer": item["synthesis"],
                "source_trace": item.get("sources", []),
                "mode": mode,
            }
        )

    eval_pack = make_eval_artifacts(
        "faq_formatting",
        [{"description": "report rows generated", "passed": len(rows) > 0, "failure_mode": "no_content"}],
        ctx,
    )

    artifact = {
        "artifact_type": "faq_report_artifact",
        "schema_version": "1.0.0",
        "trace_id": ctx.trace_id,
        "inputs_ref": ["faq_artifact"],
        "outputs": {"mode": mode, "report_rows": rows},
        "provenance": stage_provenance("faq_formatting", ctx, ["faq_artifact"]),
        "evaluation_refs": eval_pack,
    }
    return ensure_contract(artifact, "faq_report_artifact")
