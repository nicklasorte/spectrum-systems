"""Tests for the TLS-BND-01 boundary map artifacts.

These tests assert the boundary map declares allowed and forbidden TLS
responsibilities, that forbidden artifact-name patterns reject candidate
names while safe owner-input names are accepted, that the red-team report
records abuse cases, and that the fixed map resolves every high-severity
finding raised by the red-team.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TLS_DIR = REPO_ROOT / "artifacts" / "tls"
BOUNDARY_MAP_PATH = TLS_DIR / "tls_boundary_map.json"
BOUNDARY_REDTEAM_PATH = TLS_DIR / "tls_boundary_redteam_report.json"
BOUNDARY_FIXED_PATH = TLS_DIR / "tls_boundary_map_fixed.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _name_blocked(name: str, patterns: list[str]) -> bool:
    lowered = name.lower()
    for pattern in patterns:
        if fnmatch.fnmatchcase(lowered, pattern.lower()):
            return True
    return False


def test_boundary_map_exists() -> None:
    assert BOUNDARY_MAP_PATH.is_file(), "tls_boundary_map.json must exist"
    assert BOUNDARY_REDTEAM_PATH.is_file(), "tls_boundary_redteam_report.json must exist"
    assert BOUNDARY_FIXED_PATH.is_file(), "tls_boundary_map_fixed.json must exist"


def test_boundary_map_has_allowed_and_forbidden_responsibilities() -> None:
    for path in (BOUNDARY_MAP_PATH, BOUNDARY_FIXED_PATH):
        payload = _load(path)
        allowed = payload.get("allowed_responsibilities", [])
        forbidden = payload.get("forbidden_responsibilities", [])
        assert allowed, f"{path.name} must declare allowed_responsibilities"
        assert forbidden, f"{path.name} must declare forbidden_responsibilities"
        allowed_names = {item["name"] for item in allowed}
        required_allowed = {
            "registry_parsing",
            "evidence_observation",
            "candidate_classification",
            "trust_gap_signal_reporting",
            "priority_ranking",
            "requested_candidate_ranking",
            "explanation_generation",
            "roadmap_backed_leverage_queue",
            "owner_input_packet_generation_only",
        }
        assert required_allowed.issubset(allowed_names), (
            f"{path.name} missing required allowed_responsibilities: "
            f"{sorted(required_allowed - allowed_names)}"
        )
        forbidden_names = {item["name"] for item in forbidden}
        required_forbidden = {
            "control_outcomes",
            "owner_approvals",
            "enforcement_actions",
            "certification_outcomes",
            "promotion_readiness_outcomes",
            "authority_decisions",
            "runtime_execution_mutation",
        }
        assert required_forbidden.issubset(forbidden_names), (
            f"{path.name} missing required forbidden_responsibilities: "
            f"{sorted(required_forbidden - forbidden_names)}"
        )


def test_forbidden_artifact_names_are_rejected() -> None:
    payload = _load(BOUNDARY_FIXED_PATH)
    patterns = payload["forbidden_artifact_name_patterns"]
    candidates = [
        "tls_control_decision_outcome.json",
        "tls_enforcement_record.json",
        "tls_approval_record.json",
        "tls_certification_status.json",
        "tls_promotion_ready.json",
        "tls_promoted_signal.json",
        "tls_authority_decision.json",
        "tls_execution_decision.json",
        "tls_closure_decision_record.json",
        "tls_judgment_record.json",
        "tls_final_decision_log.json",
    ]
    for candidate in candidates:
        assert _name_blocked(candidate, patterns), (
            f"forbidden artifact name '{candidate}' was not rejected by boundary map patterns"
        )


def test_safe_owner_input_names_are_allowed() -> None:
    payload = _load(BOUNDARY_FIXED_PATH)
    patterns = payload["forbidden_artifact_name_patterns"]
    safe_candidates = [
        "tls_owner_input_packet.json",
        "tls_ranking_review_report.json",
        "system_dependency_priority_report.json",
        "system_candidate_classification.json",
        "system_evidence_attachment.json",
        "system_trust_gap_report.json",
        "tls_roadmap_table.md",
        "tls_action_plan.json",
        "tls_boundary_map.json",
        "tls_boundary_map_fixed.json",
        "tls_boundary_redteam_report.json",
    ]
    for candidate in safe_candidates:
        assert not _name_blocked(candidate, patterns), (
            f"safe owner-input/TLS artifact name '{candidate}' was wrongly rejected"
        )


def test_redteam_report_has_abuse_cases() -> None:
    payload = _load(BOUNDARY_REDTEAM_PATH)
    cases = payload.get("abuse_cases", [])
    assert len(cases) >= 8, "red-team report must list at least 8 abuse cases"
    required_fields = {
        "abuse_case_id",
        "attempted_violation",
        "expected_result",
        "observed_result",
        "finding_severity",
        "recommended_fix",
    }
    for case in cases:
        missing = required_fields - set(case)
        assert not missing, f"abuse case missing fields: {sorted(missing)}"
    severities = {case["finding_severity"] for case in cases}
    assert "high" in severities, "red-team report must include at least one high-severity finding"


def test_fixed_map_resolves_high_severity_findings() -> None:
    redteam = _load(BOUNDARY_REDTEAM_PATH)
    fixed = _load(BOUNDARY_FIXED_PATH)
    high_severity_ids = {
        case["abuse_case_id"]
        for case in redteam.get("abuse_cases", [])
        if case.get("finding_severity") == "high"
    }
    fix_ids = {entry["finding_id"] for entry in fixed.get("fixes_applied", [])}
    missing = high_severity_ids - fix_ids
    assert not missing, f"fixed boundary map missing fix entries for high-severity findings: {sorted(missing)}"
    for entry in fixed.get("fixes_applied", []):
        if entry["finding_id"] in high_severity_ids:
            assert entry.get("status") == "fixed", (
                f"high-severity finding {entry['finding_id']} not marked fixed"
            )


def test_boundary_map_declares_recommendation_only() -> None:
    for path in (BOUNDARY_MAP_PATH, BOUNDARY_FIXED_PATH):
        payload = _load(path)
        assert payload.get("recommendation_only") is True, (
            f"{path.name} must declare recommendation_only=true"
        )
        assert payload.get("owner_outcome_present") is False, (
            f"{path.name} must declare owner_outcome_present=false"
        )


def test_fixed_map_has_field_and_value_policies() -> None:
    payload = _load(BOUNDARY_FIXED_PATH)
    assert payload.get("forbidden_field_patterns"), "fixed map must list forbidden_field_patterns"
    assert payload.get("forbidden_value_patterns"), "fixed map must list forbidden_value_patterns"
    assert payload.get("forbidden_text_phrases"), "fixed map must list forbidden_text_phrases"
    assert payload.get("forbidden_action_verbs"), "fixed map must list forbidden_action_verbs"
    field_policy = payload.get("owner_input_packet_field_policy")
    assert field_policy, "fixed map must include owner_input_packet_field_policy"
    assert field_policy.get("allowed_owner_input_fields"), "field policy must list allowed fields"
    assert field_policy.get("forbidden_owner_outcome_fields"), "field policy must list forbidden owner outcome fields"
    required = field_policy.get("required_assertions", {})
    assert required.get("recommendation_only") is True
    assert required.get("owner_outcome_present") is False


def test_owner_input_packet_complies_with_field_policy() -> None:
    """The existing TLS owner-input packet must satisfy the fixed-map field policy."""
    packet_path = TLS_DIR / "tls_owner_input_packet.json"
    if not packet_path.is_file():
        return
    packet = _load(packet_path)
    fixed = _load(BOUNDARY_FIXED_PATH)
    policy = fixed["owner_input_packet_field_policy"]
    forbidden = set(policy["forbidden_owner_outcome_fields"])
    leaked = sorted(set(packet.keys()) & forbidden)
    assert not leaked, f"owner-input packet contains forbidden owner-outcome fields: {leaked}"
    assert packet.get("recommendation_only") is True, (
        "owner-input packet must declare recommendation_only=true"
    )
    assert packet.get("owner_outcome_present") is False, (
        "owner-input packet must declare owner_outcome_present=false"
    )
