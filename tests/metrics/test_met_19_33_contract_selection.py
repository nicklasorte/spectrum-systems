"""Contract preflight pytest selection target for MET-19-33.

Validates:

- every MET-19-33 artifact JSON file exists and parses
- envelope fields, ``failure_prevented`` and ``signal_improved`` are present
- candidate closure items carry ``source_artifacts_used``
- stale items remain visible as ``stale_candidate_signal``
- trend/frequency honesty gate stays unknown until 3 comparable cases exist
- override evidence intake stays unknown/absent without a canonical log
- EVL handoff tracker uses handoff/materialization observation language only
- generated artifact classification covers MET dashboard_metrics paths
- review docs for MET-21, MET-27, MET-28, MET-29, MET-30, MET-31, MET-32,
  MET-33 exist and use authority-neutral vocabulary
- the dashboard API route exposes new compact blocks
- the dashboard page renders the new compact sections
- no banned authority field tokens appear in MET-owned artifact envelopes
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

MET_19_33_ARTIFACT_FILES = (
    "candidate_closure_ledger_record.json",
    "met_artifact_dependency_index_record.json",
    "trend_frequency_honesty_gate_record.json",
    "evl_handoff_observation_tracker_record.json",
    "override_evidence_intake_record.json",
    "debug_explanation_index_record.json",
    "met_generated_artifact_classification_record.json",
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
    "MET-21-metric-usefulness-pruning-audit.md",
    "MET-27-closure-authority-redteam.md",
    "MET-28-closure-authority-fixes.md",
    "MET-29-simplification-debuggability-redteam.md",
    "MET-30-simplification-debuggability-fixes.md",
    "MET-31-artifact-integrity-redteam.md",
    "MET-32-artifact-integrity-fixes.md",
    "MET-33-final-hardening-review.md",
)

API_BLOCK_FIELD_NAMES = (
    "candidate_closure:",
    "met_artifact_dependency_index:",
    "trend_frequency_honesty_gate:",
    "evl_handoff_observations:",
    "override_evidence_intake:",
    "debug_explanation_index:",
    "met_generated_artifact_classification:",
)

DASHBOARD_TEST_IDS = (
    "candidate-closure-section",
    "debug-explanation-index-section",
    "trend-frequency-honesty-section",
    "evl-handoff-observations-section",
    "artifact-integrity-section",
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


@pytest.mark.parametrize("filename", MET_19_33_ARTIFACT_FILES)
def test_met_19_33_artifact_exists_and_parses(filename: str) -> None:
    path = METRICS_DIR / filename
    assert path.is_file(), f"missing MET-19-33 artifact: {path}"
    data = _read_json(path)
    assert isinstance(data, dict), f"artifact must be a JSON object: {path}"


@pytest.mark.parametrize("filename", MET_19_33_ARTIFACT_FILES)
def test_met_19_33_artifact_envelope_fields_present(filename: str) -> None:
    data = _read_json(METRICS_DIR / filename)
    for field in ENVELOPE_FIELDS:
        assert field in data, f"envelope field {field!r} missing from {filename}"
    assert data["owner_system"] == "MET"
    assert data["data_source"] == "artifact_store"
    assert data["status"] in {"warn", "partial", "unknown"}
    assert isinstance(data["source_artifacts_used"], list)
    assert data["source_artifacts_used"], f"empty source_artifacts_used in {filename}"


@pytest.mark.parametrize("filename", MET_19_33_ARTIFACT_FILES)
def test_met_19_33_artifact_failure_prevented_and_signal_improved(filename: str) -> None:
    data = _read_json(METRICS_DIR / filename)
    assert isinstance(data.get("failure_prevented"), str) and data["failure_prevented"], (
        f"failure_prevented missing or empty in {filename}"
    )
    assert isinstance(data.get("signal_improved"), str) and data["signal_improved"], (
        f"signal_improved missing or empty in {filename}"
    )


@pytest.mark.parametrize("filename", MET_19_33_ARTIFACT_FILES)
def test_met_19_33_artifact_envelope_no_banned_authority_fields(filename: str) -> None:
    data = _read_json(METRICS_DIR / filename)
    top_level_keys = set(data.keys())
    for field in BANNED_AUTHORITY_FIELDS:
        assert field not in top_level_keys, (
            f"banned authority field {field!r} appears at top level of {filename}"
        )


# --------------------------------------------------------------------------- #
# MET-19 — candidate closure ledger invariants
# --------------------------------------------------------------------------- #


def test_candidate_closure_items_have_source_artifacts_used() -> None:
    data = _read_json(METRICS_DIR / "candidate_closure_ledger_record.json")
    items = data.get("candidate_items")
    assert isinstance(items, list) and items
    valid_states = {
        "proposed",
        "open",
        "materialization_observed",
        "rejected_observation",
        "superseded_observation",
        "expired_observation",
        "stale_candidate_signal",
        "unknown",
    }
    valid_types = {
        "eval_candidate",
        "policy_candidate_signal",
        "fallback_reduction_item",
        "replay_lineage_hardening_item",
        "sel_signal_input",
        "failure_feedback_item",
    }
    for item in items:
        assert isinstance(item.get("candidate_id"), str) and item["candidate_id"]
        assert item.get("candidate_type") in valid_types
        assert item.get("current_state") in valid_states
        assert isinstance(item.get("source_artifacts_used"), list)
        assert item["source_artifacts_used"], (
            f"candidate {item.get('candidate_id')} missing source_artifacts_used"
        )


def test_candidate_closure_keeps_stale_visible_not_hidden() -> None:
    data = _read_json(METRICS_DIR / "candidate_closure_ledger_record.json")
    items = data.get("candidate_items") or []
    stale_items = [i for i in items if i.get("current_state") == "stale_candidate_signal"]
    # At least one undated example surfaces as stale_candidate_signal so the
    # invariant is exercised; missing/undated items must not silently disappear.
    assert stale_items, (
        "candidate_closure_ledger_record must surface at least one stale_candidate_signal"
    )
    for item in stale_items:
        # Undated items must keep age_days as 'unknown' rather than fabricate a number.
        if item.get("age_days") not in (None, "unknown") and not isinstance(
            item["age_days"], (int, float)
        ):
            raise AssertionError(
                f"stale candidate {item.get('candidate_id')} has invalid age_days"
            )


def test_candidate_closure_does_not_claim_authority_action() -> None:
    data = _read_json(METRICS_DIR / "candidate_closure_ledger_record.json")
    items = data.get("candidate_items") or []
    forbidden_states = {"approved", "decided", "enforced", "certified", "promoted", "executed"}
    for item in items:
        assert item.get("current_state") not in forbidden_states


# --------------------------------------------------------------------------- #
# MET-22 — trend/frequency honesty gate invariants
# --------------------------------------------------------------------------- #


def test_trend_frequency_gate_required_threshold_is_three() -> None:
    data = _read_json(METRICS_DIR / "trend_frequency_honesty_gate_record.json")
    assert data.get("required_case_count_for_trend") == 3
    assert isinstance(data.get("comparable_cases"), list)


def test_trend_frequency_gate_blocks_fields_when_below_threshold() -> None:
    data = _read_json(METRICS_DIR / "trend_frequency_honesty_gate_record.json")
    breakdown = data.get("shape_breakdown") or []
    # Per-shape breakdown must keep trend_state at 'unknown' for any shape with
    # fewer than 3 cases.
    for shape in breakdown:
        if isinstance(shape.get("case_count"), int) and shape["case_count"] < 3:
            assert shape.get("trend_state") == "unknown"
    blocked = data.get("blocked_trend_fields") or []
    assert isinstance(blocked, list) and blocked, (
        "trend honesty gate must enumerate blocked_trend_fields below the threshold"
    )


# --------------------------------------------------------------------------- #
# MET-23 — EVL handoff vocabulary
# --------------------------------------------------------------------------- #


def test_evl_handoff_uses_observation_language_only() -> None:
    data = _read_json(METRICS_DIR / "evl_handoff_observation_tracker_record.json")
    items = data.get("handoff_items")
    assert isinstance(items, list) and items
    valid_observations = {"none_observed", "observed", "blocked_observation", "unknown"}
    for item in items:
        assert item.get("target_owner_recommendation") == "EVL"
        assert item.get("target_loop_leg") == "EVL"
        assert item.get("materialization_observation") in valid_observations
        assert isinstance(item.get("source_artifacts_used"), list)
        assert item["source_artifacts_used"]
        # MET must not declare EVL accepted/adopted/approved anything.
        for forbidden in (
            "accepted",
            "adopted",
            "approved",
            "certified",
            "enforced",
            "promoted",
        ):
            for value in item.values():
                if isinstance(value, str):
                    assert forbidden not in value.lower().split(), (
                        f"handoff item carries banned word {forbidden!r}: {item}"
                    )


# --------------------------------------------------------------------------- #
# MET-24 — override evidence intake stays honest
# --------------------------------------------------------------------------- #


def test_override_evidence_intake_holds_at_unknown_absent() -> None:
    data = _read_json(METRICS_DIR / "override_evidence_intake_record.json")
    assert data.get("override_evidence_count") == "unknown"
    assert data.get("evidence_status") == "absent"
    assert "override_evidence_missing" in (data.get("reason_codes") or [])
    assert isinstance(data.get("override_evidence_items"), list)
    assert data["override_evidence_items"] == []
    assert data.get("next_recommended_input")


# --------------------------------------------------------------------------- #
# MET-25 — debug explanation index invariants
# --------------------------------------------------------------------------- #


def test_debug_explanation_index_targets_under_15_minutes() -> None:
    data = _read_json(METRICS_DIR / "debug_explanation_index_record.json")
    assert data.get("debug_target_minutes") == 15
    entries = data.get("explanation_entries")
    assert isinstance(entries, list) and entries
    valid_readiness = {"sufficient", "partial", "insufficient", "unknown"}
    for entry in entries:
        assert isinstance(entry.get("explanation_id"), str)
        assert isinstance(entry.get("what_failed"), str) and entry["what_failed"]
        assert isinstance(entry.get("why"), str) and entry["why"]
        assert isinstance(entry.get("where_in_loop"), str)
        assert isinstance(entry.get("source_evidence"), list) and entry["source_evidence"]
        assert isinstance(entry.get("next_recommended_input"), str) and entry[
            "next_recommended_input"
        ]
        assert entry.get("debug_readiness") in valid_readiness


# --------------------------------------------------------------------------- #
# MET-26 — generated artifact classification covers MET paths
# --------------------------------------------------------------------------- #


def test_generated_artifact_classification_covers_met_paths() -> None:
    data = _read_json(METRICS_DIR / "met_generated_artifact_classification_record.json")
    classified = data.get("classified_paths")
    assert isinstance(classified, list) and classified
    classified_paths = {p["path"] for p in classified if isinstance(p, dict) and p.get("path")}
    # Every MET-19-33 artifact path must appear in the classification.
    for filename in MET_19_33_ARTIFACT_FILES:
        rel = f"artifacts/dashboard_metrics/{filename}"
        assert rel in classified_paths, f"MET path {rel} missing from classification"
    valid_classes = {
        "canonical_seed",
        "dashboard_metric",
        "derived_metric",
        "run_specific_generated",
        "review_artifact",
        "test_fixture",
        "unknown",
    }
    valid_policies = {
        "normal_review",
        "regenerate_not_hand_merge",
        "canonical_review_required",
        "unknown_blocked",
    }
    for entry in classified:
        assert entry.get("classification") in valid_classes, entry
        assert entry.get("merge_policy") in valid_policies, entry


# --------------------------------------------------------------------------- #
# MET-20 — dependency index covers MET-19-33 artifacts
# --------------------------------------------------------------------------- #


def test_dependency_index_covers_met_19_33_paths() -> None:
    data = _read_json(METRICS_DIR / "met_artifact_dependency_index_record.json")
    deps = data.get("artifact_dependencies")
    assert isinstance(deps, list) and deps
    paths = {d["artifact_path"] for d in deps if isinstance(d, dict)}
    # The MET-19 closure ledger and MET-20 index itself must self-reference.
    assert "artifacts/dashboard_metrics/candidate_closure_ledger_record.json" in paths
    valid_keep_fold_remove = {"keep", "fold_candidate", "remove_candidate"}
    for dep in deps:
        assert dep.get("keep_fold_remove") in valid_keep_fold_remove
        question = dep.get("debug_question_answered") or {}
        for key in (
            "what_failed",
            "why",
            "where_in_loop",
            "source_evidence",
            "next_recommended_input",
        ):
            assert key in question, f"dependency entry {dep.get('artifact_path')} missing {key}"


# --------------------------------------------------------------------------- #
# Review docs presence + authority-vocabulary discipline
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("doc_name", REVIEW_DOCS)
def test_met_19_33_review_doc_exists(doc_name: str) -> None:
    assert (REVIEWS_DIR / doc_name).is_file(), f"missing review doc: {doc_name}"


@pytest.mark.parametrize("doc_name", REVIEW_DOCS)
def test_met_19_33_review_doc_does_not_assert_met_authority(doc_name: str) -> None:
    content = (REVIEWS_DIR / doc_name).read_text(encoding="utf-8")
    for phrase in BANNED_MET_AUTHORITY_PHRASES:
        assert phrase not in content, (
            f"review doc {doc_name} asserts MET authority via {phrase!r}"
        )


# --------------------------------------------------------------------------- #
# Dashboard wiring (API + page)
# --------------------------------------------------------------------------- #


def test_intelligence_route_exposes_new_met_19_33_blocks() -> None:
    assert INTELLIGENCE_ROUTE_PATH.is_file()
    src = INTELLIGENCE_ROUTE_PATH.read_text(encoding="utf-8")
    for field_name in API_BLOCK_FIELD_NAMES:
        assert field_name in src, f"intelligence route missing field {field_name}"


def test_intelligence_route_does_not_substitute_zero_for_override_evidence_count() -> None:
    src = INTELLIGENCE_ROUTE_PATH.read_text(encoding="utf-8")
    # Truthy branch must read the artifact field with 'unknown' fallback.
    assert (
        "override_evidence_count: overrideEvidenceIntake.override_evidence_count ?? 'unknown'"
        in src
    )
    # Missing-artifact branch must pin the count to 'unknown'.
    assert "override_evidence_count: 'unknown'" in src


def test_intelligence_route_degrades_candidate_closure_to_unknown() -> None:
    src = INTELLIGENCE_ROUTE_PATH.read_text(encoding="utf-8")
    assert "candidate_item_count: 'unknown'" in src
    assert "stale_candidate_signal_count: 'unknown'" in src


def test_dashboard_page_renders_compact_met_19_33_sections() -> None:
    assert DASHBOARD_PAGE_PATH.is_file()
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    for testid in DASHBOARD_TEST_IDS:
        assert testid in src, f"dashboard page missing testId {testid}"


def test_dashboard_page_places_met_19_33_section_ids_in_diagnostics_surface() -> None:
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    diagnostics_idx = src.find("activeTab === 'diagnostics'")
    assert diagnostics_idx != -1, "dashboard page missing diagnostics tab surface"
    for testid in DASHBOARD_TEST_IDS:
        testid_idx = src.find(testid)
        assert testid_idx > diagnostics_idx, f"expected {testid} to be rendered under diagnostics surface"


def test_dashboard_page_compact_max_constant_present() -> None:
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    assert "MET_COMPACT_ITEM_MAX = 5" in src
