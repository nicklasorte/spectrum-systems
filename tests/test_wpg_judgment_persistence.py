"""Tests for WPG judgment persistence — RT-Loop-10 and RT-Loop-11."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from spectrum_systems.orchestration.wpg_pipeline import _persist_judgment_if_valid


_ALLOW_JUDGMENT_EVAL = {
    "artifact_type": "judgment_eval",
    "evaluation_refs": {
        "control_decision": {
            "decision": "ALLOW",
            "reasons": ["judgment_quality_ok"],
            "enforcement": {"action": "proceed"},
        }
    },
}

_BLOCK_JUDGMENT_EVAL = {
    "artifact_type": "judgment_eval",
    "evaluation_refs": {
        "control_decision": {
            "decision": "BLOCK",
            "reasons": ["rationale_non_empty"],
            "enforcement": {"action": "trigger_repair"},
        }
    },
}

_JUDGMENT_RECORD = {
    "artifact_type": "judgment_record",
    "artifact_id": "jdg-abc123",
    "cycle_id": "cycle-trace-001",
    "selected_outcome": "approve",
    "rationale_summary": "finding:none",
}


def test_wpg_persists_valid_judgment():
    """RT-Loop-10: Valid (ALLOW) judgment is persisted to the JudgmentCorpus."""
    artifact_store = Mock()

    with patch("spectrum_systems.orchestration.wpg_pipeline.JudgmentCorpus") as mock_corpus_class:
        mock_corpus = Mock()
        mock_corpus_class.return_value = mock_corpus

        _persist_judgment_if_valid(_JUDGMENT_RECORD, _ALLOW_JUDGMENT_EVAL, artifact_store)

        mock_corpus_class.assert_called_once_with(artifact_store)
        mock_corpus.record_judgment.assert_called_once()
        call_kwargs = mock_corpus.record_judgment.call_args.kwargs
        assert call_kwargs["decision"] == "approve"
        assert call_kwargs["confidence"] >= 0.0


def test_wpg_skips_persistence_on_blocked_judgment():
    """RT-Loop-11: BLOCK judgment is not persisted to the JudgmentCorpus."""
    artifact_store = Mock()

    with patch("spectrum_systems.orchestration.wpg_pipeline.JudgmentCorpus") as mock_corpus_class:
        mock_corpus = Mock()
        mock_corpus_class.return_value = mock_corpus

        _persist_judgment_if_valid(_JUDGMENT_RECORD, _BLOCK_JUDGMENT_EVAL, artifact_store)

        mock_corpus.record_judgment.assert_not_called()


def test_wpg_skips_persistence_without_artifact_store():
    """No artifact_store means persistence is skipped entirely (backward compat)."""
    with patch("spectrum_systems.orchestration.wpg_pipeline.JudgmentCorpus") as mock_corpus_class:
        _persist_judgment_if_valid(_JUDGMENT_RECORD, _ALLOW_JUDGMENT_EVAL, None)
        mock_corpus_class.assert_not_called()
