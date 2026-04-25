"""3LS authority repair suggestions tests.

Covers:
- Suggested repairs include neutral terms.
- Suggested repairs do not propose allowlist override for non-owner files.
- Owner-path violations are flagged for manual owner review, not auto-allowlisted.
- Missing input artifact fails closed.
- Missing neutral vocabulary fails closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import suggest_3ls_authority_repairs as suggester  # noqa: E402

NEUTRAL_VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_neutral_vocabulary.json"


@pytest.fixture()
def neutral_vocab() -> dict:
    return json.loads(NEUTRAL_VOCAB_PATH.read_text(encoding="utf-8"))


def _preflight_payload(violations: list[dict]) -> dict:
    return {
        "artifact_type": "3ls_authority_preflight_result",
        "artifact_version": "1.0.0",
        "status": "fail",
        "changed_files": ["spectrum_systems/modules/orchestration/tlc_router.py"],
        "scanned_files": ["spectrum_systems/modules/orchestration/tlc_router.py"],
        "violations": violations,
        "suggested_repairs": [],
        "summary": {
            "violation_count": len(violations),
            "files_with_violations": 1,
            "safe_autofix_available_count": 0,
        },
    }


def test_suggested_repairs_include_neutral_terms(neutral_vocab: dict) -> None:
    preflight_result = _preflight_payload(
        [
            {
                "rule": "forbidden_value",
                "path": "spectrum_systems/modules/orchestration/tmp_tls_repair.py",
                "line": 12,
                "token": "allow",
                "three_letter_system": "unknown",
                "three_letter_system_owner": False,
                "authority_domains_owned": [],
            }
        ]
    )
    suggestions = suggester.build_suggestions(preflight_result, neutral_vocab)
    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert "passed_gate" in suggestion["suggested_terms"]
    assert "gate_evidence_valid" in suggestion["suggested_terms"]
    assert suggestion["propose_allowlist_override"] is False


def test_suggested_repairs_no_allowlist_override_for_non_owner(neutral_vocab: dict) -> None:
    preflight_result = _preflight_payload(
        [
            {
                "rule": "forbidden_value",
                "path": "spectrum_systems/modules/orchestration/tmp_tls_no_allowlist.py",
                "line": 22,
                "token": "block",
                "three_letter_system": "unknown",
                "three_letter_system_owner": False,
                "authority_domains_owned": [],
            },
            {
                "rule": "forbidden_field",
                "path": "spectrum_systems/modules/orchestration/tmp_tls_no_allowlist.py",
                "line": 24,
                "token": "decision",
                "three_letter_system": "unknown",
                "three_letter_system_owner": False,
                "authority_domains_owned": [],
            },
        ]
    )
    suggestions = suggester.build_suggestions(preflight_result, neutral_vocab)
    for suggestion in suggestions:
        assert suggestion["propose_allowlist_override"] is False


def test_owner_path_violation_requires_manual_review(neutral_vocab: dict) -> None:
    preflight_result = _preflight_payload(
        [
            {
                "rule": "forbidden_value",
                "path": "spectrum_systems/modules/runtime/cde_decision_flow.py",
                "line": 1,
                "token": "allow",
                "three_letter_system": "TPA",
                "three_letter_system_owner": True,
                "authority_domains_owned": ["control_decision"],
            }
        ]
    )
    suggestions = suggester.build_suggestions(preflight_result, neutral_vocab)
    assert len(suggestions) == 1
    assert suggestions[0]["owner_authority_review_required"] is True
    assert suggestions[0]["propose_allowlist_override"] is False


def test_missing_input_artifact_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(suggester.AuthorityRepairSuggestionError):
        suggester._load_json(missing)


def test_wrong_artifact_type_input_fails_closed(neutral_vocab: dict) -> None:
    bad = {"artifact_type": "not_3ls", "violations": []}
    with pytest.raises(suggester.AuthorityRepairSuggestionError):
        suggester.build_suggestions(bad, neutral_vocab)


def test_no_neutral_replacement_emits_restructure_suggestion(neutral_vocab: dict) -> None:
    """If a forbidden token has no registered neutral replacement, the suggestion
    must instruct restructuring rather than silently propose an allowlist."""
    preflight_result = _preflight_payload(
        [
            {
                "rule": "forbidden_value",
                "path": "spectrum_systems/modules/orchestration/tmp_tls_unknown_token.py",
                "line": 9,
                "token": "unmapped_authority_token",
                "three_letter_system": "unknown",
                "three_letter_system_owner": False,
                "authority_domains_owned": [],
            }
        ]
    )
    suggestions = suggester.build_suggestions(preflight_result, neutral_vocab)
    assert len(suggestions) == 1
    assert suggestions[0]["suggested_terms"] == []
    assert suggestions[0]["propose_allowlist_override"] is False
    assert "restructure" in suggestions[0]["rationale"].lower() or "remove" in suggestions[0]["rationale"].lower()


def test_artifact_summary_counts_correct(neutral_vocab: dict) -> None:
    preflight_result = _preflight_payload(
        [
            {
                "rule": "forbidden_value",
                "path": "spectrum_systems/modules/runtime/cde_decision_flow.py",
                "line": 1,
                "token": "allow",
                "three_letter_system_owner": True,
                "authority_domains_owned": ["control_decision"],
            },
            {
                "rule": "forbidden_value",
                "path": "spectrum_systems/modules/orchestration/tmp.py",
                "line": 4,
                "token": "block",
                "three_letter_system_owner": False,
                "authority_domains_owned": [],
            },
        ]
    )
    suggestions = suggester.build_suggestions(preflight_result, neutral_vocab)
    artifact = suggester.build_artifact(preflight_result, suggestions)
    assert artifact["summary"]["suggestion_count"] == 2
    assert artifact["summary"]["owner_review_required_count"] == 1
    assert artifact["summary"]["allowlist_override_proposed_count"] == 0
