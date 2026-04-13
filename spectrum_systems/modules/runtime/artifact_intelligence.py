"""Artifact intelligence MVP helpers."""

from __future__ import annotations


def build_override_hotspot_report(*, overrides_by_surface: dict[str, int]) -> dict[str, object]:
    ranked = sorted(overrides_by_surface.items(), key=lambda item: item[1], reverse=True)
    return {"artifact_type": "override_hotspot_report", "hotspots": ranked}


def build_evidence_gap_hotspot_report(*, gaps_by_surface: dict[str, int]) -> dict[str, object]:
    ranked = sorted(gaps_by_surface.items(), key=lambda item: item[1], reverse=True)
    return {"artifact_type": "evidence_gap_hotspot_report", "hotspots": ranked}


def build_trust_posture_snapshot(*, unresolved_overrides: int, missing_evidence: int) -> dict[str, object]:
    posture = "healthy" if unresolved_overrides == 0 and missing_evidence == 0 else "at_risk"
    return {
        "artifact_type": "trust_posture_snapshot",
        "posture": posture,
        "unresolved_overrides": unresolved_overrides,
        "missing_evidence": missing_evidence,
    }
