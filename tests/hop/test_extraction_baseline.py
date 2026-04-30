"""HOP-006B1 — extraction schema and baseline harness unit tests.

Coverage:
- Schema accepts valid extraction signal
- Schema rejects item without evidence_refs
- Schema rejects unknown category
- Baseline emits each category on simple keyword cases
- Baseline fails or misses multi-turn ambiguous cases (by construction)
- AGS authority-shape preflight passes HOP extraction files
- Authority leak guard passes HOP extraction files
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.authority_leak_rules import find_forbidden_vocabulary, load_authority_registry
from scripts.authority_shape_detector import detect_authority_shapes
from spectrum_systems.modules.hop import extraction_baseline_harness
from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import HopSchemaError, validate_hop_artifact
from spectrum_systems.governance.authority_shape_preflight import (
    evaluate_preflight,
    load_vocabulary,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "contracts" / "governance" / "authority_registry.json"
VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _input(turns):
    return {"transcript_id": "t_extract_test", "turns": turns}


def _valid_extraction_signal(items=None):
    """Build a minimal valid hop_harness_extraction_signal payload."""
    if items is None:
        items = []
    payload = {
        "artifact_type": "hop_harness_extraction_signal",
        "schema_ref": "hop/harness_extraction_signal.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="hop_test"),
        "advisory_only": True,
        "delegates_to": ["JSX", "EVL"],
        "transcript_id": "t_test_001",
        "candidate_id": "extraction_baseline_v1",
        "items": items,
        "generated_at": "2026-04-29T00:00:00.000000Z",
    }
    finalize_artifact(payload, id_prefix="hop_extract_")
    return payload


def _valid_item(category="risk"):
    return {
        "item_id": "hop_extract_abcd1234abcd1234",
        "category": category,
        "description": "There is a risk here.",
        "evidence_refs": [{"turn_index": 0, "char_start": 10, "char_end": 14}],
        "source_turn_indices": [0],
        "owner_text": None,
        "due_date_text": None,
        "confidence_signal": "medium",
        "ambiguity_signal": "none",
    }


# ---------------------------------------------------------------------------
# Schema: accepts valid extraction signal
# ---------------------------------------------------------------------------

def test_schema_accepts_empty_items_signal() -> None:
    payload = _valid_extraction_signal()
    validate_hop_artifact(payload, "hop_harness_extraction_signal")


def test_schema_accepts_signal_with_valid_item() -> None:
    payload = _valid_extraction_signal(items=[_valid_item("risk")])
    validate_hop_artifact(payload, "hop_harness_extraction_signal")


def test_schema_accepts_all_categories() -> None:
    for cat in ("issue", "risk", "action", "open_question", "assumption"):
        payload = _valid_extraction_signal(items=[_valid_item(cat)])
        validate_hop_artifact(payload, "hop_harness_extraction_signal")


def test_schema_accepts_nullable_owner_and_due_date() -> None:
    item = _valid_item()
    item["owner_text"] = None
    item["due_date_text"] = None
    validate_hop_artifact(_valid_extraction_signal(items=[item]), "hop_harness_extraction_signal")


def test_schema_accepts_string_owner_and_due_date() -> None:
    item = _valid_item()
    item["owner_text"] = "Alice"
    item["due_date_text"] = "by Friday"
    validate_hop_artifact(_valid_extraction_signal(items=[item]), "hop_harness_extraction_signal")


def test_schema_enforces_advisory_only_const_true() -> None:
    payload = _valid_extraction_signal()
    payload["advisory_only"] = False
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(payload, "hop_harness_extraction_signal")


def test_schema_requires_delegates_to() -> None:
    payload = _valid_extraction_signal()
    del payload["delegates_to"]
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(payload, "hop_harness_extraction_signal")


def test_schema_rejects_empty_delegates_to() -> None:
    payload = _valid_extraction_signal()
    payload["delegates_to"] = []
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(payload, "hop_harness_extraction_signal")


# ---------------------------------------------------------------------------
# Schema: rejects item without evidence_refs
# ---------------------------------------------------------------------------

def test_schema_rejects_item_with_empty_evidence_refs() -> None:
    item = _valid_item()
    item["evidence_refs"] = []
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(_valid_extraction_signal(items=[item]), "hop_harness_extraction_signal")


def test_schema_rejects_item_missing_evidence_refs() -> None:
    item = _valid_item()
    del item["evidence_refs"]
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(_valid_extraction_signal(items=[item]), "hop_harness_extraction_signal")


# ---------------------------------------------------------------------------
# Schema: rejects unknown category
# ---------------------------------------------------------------------------

def test_schema_rejects_unknown_category() -> None:
    item = _valid_item()
    item["category"] = "unknown"
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(_valid_extraction_signal(items=[item]), "hop_harness_extraction_signal")


def test_schema_rejects_free_form_category() -> None:
    item = _valid_item()
    item["category"] = "concern"
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(_valid_extraction_signal(items=[item]), "hop_harness_extraction_signal")


def test_schema_rejects_additional_properties_on_item() -> None:
    item = _valid_item()
    item["extra_field"] = "leak"
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(_valid_extraction_signal(items=[item]), "hop_harness_extraction_signal")


# ---------------------------------------------------------------------------
# Baseline: emits correct category on simple keyword cases
# ---------------------------------------------------------------------------

def test_baseline_emits_risk_on_risk_keyword() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "assistant", "text": "There is a risk of failure."}])
    )
    validate_hop_artifact(out, "hop_harness_extraction_signal")
    categories = [i["category"] for i in out["items"]]
    assert "risk" in categories


def test_baseline_emits_risk_on_concern_keyword() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "user", "text": "I have a concern about this."}])
    )
    categories = [i["category"] for i in out["items"]]
    assert "risk" in categories


def test_baseline_emits_action_on_we_will_keyword() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "assistant", "text": "We will fix this by tomorrow."}])
    )
    validate_hop_artifact(out, "hop_harness_extraction_signal")
    categories = [i["category"] for i in out["items"]]
    assert "action" in categories


def test_baseline_emits_action_on_lets_keyword() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "assistant", "text": "Let's schedule a review meeting."}])
    )
    categories = [i["category"] for i in out["items"]]
    assert "action" in categories


def test_baseline_emits_issue_on_issue_keyword() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "user", "text": "There is an issue with the deployment."}])
    )
    validate_hop_artifact(out, "hop_harness_extraction_signal")
    categories = [i["category"] for i in out["items"]]
    assert "issue" in categories


def test_baseline_emits_issue_on_bug_keyword() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "assistant", "text": "This is a known bug."}])
    )
    categories = [i["category"] for i in out["items"]]
    assert "issue" in categories


def test_baseline_emits_assumption_on_assume_keyword() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "assistant", "text": "I'll assume the service is running."}])
    )
    validate_hop_artifact(out, "hop_harness_extraction_signal")
    categories = [i["category"] for i in out["items"]]
    assert "assumption" in categories


def test_baseline_emits_assumption_on_assuming_keyword() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "assistant", "text": "Assuming the config is correct."}])
    )
    categories = [i["category"] for i in out["items"]]
    assert "assumption" in categories


def test_baseline_emits_open_question_unanswered_user_question() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "user", "text": "What is the deadline?"}])
    )
    validate_hop_artifact(out, "hop_harness_extraction_signal")
    categories = [i["category"] for i in out["items"]]
    assert "open_question" in categories


def test_baseline_does_not_emit_open_question_when_answered_with_keyword() -> None:
    out = extraction_baseline_harness.run(
        _input([
            {"speaker": "user", "text": "What is the risk here?"},
            {"speaker": "assistant", "text": "The risk is low."},
        ])
    )
    categories = [i["category"] for i in out["items"]]
    assert "open_question" not in categories


def test_baseline_output_validates_against_schema() -> None:
    out = extraction_baseline_harness.run(
        _input([
            {"speaker": "user", "text": "Is there a risk of delay?"},
            {"speaker": "assistant", "text": "We will address the issue tomorrow. I'll assume the fix is straightforward."},
        ])
    )
    validate_hop_artifact(out, "hop_harness_extraction_signal")
    assert out["advisory_only"] is True
    assert "JSX" in out["delegates_to"]
    assert "EVL" in out["delegates_to"]


def test_baseline_empty_transcript_yields_empty_items() -> None:
    out = extraction_baseline_harness.run(_input([]))
    validate_hop_artifact(out, "hop_harness_extraction_signal")
    assert out["items"] == []


def test_baseline_all_items_carry_evidence_refs() -> None:
    out = extraction_baseline_harness.run(
        _input([
            {"speaker": "user", "text": "There is an issue with the risk of failure."},
            {"speaker": "assistant", "text": "We will assume it is broken. Let's fix it."},
        ])
    )
    for item in out["items"]:
        assert len(item["evidence_refs"]) >= 1, f"item missing evidence_refs: {item}"


def test_baseline_all_items_confidence_signal_medium() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "assistant", "text": "There is a risk and an issue here."}])
    )
    for item in out["items"]:
        assert item["confidence_signal"] == "medium"


def test_baseline_all_items_ambiguity_signal_none() -> None:
    out = extraction_baseline_harness.run(
        _input([{"speaker": "assistant", "text": "There is a risk and an issue here."}])
    )
    for item in out["items"]:
        assert item["ambiguity_signal"] == "none"


# ---------------------------------------------------------------------------
# Baseline: fails / misses multi-turn ambiguous cases (by construction)
# ---------------------------------------------------------------------------

def test_baseline_misses_implied_risk_without_keyword() -> None:
    """An implied risk with no keyword is invisible to the baseline."""
    out = extraction_baseline_harness.run(
        _input([
            {"speaker": "user", "text": "Will the system handle 10x load?"},
            {"speaker": "assistant", "text": "That is a challenging scenario."},
        ])
    )
    categories = [i["category"] for i in out["items"]]
    assert "risk" not in categories


def test_baseline_emits_risk_for_negated_language() -> None:
    """Baseline always emits risk on keyword even when negated (known weakness)."""
    out = extraction_baseline_harness.run(
        _input([{"speaker": "assistant", "text": "There is no risk whatsoever."}])
    )
    categories = [i["category"] for i in out["items"]]
    assert "risk" in categories


def test_baseline_misses_attribution_across_turns() -> None:
    """Multi-turn attribution is invisible: baseline assigns None to owner_text."""
    out = extraction_baseline_harness.run(
        _input([
            {"speaker": "user", "text": "Alice said we will handle it."},
            {"speaker": "assistant", "text": "Bob confirmed the action."},
        ])
    )
    for item in out["items"]:
        assert item["owner_text"] is None


def test_baseline_ambiguity_signal_never_set() -> None:
    """Baseline never emits non-none ambiguity_signal regardless of transcript complexity."""
    out = extraction_baseline_harness.run(
        _input([
            {"speaker": "assistant", "text": "We will do X."},
            {"speaker": "assistant", "text": "We will do Y instead."},
        ])
    )
    for item in out["items"]:
        assert item["ambiguity_signal"] == "none"


def test_baseline_invalid_input_type_raises() -> None:
    with pytest.raises(TypeError):
        extraction_baseline_harness.run("not_a_dict")  # type: ignore[arg-type]


def test_baseline_missing_transcript_id_raises() -> None:
    with pytest.raises(ValueError):
        extraction_baseline_harness.run({"transcript_id": "", "turns": []})


def test_baseline_turns_not_list_raises() -> None:
    with pytest.raises(ValueError):
        extraction_baseline_harness.run({"transcript_id": "t1", "turns": "bad"})


# ---------------------------------------------------------------------------
# AGS preflight: HOP extraction files pass authority-shape check
# ---------------------------------------------------------------------------

def test_ags_preflight_passes_hop_extraction_files() -> None:
    vocab = load_vocabulary(VOCAB_PATH)
    hop_extraction_files = [
        "spectrum_systems/modules/hop/extraction_baseline_harness.py",
        "contracts/schemas/hop/harness_extraction_signal.schema.json",
        "tests/hop/test_extraction_baseline.py",
    ]
    result = evaluate_preflight(
        repo_root=REPO_ROOT,
        changed_files=hop_extraction_files,
        vocab=vocab,
        mode="suggest-only",
    )
    if result.violations:
        formatted = "\n".join(
            f"  {v.file}:{v.line} [{v.cluster}] {v.symbol}"
            for v in result.violations[:20]
        )
        pytest.fail(
            f"HOP extraction files produced {len(result.violations)} authority-shape "
            f"violations:\n{formatted}"
        )


# ---------------------------------------------------------------------------
# Authority leak guard: HOP extraction files pass vocabulary check
# ---------------------------------------------------------------------------

def test_authority_leak_guard_passes_hop_extraction_files() -> None:
    registry = load_authority_registry(REGISTRY_PATH)
    hop_extraction_files = [
        REPO_ROOT / "spectrum_systems" / "modules" / "hop" / "extraction_baseline_harness.py",
        REPO_ROOT / "contracts" / "schemas" / "hop" / "harness_extraction_signal.schema.json",
    ]
    for file_path in hop_extraction_files:
        vocab_violations = find_forbidden_vocabulary(file_path, registry)
        shape_violations = detect_authority_shapes(file_path, registry)
        all_violations = vocab_violations + shape_violations
        if all_violations:
            formatted = "\n".join(
                f"  {v.get('file', file_path)}:{v.get('line', '?')} {v.get('rule', '?')} {v.get('token', '?')}"
                for v in all_violations[:10]
            )
            pytest.fail(
                f"{file_path.name} produced {len(all_violations)} authority leak "
                f"violations:\n{formatted}"
            )
