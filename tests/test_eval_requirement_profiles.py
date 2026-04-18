import pytest

from spectrum_systems.modules.runtime.bne02_full_wave import (
    BNE02BlockError,
    enforce_artifact_eval_requirement_profile,
)


def test_missing_profile_blocks() -> None:
    with pytest.raises(BNE02BlockError, match="missing eval requirement profile"):
        enforce_artifact_eval_requirement_profile(artifact_family="wpg", requirement_profile=None)


def test_missing_family_profile_blocks() -> None:
    with pytest.raises(BNE02BlockError, match="missing eval requirement profile for artifact family"):
        enforce_artifact_eval_requirement_profile(
            artifact_family="wpg",
            requirement_profile={"other": ["eval.a"]},
        )


def test_requirement_profile_returns_required_evals() -> None:
    unique, ordered = enforce_artifact_eval_requirement_profile(
        artifact_family="wpg",
        requirement_profile={"wpg": ["eval.a", "eval.b", "eval.a"]},
    )
    assert unique == ["eval.a", "eval.b"]
    assert ordered == ["eval.a", "eval.a", "eval.b"]
