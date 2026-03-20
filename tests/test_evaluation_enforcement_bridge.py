"""Tests for BU — Governor Enforcement Bridge (evaluation_enforcement_bridge.py).

Covers:
 1.  load_budget_decision loads a valid decision
 2.  load_budget_decision raises on missing file
 3.  load_budget_decision raises InvalidDecisionError on invalid JSON structure
 4.  validate_budget_decision returns empty list for valid decision
 5.  validate_budget_decision returns errors for invalid decision
 6.  validate_enforcement_action returns empty list for valid action
 7.  validate_enforcement_action returns errors for invalid action
 8.  determine_enforcement_scope defaults to 'release' when no context
 9.  determine_enforcement_scope reads scope from context
10.  determine_enforcement_scope falls back to default on unknown scope
11.  enforce_budget_decision — allow → advisory allow, allowed_to_proceed=True
12.  enforce_budget_decision — allow_with_warning → advisory warn, allowed_to_proceed=True
13.  enforce_budget_decision — require_review → enforced, allowed_to_proceed=False (no override)
14.  enforce_budget_decision — require_review + override → enforced, allowed_to_proceed=True
15.  enforce_budget_decision — freeze_changes → enforced, allowed_to_proceed=False
16.  enforce_budget_decision — block_release → enforced, allowed_to_proceed=False
17.  enforce_budget_decision raises InvalidDecisionError on invalid decision
18.  build_enforcement_action produces schema-valid artifact
19.  build_enforcement_action includes all required fields
20.  build_enforcement_action raises on unknown system_response
21.  run_enforcement_bridge — allow fixture → allow action
22.  run_enforcement_bridge — warn fixture → warn action
23.  run_enforcement_bridge — require_review fixture → blocked action (no override)
24.  run_enforcement_bridge — require_review fixture + override → allowed action
25.  run_enforcement_bridge — freeze_changes fixture → blocked action
26.  run_enforcement_bridge — block_release fixture → blocked action
27.  run_enforcement_bridge raises on missing file
28.  run_enforcement_bridge raises InvalidDecisionError on invalid decision
29.  run_enforcement_bridge respects context enforcement_scope
30.  CLI exit 0 — allow
31.  CLI exit 0 — warn
32.  CLI exit 1 — require_review (no override)
33.  CLI exit 0 — require_review with override
34.  CLI exit 2 — freeze_changes
35.  CLI exit 2 — block_release
36.  CLI exit 2 — invalid input
37.  CLI writes enforcement action artifact to output-dir
38.  All produced enforcement actions are schema-valid
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_enforcement_bridge import (  # noqa: E402
    EnforcementBridgeError,
    InvalidDecisionError,
    build_enforcement_action,
    determine_enforcement_scope,
    enforce_budget_decision,
    load_budget_decision,
    run_enforcement_bridge,
    validate_budget_decision,
    validate_enforcement_action,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "evaluation_enforcement_bridge"
_ALLOW = _FIXTURE_DIR / "decision_allow.json"
_WARN = _FIXTURE_DIR / "decision_warn.json"
_REVIEW = _FIXTURE_DIR / "decision_require_review.json"
_FREEZE = _FIXTURE_DIR / "decision_freeze_changes.json"
_BLOCK = _FIXTURE_DIR / "decision_block_release.json"
_INVALID = _FIXTURE_DIR / "invalid_decision.json"
_OVERRIDE = _FIXTURE_DIR / "override_artifact.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _make_decision(
    *,
    decision_id: str = "test-decision-001",
    summary_id: str = "test-summary-001",
    status: str = "healthy",
    system_response: str = "allow",
    reasons: list | None = None,
    triggered_thresholds: list | None = None,
    required_actions: list | None = None,
) -> Dict[str, Any]:
    return {
        "decision_id": decision_id,
        "summary_id": summary_id,
        "status": status,
        "system_response": system_response,
        "reasons": reasons if reasons is not None else ["All signals healthy."],
        "triggered_thresholds": triggered_thresholds if triggered_thresholds is not None else [],
        "required_actions": required_actions if required_actions is not None else [],
        "created_at": "2025-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# 1–3. load_budget_decision
# ---------------------------------------------------------------------------


def test_load_budget_decision_valid():
    decision = load_budget_decision(_ALLOW)
    assert decision["decision_id"] == "decision-allow-001"


def test_load_budget_decision_missing_file():
    with pytest.raises(EnforcementBridgeError, match="not found"):
        load_budget_decision("/nonexistent/path/decision.json")


def test_load_budget_decision_invalid_raises():
    with pytest.raises(InvalidDecisionError):
        load_budget_decision(_INVALID)


# ---------------------------------------------------------------------------
# 4–5. validate_budget_decision
# ---------------------------------------------------------------------------


def test_validate_budget_decision_valid():
    decision = _load_json(_ALLOW)
    errors = validate_budget_decision(decision)
    assert errors == [], f"Unexpected errors: {errors}"


def test_validate_budget_decision_invalid():
    errors = validate_budget_decision({"bad": "data"})
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# 6–7. validate_enforcement_action
# ---------------------------------------------------------------------------


def test_validate_enforcement_action_valid():
    action = build_enforcement_action(
        decision_id="dec-001",
        summary_id="sum-001",
        system_response="allow",
        enforcement_scope="release",
        reasons=["All healthy."],
        required_human_actions=[],
        allowed_to_proceed=True,
    )
    errors = validate_enforcement_action(action)
    assert errors == [], f"Unexpected errors: {errors}"


def test_validate_enforcement_action_invalid():
    errors = validate_enforcement_action({"status": "not-a-valid-status"})
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# 8–10. determine_enforcement_scope
# ---------------------------------------------------------------------------


def test_determine_enforcement_scope_default():
    decision = _make_decision()
    scope = determine_enforcement_scope(decision)
    assert scope == "release"


def test_determine_enforcement_scope_from_context():
    decision = _make_decision()
    scope = determine_enforcement_scope(decision, context={"enforcement_scope": "promotion"})
    assert scope == "promotion"


def test_determine_enforcement_scope_unknown_falls_back():
    decision = _make_decision()
    scope = determine_enforcement_scope(decision, context={"enforcement_scope": "unknown_scope"})
    assert scope == "release"


# ---------------------------------------------------------------------------
# 11–17. enforce_budget_decision
# ---------------------------------------------------------------------------


def test_enforce_budget_decision_allow():
    decision = _make_decision(system_response="allow", status="healthy")
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "allow"
    assert action["status"] == "advisory"
    assert action["allowed_to_proceed"] is True


def test_enforce_budget_decision_allow_with_warning():
    decision = _make_decision(system_response="allow_with_warning", status="warning")
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "warn"
    assert action["status"] == "advisory"
    assert action["allowed_to_proceed"] is True


def test_enforce_budget_decision_require_review_no_override():
    decision = _make_decision(system_response="require_review", status="warning")
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "require_review"
    assert action["status"] == "enforced"
    assert action["allowed_to_proceed"] is False


def test_enforce_budget_decision_require_review_with_override():
    decision = _make_decision(system_response="require_review", status="warning")
    override = {"override_id": "override-001", "reviewer": "eng"}
    action = enforce_budget_decision(decision, context={"override_artifact": override})
    assert action["action_type"] == "require_review"
    assert action["status"] == "enforced"
    assert action["allowed_to_proceed"] is True


def test_enforce_budget_decision_freeze_changes():
    decision = _make_decision(system_response="freeze_changes", status="exhausted")
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "freeze_changes"
    assert action["status"] == "enforced"
    assert action["allowed_to_proceed"] is False


def test_enforce_budget_decision_block_release():
    decision = _make_decision(system_response="block_release", status="blocked")
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "block_release"
    assert action["status"] == "enforced"
    assert action["allowed_to_proceed"] is False


def test_enforce_budget_decision_invalid_decision_raises():
    with pytest.raises(InvalidDecisionError):
        enforce_budget_decision({"bad": "data"})


# ---------------------------------------------------------------------------
# 18–20. build_enforcement_action
# ---------------------------------------------------------------------------


def test_build_enforcement_action_schema_valid():
    action = build_enforcement_action(
        decision_id="dec-001",
        summary_id="sum-001",
        system_response="block_release",
        enforcement_scope="release",
        reasons=["Critical failure rate."],
        required_human_actions=["Block all release activity."],
        allowed_to_proceed=False,
    )
    errors = validate_enforcement_action(action)
    assert errors == [], f"Schema errors: {errors}"


def test_build_enforcement_action_required_fields():
    action = build_enforcement_action(
        decision_id="dec-002",
        summary_id="sum-002",
        system_response="allow_with_warning",
        enforcement_scope="promotion",
        reasons=["Elevated drift."],
        required_human_actions=["Review before promoting."],
        allowed_to_proceed=True,
    )
    for field in (
        "action_id", "decision_id", "summary_id", "status", "action_type",
        "enforcement_scope", "allowed_to_proceed", "reasons",
        "required_human_actions", "created_at",
    ):
        assert field in action, f"Missing field: {field}"
    assert action["decision_id"] == "dec-002"
    assert action["summary_id"] == "sum-002"


def test_build_enforcement_action_raises_on_unknown_response():
    with pytest.raises(EnforcementBridgeError, match="Unknown system_response"):
        build_enforcement_action(
            decision_id="dec-003",
            summary_id="sum-003",
            system_response="not_a_valid_response",
            enforcement_scope="release",
            reasons=["test"],
            required_human_actions=[],
            allowed_to_proceed=False,
        )


# ---------------------------------------------------------------------------
# 21–29. run_enforcement_bridge
# ---------------------------------------------------------------------------


def test_run_enforcement_bridge_allow():
    action = run_enforcement_bridge(_ALLOW)
    assert action["action_type"] == "allow"
    assert action["allowed_to_proceed"] is True
    assert action["decision_id"] == "decision-allow-001"


def test_run_enforcement_bridge_warn():
    action = run_enforcement_bridge(_WARN)
    assert action["action_type"] == "warn"
    assert action["allowed_to_proceed"] is True


def test_run_enforcement_bridge_require_review_no_override():
    action = run_enforcement_bridge(_REVIEW)
    assert action["action_type"] == "require_review"
    assert action["allowed_to_proceed"] is False


def test_run_enforcement_bridge_require_review_with_override():
    override = _load_json(_OVERRIDE)
    action = run_enforcement_bridge(_REVIEW, context={"override_artifact": override})
    assert action["action_type"] == "require_review"
    assert action["allowed_to_proceed"] is True


def test_run_enforcement_bridge_freeze_changes():
    action = run_enforcement_bridge(_FREEZE)
    assert action["action_type"] == "freeze_changes"
    assert action["allowed_to_proceed"] is False


def test_run_enforcement_bridge_block_release():
    action = run_enforcement_bridge(_BLOCK)
    assert action["action_type"] == "block_release"
    assert action["allowed_to_proceed"] is False


def test_run_enforcement_bridge_raises_on_missing_file():
    with pytest.raises(EnforcementBridgeError, match="not found"):
        run_enforcement_bridge("/nonexistent/path/decision.json")


def test_run_enforcement_bridge_raises_on_invalid_decision():
    with pytest.raises(InvalidDecisionError):
        run_enforcement_bridge(_INVALID)


def test_run_enforcement_bridge_respects_scope():
    action = run_enforcement_bridge(_ALLOW, context={"enforcement_scope": "schema_change"})
    assert action["enforcement_scope"] == "schema_change"


# ---------------------------------------------------------------------------
# 30–37. CLI
# ---------------------------------------------------------------------------


def test_cli_exit_0_allow(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_ALLOW), "--output-dir", str(tmp_path)])
    assert exit_code == 0


def test_cli_exit_0_warn(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_WARN), "--output-dir", str(tmp_path)])
    assert exit_code == 0


def test_cli_exit_1_require_review_no_override(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_REVIEW), "--output-dir", str(tmp_path)])
    assert exit_code == 1


def test_cli_exit_0_require_review_with_override(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main([
        "--input", str(_REVIEW),
        "--output-dir", str(tmp_path),
        "--override", str(_OVERRIDE),
    ])
    assert exit_code == 0


def test_cli_exit_2_freeze_changes(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_FREEZE), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_exit_2_block_release(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_BLOCK), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_exit_2_invalid_input(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_INVALID), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_writes_enforcement_action_artifact(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    main(["--input", str(_ALLOW), "--output-dir", str(tmp_path)])
    action_path = tmp_path / "evaluation_enforcement_action.json"
    assert action_path.is_file()
    with action_path.open() as fh:
        action = json.load(fh)
    errors = validate_enforcement_action(action)
    assert errors == [], f"Written action is not schema-valid: {errors}"


# ---------------------------------------------------------------------------
# 38. All produced enforcement actions are schema-valid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    [_ALLOW, _WARN, _REVIEW, _FREEZE, _BLOCK],
    ids=["allow", "warn", "require_review", "freeze_changes", "block_release"],
)
def test_all_enforcement_actions_schema_valid(fixture: Path):
    action = run_enforcement_bridge(fixture)
    errors = validate_enforcement_action(action)
    assert errors == [], f"Schema errors for {fixture.name}: {errors}"
