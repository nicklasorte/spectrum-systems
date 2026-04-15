from __future__ import annotations

from typing import Any, Dict, List

from spectrum_systems.modules.wpg.common import StageContext, control_decision_from_eval, ensure_contract, make_eval_artifacts


def run_multi_pass_critique(
    *,
    sections_artifact: Dict[str, Any],
    agency_profile: Dict[str, Any],
    industry_profile: Dict[str, Any],
    ctx: StageContext,
) -> Dict[str, Any]:
    sections = sections_artifact.get("outputs", {}).get("sections", [])
    agency_profiles = agency_profile.get("outputs", {}).get("profiles", [])
    industry_objections = industry_profile.get("outputs", {}).get("objections", [])

    findings: List[Dict[str, Any]] = []
    for section in sections:
        title = str(section.get("title", "untitled"))
        agency_hits = [p for p in agency_profiles if p.get("recurring_objections")]
        industry_hits = [o for o in industry_objections if int(o.get("count", 0)) > 0]
        severity = "high" if agency_hits and industry_hits else "medium" if (agency_hits or industry_hits) else "low"
        findings.append(
            {
                "section_title": title,
                "agency_critique": [p.get("top_resolution_pattern") for p in agency_hits],
                "industry_critique": [o.get("theme") for o in industry_hits],
                "editorial_synthesis": f"Resolve critique hotspots for section '{title}'.",
                "severity": severity,
            }
        )

    high_count = sum(1 for row in findings if row["severity"] == "high")
    eval_pack = make_eval_artifacts(
        "multi_pass_critique",
        [
            {"description": "critique findings emitted", "passed": len(findings) > 0, "failure_mode": "missing_critique_findings"},
            {"description": "high critique bounded", "passed": high_count == 0, "failure_mode": "high_severity_critique"},
        ],
        ctx,
    )
    control = control_decision_from_eval(stage="multi_pass_critique", eval_summary=eval_pack["eval_summary"])
    if high_count > 0:
        control["decision"] = "BLOCK"
        control["reasons"] = sorted(set(control.get("reasons", []) + ["high_severity_critique"]))
        control["enforcement"] = {"action": "trigger_repair"}

    return ensure_contract(
        {
            "artifact_type": "stakeholder_critique_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "outputs": {"findings": findings, "high_severity_count": high_count},
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "stakeholder_critique_artifact",
    )
