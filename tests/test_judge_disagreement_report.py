from spectrum_systems.contracts import load_example, validate_artifact

def test_judge_disagreement_example_valid() -> None:
    validate_artifact(load_example("judge_disagreement_report"), "judge_disagreement_report")
