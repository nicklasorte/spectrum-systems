"""Contract preflight pytest selection target for MET-04-18.

This file exists primarily to give contract preflight a repo-level pytest
selection for the MET-04-18 changed artifacts/docs. It validates that:

- every MET-04-18 artifact JSON file exists and parses
- envelope fields and `failure_prevented` / `signal_improved` are present
  on artifacts that justify themselves by those fields
- candidate records remain `proposed` (no adoption claim)
- override audit log holds at `override_count: "unknown"` rather than 0
- review docs for MET-07/08/14/15/16/17/18 + final integration review exist
- the dashboard API route source references the new MET-04+ blocks
- no banned authority field/value tokens appear in MET-owned artifact
  envelopes outside canonical-owner descriptions

The dashboard-side jest tests at
``apps/dashboard-3ls/__tests__/api/met-04-18-*.test.ts`` are the binding
end-to-end check; this pytest file gives the contract preflight a deterministic
selection target so non-Python MET-04-18 changes are observable in pytest
selection integrity.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
METRICS_DIR = REPO_ROOT / "artifacts" / "dashboard_metrics"
CASES_DIR = REPO_ROOT / "artifacts" / "dashboard_cases"
REVIEWS_DIR = REPO_ROOT / "docs" / "reviews"
DASHBOARD_DIR = REPO_ROOT / "apps" / "dashboard-3ls"
INTELLIGENCE_ROUTE_PATH = DASHBOARD_DIR / "app" / "api" / "intelligence" / "route.ts"
DASHBOARD_PAGE_PATH = DASHBOARD_DIR / "app" / "page.tsx"

MET_04_18_ARTIFACT_FILES = (
    "failure_feedback_record.json",
    "eval_candidate_record.json",
    "policy_candidate_signal_record.json",
    "feedback_loop_snapshot.json",
    "failure_explanation_packets.json",
    "override_audit_log_record.json",
    "eval_materialization_path_record.json",
    "replay_lineage_hardening_record.json",
    "fallback_reduction_plan_record.json",
    "sel_compliance_signal_input_record.json",
)

ENVELOPE_FIELDS = (
    "artifact_type",
    "schema_version",
    "record_id",
    "created_at",
    "owner_system",
    "data_source",
    "source_artifacts_used",
    "reason_codes",
    "status",
    "warnings",
)

REVIEW_DOCS = (
    "MET-07-learning-loop-truth-redteam.md",
    "MET-08-learning-loop-fixes.md",
    "MET-14-removable-metric-system-audit.md",
    "MET-15-core-loop-strength-redteam.md",
    "MET-16-core-loop-fixes.md",
    "MET-17-dashboard-usefulness-redteam.md",
    "MET-18-dashboard-usefulness-fixes.md",
    "MET-04-18-final-integration-review.md",
)

API_BLOCK_FIELD_NAMES = (
    "feedback_loop:",
    "feedback_loop_status:",
    "unresolved_feedback_count:",
    "eval_candidates:",
    "policy_candidate_signals:",
    "failure_explanation_packets:",
    "override_audit:",
    "eval_materialization_path:",
    "additional_cases_summary:",
    "replay_lineage_hardening:",
    "fallback_reduction_plan:",
    "sel_compliance_signal_input:",
)

BANNED_AUTHORITY_FIELDS = (
    "enforcement_action",
    "certification_status",
    "certified",
    "promoted",
    "promotion_ready",
)

BANNED_MET_AUTHORITY_PHRASES = (
    "MET decides",
    "MET will decide",
    "MET enforces",
    "MET will enforce",
    "MET certifies",
    "MET will certify",
    "MET promotes",
    "MET will promote",
    "MET adopts",
    "MET will adopt",
    "MET approves",
    "MET will approve",
    "MET approval",
    "MET decision",
    "MET enforcement",
    "MET certification",
    "MET promotion",
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Artifact existence and envelope shape
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("filename", MET_04_18_ARTIFACT_FILES)
def test_met_04_18_artifact_exists_and_parses(filename: str) -> None:
    path = METRICS_DIR / filename
    assert path.is_file(), f"missing MET-04-18 artifact: {path}"
    data = _read_json(path)
    assert isinstance(data, dict), f"artifact must be a JSON object: {path}"


@pytest.mark.parametrize("filename", MET_04_18_ARTIFACT_FILES)
def test_met_04_18_artifact_envelope_fields_present(filename: str) -> None:
    data = _read_json(METRICS_DIR / filename)
    for field in ENVELOPE_FIELDS:
        assert field in data, f"envelope field {field!r} missing from {filename}"
    assert data["owner_system"] == "MET"
    assert data["data_source"] == "artifact_store"
    assert data["status"] in {"warn", "partial", "unknown"}
    assert isinstance(data["source_artifacts_used"], list)
    assert data["source_artifacts_used"], f"empty source_artifacts_used in {filename}"


@pytest.mark.parametrize("filename", MET_04_18_ARTIFACT_FILES)
def test_met_04_18_artifact_failure_prevented_and_signal_improved(filename: str) -> None:
    data = _read_json(METRICS_DIR / filename)
    assert isinstance(data.get("failure_prevented"), str) and data["failure_prevented"], (
        f"failure_prevented missing or empty in {filename}"
    )
    assert isinstance(data.get("signal_improved"), str) and data["signal_improved"], (
        f"signal_improved missing or empty in {filename}"
    )


@pytest.mark.parametrize("filename", MET_04_18_ARTIFACT_FILES)
def test_met_04_18_artifact_envelope_no_banned_authority_fields(filename: str) -> None:
    data = _read_json(METRICS_DIR / filename)
    top_level_keys = set(data.keys())
    for field in BANNED_AUTHORITY_FIELDS:
        assert field not in top_level_keys, (
            f"banned authority field {field!r} appears at top level of {filename}"
        )


# --------------------------------------------------------------------------- #
# Candidate-stays-proposed invariants
# --------------------------------------------------------------------------- #


def test_eval_candidates_remain_proposed_and_owner_recommendation_evl() -> None:
    data = _read_json(METRICS_DIR / "eval_candidate_record.json")
    candidates = data.get("candidates")
    assert isinstance(candidates, list) and candidates
    for candidate in candidates:
        assert candidate.get("status") == "proposed"
        assert candidate.get("owner_recommendation") == "EVL"
        assert candidate.get("candidate_eval_type") in {
            "schema_conformance",
            "evidence_coverage",
            "trace_completeness",
            "replay_consistency",
            "authority_boundary",
            "dashboard_truth",
        }
        assert isinstance(candidate.get("source_artifacts_used"), list)
        assert candidate["source_artifacts_used"]


def test_policy_candidate_signals_remain_proposed_with_owner_and_evidence() -> None:
    data = _read_json(METRICS_DIR / "policy_candidate_signal_record.json")
    candidates = data.get("candidates")
    assert isinstance(candidates, list) and candidates
    for candidate in candidates:
        assert candidate.get("status") == "proposed"
        assert candidate.get("suggested_owner_system") in {"TPA", "CDE", "SEL", "GOV"}
        assert isinstance(candidate.get("required_evidence_before_adoption"), list)
        assert isinstance(candidate.get("source_artifacts_used"), list)
        assert candidate["source_artifacts_used"]


def test_eval_materialization_path_is_proposed() -> None:
    data = _read_json(METRICS_DIR / "eval_materialization_path_record.json")
    assert data.get("materialization_status") == "proposed"
    assert data.get("owner_recommendation") == "EVL"
    assert isinstance(data.get("required_authority_inputs"), list)
    assert data["required_authority_inputs"]
    assert isinstance(data.get("required_artifacts_before_materialization"), list)
    assert isinstance(data.get("required_tests"), list)


def test_failure_feedback_items_link_to_known_source_types() -> None:
    data = _read_json(METRICS_DIR / "failure_feedback_record.json")
    items = data.get("feedback_items")
    assert isinstance(items, list) and items
    valid_source_types = {"failure_mode", "near_miss", "leverage_item"}
    valid_feedback_status = {
        "proposed",
        "materialized",
        "rejected",
        "superseded",
        "expired",
        "unknown",
    }
    for item in items:
        assert item.get("source_type") in valid_source_types
        assert item.get("feedback_status") in valid_feedback_status
        assert isinstance(item.get("source_artifacts_used"), list)
        assert item["source_artifacts_used"]


# --------------------------------------------------------------------------- #
# Override + cases invariants
# --------------------------------------------------------------------------- #


def test_override_audit_log_holds_at_unknown_without_history() -> None:
    data = _read_json(METRICS_DIR / "override_audit_log_record.json")
    assert data.get("override_count") == "unknown"
    assert "override_history_missing" in (data.get("reason_codes") or [])
    assert isinstance(data.get("overrides"), list)
    assert data["overrides"] == []
    assert data.get("next_recommended_input")


def test_dashboard_cases_index_lists_three_or_more_comparable_cases() -> None:
    index_path = CASES_DIR / "case_index_record.json"
    assert index_path.is_file()
    index = _read_json(index_path)
    cases = index.get("cases")
    assert isinstance(cases, list)
    assert len(cases) >= 3, "expected at least 3 comparable artifact-backed cases"
    reason_codes = index.get("reason_codes") or []
    assert "trend_remains_unknown_below_three_comparable_cases" in reason_codes


@pytest.mark.parametrize(
    "case_filename",
    (
        "case_eval_gap_001.json",
        "case_replay_gap_001.json",
        "case_cert_incomplete_001.json",
    ),
)
def test_dashboard_case_ties_to_real_failure_or_near_miss_or_leverage(case_filename: str) -> None:
    data = _read_json(CASES_DIR / case_filename)
    assert data.get("owner_system") == "MET"
    assert data.get("data_source") == "artifact_store"
    assert data.get("status") in {"warn", "partial", "unknown"}
    ties = (
        data.get("ties_to_failure_mode"),
        data.get("ties_to_near_miss"),
        data.get("ties_to_leverage_item"),
    )
    assert any(isinstance(tie, str) and tie for tie in ties), (
        f"case {case_filename} must tie to a real failure mode, near miss, or leverage item"
    )
    assert isinstance(data.get("failure_prevented"), str) and data["failure_prevented"]
    assert isinstance(data.get("signal_improved"), str) and data["signal_improved"]


def test_fallback_reduction_plan_targets_only_core_or_overlay_systems() -> None:
    data = _read_json(METRICS_DIR / "fallback_reduction_plan_record.json")
    items = data.get("fallback_items")
    assert isinstance(items, list) and items
    allowed_systems = {"AEX", "PQX", "EVL", "TPA", "CDE", "SEL", "REP", "LIN", "OBS", "SLO"}
    for item in items:
        assert item.get("system_id") in allowed_systems, (
            f"fallback row system_id {item.get('system_id')!r} outside core/overlay set"
        )
        assert isinstance(item.get("replacement_signal_needed"), str)
        assert item.get("priority") in {"high", "medium", "low"}
        assert isinstance(item.get("source_artifacts_used"), list)
        assert item["source_artifacts_used"]


# --------------------------------------------------------------------------- #
# Review doc presence + authority-vocabulary discipline
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("doc_name", REVIEW_DOCS)
def test_met_04_18_review_doc_exists(doc_name: str) -> None:
    assert (REVIEWS_DIR / doc_name).is_file(), f"missing MET-04-18 review doc: {doc_name}"


@pytest.mark.parametrize("doc_name", REVIEW_DOCS)
def test_met_04_18_review_doc_does_not_assert_met_authority(doc_name: str) -> None:
    content = (REVIEWS_DIR / doc_name).read_text(encoding="utf-8")
    for phrase in BANNED_MET_AUTHORITY_PHRASES:
        assert phrase not in content, (
            f"review doc {doc_name} asserts MET authority via {phrase!r}"
        )


def test_final_integration_review_carries_glossary_and_cleanup_sections() -> None:
    content = (REVIEWS_DIR / "MET-04-18-final-integration-review.md").read_text(encoding="utf-8")
    assert "Authority-neutral glossary" in content
    assert "Authority-shape cleanup result" in content
    assert "Final violation_count (after MET-04-18-FIX)" in content
    assert "Contract preflight selection repair" in content


# --------------------------------------------------------------------------- #
# Dashboard wiring (API + page)
# --------------------------------------------------------------------------- #


def test_intelligence_route_exposes_new_met_04_18_blocks() -> None:
    assert INTELLIGENCE_ROUTE_PATH.is_file()
    src = INTELLIGENCE_ROUTE_PATH.read_text(encoding="utf-8")
    for field_name in API_BLOCK_FIELD_NAMES:
        assert field_name in src, f"intelligence route missing field {field_name}"


def test_intelligence_route_does_not_substitute_zero_for_override_count() -> None:
    src = INTELLIGENCE_ROUTE_PATH.read_text(encoding="utf-8")
    assert "override_count: overrideAuditLog.override_count ?? 'unknown'" in src
    # The fail-closed path on the missing-artifact branch must report 'unknown'.
    assert "override_count: 'unknown'" in src


def test_dashboard_page_renders_compact_met_04_18_sections() -> None:
    assert DASHBOARD_PAGE_PATH.is_file()
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    for testid in (
        "learning-loop-section",
        "failure-explanation-section",
        "override-unknowns-section",
        "fallback-reduction-section",
        "replay-lineage-hardening-section",
    ):
        assert testid in src, f"dashboard page missing testId {testid}"


def test_dashboard_page_places_met_04_18_section_ids_in_diagnostics_surface() -> None:
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    diagnostics_idx = src.find("activeTab === 'diagnostics'")
    assert diagnostics_idx != -1, "dashboard page missing diagnostics tab surface"
    for testid in (
        "learning-loop-section",
        "failure-explanation-section",
        "override-unknowns-section",
        "fallback-reduction-section",
        "replay-lineage-hardening-section",
    ):
        testid_idx = src.find(testid)
        assert testid_idx > diagnostics_idx, f"expected {testid} to be rendered under diagnostics surface"


def test_dashboard_page_does_not_use_authority_shape_headings() -> None:
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    for banned in (
        "Override Decisions",
        "Approved Candidates",
        "Enforced Signals",
        "Certified Cases",
        "Promoted Cases",
        "Executed Recommendations",
    ):
        assert banned not in src, f"dashboard page uses banned heading {banned!r}"
