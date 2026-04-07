from __future__ import annotations

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.closure_decision_engine import (
    ClosureDecisionEngineError,
    build_eval_adoption_decision_artifact,
)


def test_eval_adoption_requires_rationale_for_non_approved() -> None:
    with pytest.raises(ClosureDecisionEngineError):
        build_eval_adoption_decision_artifact(
            candidate_ref="eval_candidate_artifact:EVC-abc",
            state="deferred",
            decided_by="closure_decision_engine",
            trace_refs=["trace-x"],
        )


def test_eval_adoption_approved_is_valid() -> None:
    artifact = build_eval_adoption_decision_artifact(
        candidate_ref="eval_candidate_artifact:EVC-abc",
        state="approved",
        decided_by="closure_decision_engine",
        trace_refs=["trace-x"],
    )
    validate_artifact(artifact, "eval_adoption_decision_artifact")
