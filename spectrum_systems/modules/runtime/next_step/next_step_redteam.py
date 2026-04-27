from __future__ import annotations

from typing import Any

from .next_step_dependency_rules import LOCKED_SEQUENCE


def run_redteam(
    done: set[str],
    selected_id: str | None,
    missing_required: list[str],
    advisory_top: list[str],
    h01_claimed: bool = False,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(fid: str, severity: str, finding: str, reason_code: str, blocked_step: str, fix: str) -> None:
        findings.append(
            {
                "id": fid,
                "severity": severity,
                "finding": finding,
                "reason_code": reason_code,
                "blocked_step": blocked_step,
                "recommended_fix": fix,
            }
        )

    if missing_required:
        add(
            "RT-MISSING-SOURCE",
            "high",
            "Required source artifacts are missing.",
            "missing_source_artifacts",
            selected_id or "unknown",
            "Restore all required source artifacts before selecting next step.",
        )

    # Missing dependency / circular checks against locked sequence.
    order = {item.id: idx for idx, item in enumerate(LOCKED_SEQUENCE)}
    for item in LOCKED_SEQUENCE:
        for dep in item.depends_on:
            if order.get(dep, -1) >= order[item.id]:
                add(
                    "RT-CIRCULAR-DEPENDENCY",
                    "high",
                    f"Circular or invalid dependency ordering for {item.id}.",
                    "circular_dependency",
                    item.id,
                    "Repair dependency graph to strict acyclic lock ordering.",
                )
            if item.id in done and dep not in done:
                add(
                    "RT-MISSING-DEPENDENCY",
                    "high",
                    f"{item.id} marked complete without required dependency {dep}.",
                    f"missing_dependency:{item.id}:{dep}",
                    item.id,
                    f"Mark {item.id} partial or complete {dep} first.",
                )

    if "MET" in done and "RFX-PROOF-01" not in done:
        add(
            "RT-PREMATURE-MET",
            "high",
            "MET marked complete before proof-bound trust spine closure.",
            "premature_met",
            "MET",
            "Complete RFX-PROOF-01 and SEL chain before MET.",
        )

    if "HOP" in done and "MET" not in done:
        add(
            "RT-PREMATURE-HOP",
            "high",
            "HOP marked complete before MET.",
            "premature_hop",
            "HOP",
            "Complete MET first.",
        )

    if h01_claimed and not {"BLF-01", "RFX-04", "RMP-SUPER-01"}.issubset(done):
        add(
            "RT-H01-READINESS-GAP",
            "high",
            "H01 readiness claimed without BLF/RFX-04/RMP-SUPER-01 completion.",
            "h01_readiness_without_prereqs",
            "H01",
            "Complete BLF-01, RFX-04, and RMP-SUPER-01 before H01 readiness.",
        )

    if selected_id in {"EVL", "TPA", "CDE", "SEL"} and "RFX-PROOF-01" not in done:
        add(
            "RT-PREMATURE-CORE-HARDENING",
            "high",
            "Core hardening selected before RFX proof closure.",
            "premature_core_hardening_before_rfx_proof",
            selected_id,
            "Select RFX-PROOF-01 first.",
        )

    if selected_id and advisory_top and advisory_top[0] != selected_id:
        add(
            "RT-STALE-ADVISORY",
            "medium",
            "Top advisory ranking conflicts with locked dependency recommendation.",
            "stale_advisory_ranking_conflict",
            selected_id,
            "Treat advisory ranking as non-owning and follow locked dependencies.",
        )

    return findings
