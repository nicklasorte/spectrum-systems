from __future__ import annotations


def evaluate_rfx_module_elimination(*, modules: list[dict]) -> dict:
    reason = []
    recommendations = []
    ownership_index: dict[str, str] = {}

    for module in modules:
        impacts = module.get("impacts", [])
        responsibility = str(module.get("responsibility") or "").strip().lower()
        module_name = module.get("module")

        if not impacts:
            reason.append("rfx_module_unjustified")
            recommendation = "review"
        elif "breaks_loop" in impacts:
            reason.append("rfx_module_removal_breaks_loop")
            recommendation = "keep"
        elif "debug_loss" in impacts:
            reason.append("rfx_module_removal_reduces_debuggability")
            recommendation = "keep"
        elif "signal_loss" in impacts:
            reason.append("rfx_module_removal_reduces_signal")
            recommendation = "keep"
        else:
            recommendation = "deprecate"

        if responsibility:
            owner = ownership_index.get(responsibility)
            if owner and owner != module_name:
                reason.append("rfx_module_responsibility_duplicate")
                recommendation = "review"
            ownership_index[responsibility] = module_name

        recommendations.append({"module": module_name, "recommendation": recommendation})

    return {
        "artifact_type": "rfx_module_elimination_result",
        "schema_version": "1.0.0",
        "recommendations": recommendations,
        "reason_codes_emitted": sorted(set(reason)),
        "signals": {
            "module_justification_coverage": 100.0 * sum(1 for m in modules if m.get("impacts")) / max(len(modules), 1),
            "removable_module_count": sum(1 for item in recommendations if item["recommendation"] == "deprecate"),
            "duplicate_responsibility_count": reason.count("rfx_module_responsibility_duplicate"),
        },
    }
