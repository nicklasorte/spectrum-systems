"""
H05 TLC Router Tests — tests/transcript_pipeline/test_tlc_router_h05.py

Tests:
- valid route returns correct next type
- missing route → ArtifactRoutingError with NO_ROUTE_DEFINED
- terminal type → ArtifactRoutingError with TERMINAL_ARTIFACT_TYPE
- circular route detection (static invariant)
- validate_transition passes for correct chain
- validate_transition fails for incorrect chain
- get_full_pipeline returns complete ordered list
"""
from __future__ import annotations

import pytest

from spectrum_systems.modules.orchestration.tlc_router import (
    ArtifactRoutingError,
    _PIPELINE_ROUTES,
    _TERMINAL_TYPES,
    get_full_pipeline,
    is_terminal,
    pipeline_position,
    route_artifact,
    validate_transition,
)


class TestRouteArtifact:
    def test_transcript_artifact_routes_to_context_bundle(self) -> None:
        assert route_artifact("transcript_artifact") == "context_bundle"

    def test_context_bundle_routes_to_meeting_minutes(self) -> None:
        assert route_artifact("context_bundle") == "meeting_minutes_artifact"

    def test_meeting_minutes_routes_to_issue_registry(self) -> None:
        assert route_artifact("meeting_minutes_artifact") == "issue_registry_artifact"

    def test_issue_registry_routes_to_structured_issue_set(self) -> None:
        assert route_artifact("issue_registry_artifact") == "structured_issue_set"

    def test_structured_issue_set_routes_to_paper_draft(self) -> None:
        assert route_artifact("structured_issue_set") == "paper_draft_artifact"

    def test_paper_draft_routes_to_review(self) -> None:
        assert route_artifact("paper_draft_artifact") == "review_artifact"

    def test_review_routes_to_revised_draft(self) -> None:
        assert route_artifact("review_artifact") == "revised_draft_artifact"

    def test_revised_draft_routes_to_formatted_paper(self) -> None:
        assert route_artifact("revised_draft_artifact") == "formatted_paper_artifact"

    def test_formatted_paper_routes_to_release(self) -> None:
        assert route_artifact("formatted_paper_artifact") == "release_artifact"

    def test_all_non_terminal_types_have_routes(self) -> None:
        pipeline = get_full_pipeline()
        non_terminal = [t for t in pipeline if t not in _TERMINAL_TYPES]
        for artifact_type in non_terminal:
            result = route_artifact(artifact_type)
            assert result is not None, f"No route for {artifact_type}"


class TestMissingRoute:
    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_artifact("nonexistent_artifact_type")
        assert "NO_ROUTE_DEFINED" in exc_info.value.reason_codes

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_artifact("")
        assert "INVALID_ARTIFACT_TYPE" in exc_info.value.reason_codes

    def test_none_raises(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_artifact(None)  # type: ignore[arg-type]
        assert "INVALID_ARTIFACT_TYPE" in exc_info.value.reason_codes

    def test_terminal_type_raises(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_artifact("release_artifact")
        assert "TERMINAL_ARTIFACT_TYPE" in exc_info.value.reason_codes


class TestCircularRouteDetection:
    def test_no_cycles_in_pipeline_routes(self) -> None:
        from spectrum_systems.modules.orchestration.tlc_router import _detect_cycles
        cycles = _detect_cycles(_PIPELINE_ROUTES)
        assert cycles == [], f"Cycles detected in pipeline routes: {cycles}"

    def test_cycle_detection_identifies_simple_cycle(self) -> None:
        from spectrum_systems.modules.orchestration.tlc_router import _detect_cycles
        cyclic = {"A": "B", "B": "C", "C": "A"}
        cycles = _detect_cycles(cyclic)
        assert len(cycles) > 0


class TestValidateTransition:
    def test_correct_transition_passes(self) -> None:
        validate_transition("transcript_artifact", "context_bundle")
        validate_transition("paper_draft_artifact", "review_artifact")
        validate_transition("formatted_paper_artifact", "release_artifact")

    def test_incorrect_transition_raises(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            validate_transition("transcript_artifact", "paper_draft_artifact")
        assert "INVALID_TRANSITION" in exc_info.value.reason_codes

    def test_skipping_step_raises(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            validate_transition("context_bundle", "issue_registry_artifact")
        assert "INVALID_TRANSITION" in exc_info.value.reason_codes


class TestIsTerminal:
    def test_release_artifact_is_terminal(self) -> None:
        assert is_terminal("release_artifact") is True

    def test_transcript_artifact_is_not_terminal(self) -> None:
        assert is_terminal("transcript_artifact") is False

    def test_unknown_type_is_not_terminal(self) -> None:
        assert is_terminal("unknown_type") is False


class TestPipelinePosition:
    def test_transcript_is_first(self) -> None:
        assert pipeline_position("transcript_artifact") == 0

    def test_release_is_last(self) -> None:
        pipeline = get_full_pipeline()
        assert pipeline_position("release_artifact") == len(pipeline) - 1

    def test_paper_draft_after_structured_issue_set(self) -> None:
        pos_sis = pipeline_position("structured_issue_set")
        pos_pda = pipeline_position("paper_draft_artifact")
        assert pos_pda == pos_sis + 1

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            pipeline_position("unknown_type")
        assert "UNKNOWN_PIPELINE_POSITION" in exc_info.value.reason_codes


class TestGetFullPipeline:
    def test_pipeline_starts_with_transcript(self) -> None:
        pipeline = get_full_pipeline()
        assert pipeline[0] == "transcript_artifact"

    def test_pipeline_ends_with_release(self) -> None:
        pipeline = get_full_pipeline()
        assert pipeline[-1] == "release_artifact"

    def test_pipeline_has_no_duplicates(self) -> None:
        pipeline = get_full_pipeline()
        assert len(pipeline) == len(set(pipeline))

    def test_pipeline_has_expected_length(self) -> None:
        pipeline = get_full_pipeline()
        assert len(pipeline) == 10
