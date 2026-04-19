from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_AG06_FILES = (
    _REPO_ROOT / "contracts" / "schemas" / "generated_eval_candidate_record.schema.json",
    _REPO_ROOT / "contracts" / "schemas" / "generated_eval_candidate_queue.schema.json",
    _REPO_ROOT / "contracts" / "schemas" / "generated_eval_candidate_assessment_record.schema.json",
    _REPO_ROOT / "contracts" / "examples" / "generated_eval_candidate_record.json",
    _REPO_ROOT / "contracts" / "examples" / "generated_eval_candidate_queue.json",
    _REPO_ROOT / "contracts" / "examples" / "generated_eval_candidate_assessment_record.json",
    _REPO_ROOT / "docs" / "runtime" / "ag-06-eval-staging-and-review.md",
    _REPO_ROOT / "spectrum_systems" / "modules" / "runtime" / "failure_eval_generation.py",
    _REPO_ROOT / "tests" / "test_failure_eval_generation.py",
)

_FORBIDDEN_TOKENS = (
    "promotion_recommendation_record",
    "generated_eval_review_queue",
    "generated_eval_staging_record",
    '"promote"',
    '"monitor"',
    "accepted_for_registry",
    '"rejected"',
    '"deferred"',
)


def test_ag06_surface_avoids_authority_shaped_artifact_and_value_tokens() -> None:
    for path in _AG06_FILES:
        payload = path.read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_TOKENS:
            assert forbidden not in payload, f"forbidden AG-06 vocabulary '{forbidden}' found in {path}"
