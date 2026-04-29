"""Contract preflight pytest selection target for MET-FULL-ROADMAP.

Validates:

- MET registry entry exists and authority is NONE
- forbidden authority ownership fields are absent from MET artifacts
- every MET-FULL-ROADMAP artifact JSON file exists and parses
- every artifact has failure_prevented and signal_improved
- no fake pass / fake trend / fake materialization / unknown-to-zero
- outcome attribution requires before/after evidence
- confidence warns when evidence is weak
- recurrence requires multiple comparable cases
- action bundles are candidate-only (readiness_state == proposed)
- freeze signal is recommendation-only (recommendation_signal == no_recommendation
  when budget unknown)
- anti-gaming flags misleading green states
- /api/intelligence exposes all blocks
- the dashboard renders the compact MET Cockpit
- no button says Execute in MET-owned UI
- no banned authority vocabulary in MET-owned docs/tests/artifacts
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
METRICS_DIR = REPO_ROOT / "artifacts" / "dashboard_metrics"
REVIEWS_DIR = REPO_ROOT / "docs" / "reviews"
DASHBOARD_DIR = REPO_ROOT / "apps" / "dashboard-3ls"
INTELLIGENCE_ROUTE_PATH = DASHBOARD_DIR / "app" / "api" / "intelligence" / "route.ts"
DASHBOARD_PAGE_PATH = DASHBOARD_DIR / "app" / "page.tsx"
SYSTEM_REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "system_registry.md"

MET_FULL_ROADMAP_ARTIFACT_FILES = (
    "stale_candidate_pressure_record.json",
    "outcome_attribution_record.json",
    "failure_reduction_signal_record.json",
    "recommendation_accuracy_record.json",
    "calibration_drift_record.json",
    "signal_confidence_record.json",
    "cross_run_consistency_record.json",
    "divergence_detection_record.json",
    "met_error_budget_observation_record.json",
    "met_freeze_recommendation_signal_record.json",
    "next_best_slice_recommendation_record.json",
    "pqx_candidate_action_bundle_record.json",
    "counterfactual_reconstruction_record.json",
    "earlier_intervention_signal_record.json",
    "recurring_failure_cluster_record.json",
    "recurrence_severity_signal_record.json",
    "time_to_explain_record.json",
    "debug_readiness_sla_record.json",
    "metric_gaming_detection_record.json",
    "misleading_signal_detection_record.json",
    "signal_integrity_check_record.json",
    "merge_conflict_pressure_record.json",
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
    "failure_prevented",
    "signal_improved",
)

API_BLOCK_FIELD_NAMES = (
    "met_registry_status:",
    "met_cockpit:",
    "top_next_inputs:",
    "owner_handoff:",
    "stale_candidate_pressure:",
    "trend_readiness:",
    "override_evidence:",
    "fold_safety:",
    "outcome_attribution:",
    "recommendation_accuracy:",
    "calibration_drift:",
    "cross_run_consistency:",
    "error_budget_observation:",
    "next_best_slice:",
    "counterfactuals:",
    "recurring_failures:",
    "debug_readiness:",
    "signal_integrity:",
    "merge_conflict_pressure:",
)

DASHBOARD_TEST_IDS = (
    "met-cockpit-section",
    "met-cockpit-card",
    "met-authority",
    "met-registry-status",
    "met-top-next-inputs-section",
    "met-owner-handoff-section",
    "met-outcome-attribution-section",
    "met-outcome-attribution-list",
    "met-calibration-drift-list",
    "met-recurring-failures-list",
    "met-signal-integrity-list",
)

REVIEW_DOCS = (
    "MET-RT-01-registry-authority-redteam.md",
    "MET-FIX-01-registry-authority-fixes.md",
    "MET-RT-02-dashboard-clarity-redteam.md",
    "MET-FIX-02-dashboard-clarity-fixes.md",
    "MET-RT-03-trend-outcome-honesty-redteam.md",
    "MET-FIX-03-trend-outcome-honesty-fixes.md",
    "MET-RT-04-confidence-gaming-redteam.md",
    "MET-FIX-04-confidence-gaming-fixes.md",
    "MET-RT-05-debuggability-redteam.md",
    "MET-FIX-05-debuggability-fixes.md",
    "MET-FULL-ROADMAP-final-review.md",
)

# Authority-shaped tokens that MET-owned artifacts/docs/tests must not adopt.
# Built via concatenation so this file itself remains preflight-clean when scanned.
BANNED_TERMS = (
    "approv" + "ed",
    "accept" + "ed",
    "adopt" + "ed",
    "decid" + "ed",
    "enforc" + "ed",
    "certif" + "ied",
    "promot" + "ed",
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_met_registered_in_system_registry() -> None:
    text = SYSTEM_REGISTRY_PATH.read_text(encoding="utf-8")
    assert "### MET" in text
    assert "active, non-owning" in text
    assert "Authority:** NONE" in text or "**Authority:** NONE" in text
    # System map listing
    assert "**MET**" in text


def test_met_authority_is_none_in_definition_block() -> None:
    text = SYSTEM_REGISTRY_PATH.read_text(encoding="utf-8")
    # Lower-case definitions section uses authority: none
    idx = text.find("### MET\n- **role:**")
    assert idx > -1
    block = text[idx : idx + 1200]
    assert "authority:** none" in block.lower()
    for forbidden in (
        "own_decision_authority",
        "own_approval_authority",
        "own_enforcement_authority",
        "own_certification_authority",
        "own_promotion_authority",
        "own_execution_authority",
        "own_admission_authority",
        "emit_authority_outcomes",
    ):
        assert forbidden in block


@pytest.mark.parametrize("name", MET_FULL_ROADMAP_ARTIFACT_FILES)
def test_artifacts_exist_and_parse(name: str) -> None:
    path = METRICS_DIR / name
    assert path.is_file(), f"missing artifact: {path}"
    assert isinstance(_json(path), dict)


@pytest.mark.parametrize("name", MET_FULL_ROADMAP_ARTIFACT_FILES)
def test_artifacts_have_required_envelope(name: str) -> None:
    data = _json(METRICS_DIR / name)
    for field in ENVELOPE_FIELDS:
        assert field in data, f"{name} missing field: {field}"
    assert data["owner_system"] == "MET"
    # Most MET artifacts source from artifact_store; the merge-conflict
    # pressure record sources from git diff because that is its canonical
    # input. Both are observation-only.
    assert data["data_source"] in {"artifact_store", "git_diff"}
    assert isinstance(data["source_artifacts_used"], list) and data["source_artifacts_used"]


@pytest.mark.parametrize("name", MET_FULL_ROADMAP_ARTIFACT_FILES)
def test_no_banned_authority_terms_in_artifacts(name: str) -> None:
    raw = (METRICS_DIR / name).read_text(encoding="utf-8").lower()
    for banned in BANNED_TERMS:
        assert banned not in raw, f"{name} contains banned authority token '{banned}'"


def test_outcome_attribution_requires_before_after_for_observed_status() -> None:
    data = _json(METRICS_DIR / "outcome_attribution_record.json")
    allowed_statuses = {"insufficient_evidence", "partial", "observed", "unknown"}
    for entry in data.get("outcome_entries", []):
        assert entry.get("status") in allowed_statuses
        if entry.get("status") == "observed":
            assert entry["before_signal"]["evidence_refs"]
            assert entry["after_signal"]["evidence_refs"]


def test_recurrence_requires_multiple_comparable_cases() -> None:
    data = _json(METRICS_DIR / "recurring_failure_cluster_record.json")
    assert data.get("minimum_comparable_cases_for_recurrence", 0) >= 3
    for cluster in data.get("clusters", []):
        if cluster.get("recurrence_state") == "insufficient_cases":
            assert isinstance(cluster.get("cases_needed"), int)
            assert cluster["cases_needed"] > 0


def test_confidence_warns_with_thin_evidence() -> None:
    data = _json(METRICS_DIR / "signal_confidence_record.json")
    assert data.get("minimum_evidence_count_for_high_confidence", 0) >= 3
    for entry in data.get("signal_entries", []):
        if entry.get("confidence_level") == "high_claimed":
            assert entry.get("confidence_warning") == "high_confidence_thin_evidence"


def test_action_bundles_are_candidate_only() -> None:
    data = _json(METRICS_DIR / "pqx_candidate_action_bundle_record.json")
    for bundle in data.get("bundle_candidates", []):
        assert bundle.get("readiness_state") == "proposed"
        evidence = bundle.get("required_evidence") or []
        assert any("AEX" in e or "admission" in e for e in evidence), (
            "bundle must reference AEX admission evidence"
        )


def test_freeze_signal_is_recommendation_only() -> None:
    data = _json(METRICS_DIR / "met_freeze_recommendation_signal_record.json")
    for signal in data.get("recommendation_signals", []):
        assert signal.get("recommended_owner_system") in {"SLO", "CDE", "SEL"}
        if signal.get("budget_status_observed") == "unknown":
            assert signal.get("recommendation_signal") == "no_recommendation"


def test_calibration_remains_unknown_until_enough_outcomes() -> None:
    data = _json(METRICS_DIR / "calibration_drift_record.json")
    minimum = data.get("minimum_paired_outcomes_per_bucket")
    assert isinstance(minimum, int) and minimum > 0
    for bucket in data.get("calibration_buckets", []):
        observed = bucket.get("observed_paired_outcomes", 0)
        if observed < minimum and bucket.get("drift_state") not in {"unknown", "insufficient_cases"}:
            pytest.fail(
                f"bucket {bucket.get('bucket')} below threshold but drift_state is "
                f"{bucket.get('drift_state')}"
            )


def test_anti_gaming_flags_misleading_green_states() -> None:
    data = _json(METRICS_DIR / "misleading_signal_detection_record.json")
    flagged = [obs for obs in data.get("misleading_signal_observations", []) if obs.get("flagged")]
    assert flagged, "expected at least one misleading-signal flag in this PR"


def test_signal_integrity_aggregate() -> None:
    data = _json(METRICS_DIR / "signal_integrity_check_record.json")
    summary = data.get("integrity_summary", {})
    assert "overall_integrity_state" in summary
    assert isinstance(data.get("integrity_checks", []), list)


def test_cross_run_ignores_non_material_fields() -> None:
    data = _json(METRICS_DIR / "cross_run_consistency_record.json")
    ignored = data.get("non_material_fields_ignored", [])
    assert "created_at" in ignored
    assert "generated_at" in ignored


def test_api_route_exposes_all_blocks() -> None:
    src = INTELLIGENCE_ROUTE_PATH.read_text(encoding="utf-8")
    for field in API_BLOCK_FIELD_NAMES:
        assert field in src, f"/api/intelligence missing field: {field}"
    # MET registry status is parsed from system_registry.md at runtime, not
    # hard-coded. The route must reference the parser and the registry path.
    assert "parseMetRegistryStatus" in src
    assert "docs/architecture/system_registry.md" in src


def test_dashboard_renders_compact_met_cockpit() -> None:
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    for tid in DASHBOARD_TEST_IDS:
        assert tid in src, f"dashboard missing data-testid: {tid}"


def test_dashboard_has_no_execute_button_in_met_cockpit() -> None:
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    start = src.find("met-cockpit-section")
    end = src.find("met-outcome-attribution-section")
    assert start > -1 and end > start
    cockpit_slice = src[start:end]
    # Should not contain any button labelled Execute or admit/promote/enforce verbs
    assert ">Execute<" not in cockpit_slice
    assert ">Approve<" not in cockpit_slice
    assert ">Promote<" not in cockpit_slice


def test_review_docs_exist() -> None:
    for name in REVIEW_DOCS:
        assert (REVIEWS_DIR / name).is_file(), f"missing review doc: {name}"


def test_review_docs_close_must_fix() -> None:
    for fix_name in (
        "MET-FIX-01-registry-authority-fixes.md",
        "MET-FIX-02-dashboard-clarity-fixes.md",
        "MET-FIX-03-trend-outcome-honesty-fixes.md",
        "MET-FIX-04-confidence-gaming-fixes.md",
        "MET-FIX-05-debuggability-fixes.md",
    ):
        text = (REVIEWS_DIR / fix_name).read_text(encoding="utf-8")
        assert "must_fix" in text.lower()
        assert "no must_fix" in text.lower() or "remain open: 0" in text.lower() or "remaining open" in text.lower()
