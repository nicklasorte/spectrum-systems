"""Contract preflight pytest selection target for AEX-PQX-DASH-01.

Validates:

- artifacts/dashboard_metrics/ai_programming_governed_path_record.json exists,
  parses, and carries the required envelope fields
- the artifact is owner_system MET, data_source artifact_store
- ai_programming_work_items each declare agent_type, repo_mutating, and
  AEX/PQX/EVL/CDE/SEL/lineage observations
- the artifact does not assert AEX/PQX/EVL/CDE/SEL authority on behalf of MET
- the dashboard API route exposes ai_programming_governed_path
- the dashboard page renders the AI Programming Governed Path panel
- the helper module exists and uses authority-neutral vocabulary
- the review doc exists and is authority-neutral
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
HELPER_PATH = DASHBOARD_DIR / "lib" / "aiProgrammingGovernance.ts"

ARTIFACT_PATH = METRICS_DIR / "ai_programming_governed_path_record.json"
REVIEW_DOC_NAME = "AEX-PQX-DASH-01-ai-programming-governed-path.md"

ENVELOPE_FIELDS = (
    "artifact_type",
    "schema_version",
    "record_id",
    "created_at",
    "owner_system",
    "data_source",
    "status",
    "source_artifacts_used",
    "warnings",
    "reason_codes",
    "failure_prevented",
    "signal_improved",
    "ai_programming_work_items",
)

VALID_PRESENCE = {"present", "missing", "partial", "unknown"}
VALID_AGENTS = {"codex", "claude", "unknown_ai_agent"}
VALID_BYPASS = {
    "none",
    "aex_missing",
    "pqx_missing",
    "eval_missing",
    "lineage_missing",
    "unknown",
}
VALID_STATUS = {"warn", "block", "unknown"}
VALID_REPO_MUTATING = {True, False, "unknown"}

BANNED_AUTHORITY_FIELDS = (
    "decision",
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
    "MET admits",
    "MET executes",
    "MET admitted",
    "MET executed",
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Artifact existence and envelope shape
# --------------------------------------------------------------------------- #


def test_ai_programming_governed_path_artifact_exists_and_parses() -> None:
    assert ARTIFACT_PATH.is_file(), f"missing AI programming governed-path artifact: {ARTIFACT_PATH}"
    data = _read_json(ARTIFACT_PATH)
    assert isinstance(data, dict)


def test_ai_programming_governed_path_envelope_fields_present() -> None:
    data = _read_json(ARTIFACT_PATH)
    for field in ENVELOPE_FIELDS:
        assert field in data, f"envelope field {field!r} missing"
    assert data["owner_system"] == "MET"
    assert data["data_source"] == "artifact_store"
    assert data["status"] in VALID_STATUS
    assert isinstance(data["source_artifacts_used"], list)
    assert data["source_artifacts_used"], "empty source_artifacts_used"


def test_ai_programming_governed_path_no_banned_authority_fields() -> None:
    data = _read_json(ARTIFACT_PATH)
    top_level_keys = set(data.keys())
    for field in BANNED_AUTHORITY_FIELDS:
        assert field not in top_level_keys, (
            f"banned authority field {field!r} appears at top level"
        )


def test_ai_programming_work_items_declare_required_evidence() -> None:
    data = _read_json(ARTIFACT_PATH)
    items = data.get("ai_programming_work_items")
    assert isinstance(items, list) and items, "no AI programming work items recorded"
    for item in items:
        assert isinstance(item.get("work_item_id"), str) and item["work_item_id"]
        assert item.get("agent_type") in VALID_AGENTS
        assert item.get("repo_mutating") in VALID_REPO_MUTATING
        for key in (
            "aex_admission_observation",
            "pqx_execution_observation",
            "eval_observation",
            "control_signal_observation",
            "enforcement_or_readiness_signal_observation",
            "lineage_observation",
        ):
            assert item.get(key) in VALID_PRESENCE, (
                f"item {item.get('work_item_id')} has invalid {key}={item.get(key)!r}"
            )
        assert item.get("bypass_risk") in VALID_BYPASS
        assert isinstance(item.get("source_artifacts_used"), list)
        assert item["source_artifacts_used"], (
            f"item {item.get('work_item_id')} missing source_artifacts_used"
        )
        assert isinstance(item.get("next_recommended_input"), str) and item[
            "next_recommended_input"
        ]


def test_codex_work_item_bypass_risk_is_consistent_with_observations() -> None:
    """Validate the contract shape: any codex item declaring aex_missing /
    pqx_missing as its bypass_risk must also report a missing AEX or PQX
    observation, and vice versa. This validates fail-closed logic without
    requiring a missing-evidence sample to exist permanently in the seed —
    a fully governed artifact (all evidence present) must still pass.
    """
    data = _read_json(ARTIFACT_PATH)
    items = data.get("ai_programming_work_items") or []
    codex_items = [i for i in items if i.get("agent_type") == "codex"]
    for item in codex_items:
        bypass = item.get("bypass_risk")
        aex = item.get("aex_admission_observation")
        pqx = item.get("pqx_execution_observation")
        if bypass == "aex_missing":
            assert aex == "missing", (
                f"codex {item.get('work_item_id')} declares bypass_risk=aex_missing "
                f"but aex_admission_observation={aex!r}"
            )
        if bypass == "pqx_missing":
            assert pqx == "missing", (
                f"codex {item.get('work_item_id')} declares bypass_risk=pqx_missing "
                f"but pqx_execution_observation={pqx!r}"
            )
        # Conversely: a missing AEX or PQX must surface as a non-'none' bypass_risk.
        if item.get("repo_mutating") is True and (aex == "missing" or pqx == "missing"):
            assert bypass != "none", (
                f"codex {item.get('work_item_id')} hides missing AEX/PQX behind bypass_risk=none"
            )


def test_claude_work_item_bypass_risk_is_consistent_with_observations() -> None:
    data = _read_json(ARTIFACT_PATH)
    items = data.get("ai_programming_work_items") or []
    claude_items = [i for i in items if i.get("agent_type") == "claude"]
    for item in claude_items:
        bypass = item.get("bypass_risk")
        aex = item.get("aex_admission_observation")
        pqx = item.get("pqx_execution_observation")
        if bypass == "aex_missing":
            assert aex == "missing", (
                f"claude {item.get('work_item_id')} declares bypass_risk=aex_missing "
                f"but aex_admission_observation={aex!r}"
            )
        if bypass == "pqx_missing":
            assert pqx == "missing", (
                f"claude {item.get('work_item_id')} declares bypass_risk=pqx_missing "
                f"but pqx_execution_observation={pqx!r}"
            )
        if item.get("repo_mutating") is True and (aex == "missing" or pqx == "missing"):
            assert bypass != "none", (
                f"claude {item.get('work_item_id')} hides missing AEX/PQX behind bypass_risk=none"
            )


def test_unknown_agent_with_repo_mutation_remains_visible_not_hidden() -> None:
    data = _read_json(ARTIFACT_PATH)
    items = data.get("ai_programming_work_items") or []
    unknowns = [i for i in items if i.get("agent_type") == "unknown_ai_agent"]
    assert unknowns, "artifact must seed at least one unknown_ai_agent work item"
    for item in unknowns:
        # Unknown agents with repo mutation must keep AEX/PQX observation values
        # in {missing, partial, unknown} or 'present' if proven; never silently hidden.
        assert item.get("aex_admission_observation") in VALID_PRESENCE
        assert item.get("pqx_execution_observation") in VALID_PRESENCE


def test_artifact_does_not_claim_authority_action() -> None:
    """The MET-owned artifact must not claim AEX/PQX/EVL/CDE/SEL action."""
    text = ARTIFACT_PATH.read_text(encoding="utf-8")
    for phrase in BANNED_MET_AUTHORITY_PHRASES:
        assert phrase not in text, (
            f"AI programming governed-path artifact asserts MET authority via {phrase!r}"
        )


# --------------------------------------------------------------------------- #
# Dashboard wiring (API route, page, helper)
# --------------------------------------------------------------------------- #


def test_intelligence_route_exposes_ai_programming_governed_path_block() -> None:
    assert INTELLIGENCE_ROUTE_PATH.is_file()
    src = INTELLIGENCE_ROUTE_PATH.read_text(encoding="utf-8")
    assert "ai_programming_governed_path:" in src
    # The artifact path is referenced via the helper module's exported constant.
    assert "AI_PROGRAMMING_GOVERNED_PATH_ARTIFACT_PATH" in src
    helper_src = HELPER_PATH.read_text(encoding="utf-8")
    assert "ai_programming_governed_path_record.json" in helper_src


def test_intelligence_route_degrades_to_unknown_when_artifact_missing() -> None:
    src = INTELLIGENCE_ROUTE_PATH.read_text(encoding="utf-8")
    # The helper must be invoked so missing-artifact path returns unknown counts.
    assert "computeGovernedPathSummary(aiProgrammingGovernedPath)" in src
    assert "ai_programming_governed_path_record missing" in src


def test_dashboard_page_renders_ai_programming_governed_path_panel() -> None:
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    for testid in (
        "ai-programming-governed-path-panel",
        "ai-programming-governed-path-status",
        "ai-codex-count",
        "ai-claude-count",
        "ai-aex-present-count",
        "ai-pqx-present-count",
        "ai-bypass-risk-count",
        "ai-unknown-path-count",
        "ai-programming-top-attention",
    ):
        assert testid in src, f"dashboard page missing testId {testid}"


def test_dashboard_page_does_not_render_execute_button_for_ai_programming_panel() -> None:
    src = DASHBOARD_PAGE_PATH.read_text(encoding="utf-8")
    panel_idx = src.find("AiProgrammingGovernedPathPanel")
    assert panel_idx > -1
    # The component renders no button labelled Execute. We assert by absence of
    # the literal "Execute" word inside the component definition.
    end_marker = src.find("\n}\n", panel_idx)
    component_src = src[panel_idx : end_marker if end_marker > 0 else panel_idx + 4000]
    assert "Execute" not in component_src
    assert "execute" not in component_src.lower() or "execution" in component_src.lower()


def test_helper_module_exists_and_uses_neutral_vocabulary() -> None:
    assert HELPER_PATH.is_file()
    src = HELPER_PATH.read_text(encoding="utf-8")
    # Helper must clearly declare authority neutrality.
    assert "MET" in src
    assert "AEX" in src
    assert "PQX" in src
    # No authority claims by MET.
    for phrase in BANNED_MET_AUTHORITY_PHRASES:
        assert phrase not in src, f"helper module asserts MET authority via {phrase!r}"


# --------------------------------------------------------------------------- #
# Review doc presence + authority discipline
# --------------------------------------------------------------------------- #


def test_review_doc_exists() -> None:
    assert (REVIEWS_DIR / REVIEW_DOC_NAME).is_file(), f"missing review doc: {REVIEW_DOC_NAME}"


def test_review_doc_is_authority_neutral() -> None:
    content = (REVIEWS_DIR / REVIEW_DOC_NAME).read_text(encoding="utf-8")
    for phrase in BANNED_MET_AUTHORITY_PHRASES:
        assert phrase not in content, f"review doc asserts MET authority via {phrase!r}"
    # Must explicitly attribute authority to AEX/PQX/EVL/CDE/SEL.
    assert "AEX owns admission" in content
    assert "PQX owns execution" in content
    assert "EVL owns eval" in content
    assert "CDE owns control" in content
    assert "SEL owns enforcement" in content
