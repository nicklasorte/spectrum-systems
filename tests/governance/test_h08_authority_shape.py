"""Authority-shape regression tests for H08 transcript ingestion surfaces.

Asserts that the H08 review/fix artifacts and the transcript ingestor module
contain no protected authority-shape vocabulary outside owner paths. These
tests run the AGS-001 shape preflight directly against the H08 surfaces.

The tests do not weaken the guard, do not add allowlists, and do not move
the H08 artifacts onto canonical owner paths. They simply assert that the
H08 surfaces are clean against the unmodified vocabulary.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_PREFLIGHT_PATH = (
    REPO_ROOT / "spectrum_systems" / "governance" / "authority_shape_preflight.py"
)
_preflight = _load("_h08_shape_preflight", _PREFLIGHT_PATH)
_VOCAB_PATH = (
    REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"
)


H08_SURFACES = [
    "contracts/review_artifact/H08_review.json",
    "contracts/review_actions/H08_fix_actions.json",
    "docs/reviews/H08_transcript_ingestion_review.md",
    "docs/review-actions/H08_fix_plan.md",
    "spectrum_systems/modules/transcript_pipeline/transcript_ingestor.py",
    "spectrum_systems/modules/transcript_pipeline/__init__.py",
    "contracts/schemas/transcript_pipeline/transcript_artifact.schema.json",
]


def _scan(rel_paths: list[str]) -> dict:
    vocab = _preflight.load_vocabulary(_VOCAB_PATH)
    result = _preflight.evaluate_preflight(
        repo_root=REPO_ROOT,
        changed_files=rel_paths,
        vocab=vocab,
        mode="suggest-only",
    )
    return result.to_dict()


def test_h08_surfaces_pass_authority_shape_preflight() -> None:
    """All H08 surfaces must be shape-preflight-clean."""
    result = _scan(H08_SURFACES)
    assert result["status"] == "pass", (
        f"AGS-001 violations on H08 surfaces: {result['violations']}"
    )
    assert result["summary"]["violation_count"] == 0


def test_h08_review_uses_review_signal_vocabulary() -> None:
    """The H08 review JSON uses non-authority review_signal language, not review_decision."""
    review = json.loads(
        (REPO_ROOT / "contracts" / "review_artifact" / "H08_review.json").read_text(
            encoding="utf-8"
        )
    )
    assert "review_signal" in review, "H08 review must use review_signal field"
    assert review["review_signal"] in {
        "revision_recommended",
        "changes_requested_signal",
        "accepted_review_signal",
        "review_passed_signal",
    }
    forbidden_keys = {"review_decision", "decision", "approval"}
    assert forbidden_keys.isdisjoint(review.keys())
    forbidden_values = {"approve", "approved", "approver", "decision", "revise"}
    assert review["review_signal"] not in forbidden_values


def test_h08_review_markdown_has_no_decision_heading() -> None:
    text = (REPO_ROOT / "docs" / "reviews" / "H08_transcript_ingestion_review.md").read_text(
        encoding="utf-8"
    )
    lowered = text.lower()
    assert "**decision:**" not in lowered, "H08 review markdown must not use 'Decision:' label"
    assert "## decision" not in lowered, "H08 review markdown must not use 'Decision' heading"


def test_h08_review_markdown_avoids_protected_terms() -> None:
    text = (REPO_ROOT / "docs" / "reviews" / "H08_transcript_ingestion_review.md").read_text(
        encoding="utf-8"
    )
    lowered = text.lower()
    for term in (
        "review_decision",
        "enforcement_action",
    ):
        assert term not in lowered, f"Forbidden term {term!r} in H08 review markdown"
    # No bare "enforced" in non-owner prose.
    assert " enforced " not in lowered, "H08 review markdown must not use bare 'enforced'"


def test_h08_fix_plan_avoids_protected_terms() -> None:
    md = (REPO_ROOT / "docs" / "review-actions" / "H08_fix_plan.md").read_text(
        encoding="utf-8"
    )
    js = (REPO_ROOT / "contracts" / "review_actions" / "H08_fix_actions.json").read_text(
        encoding="utf-8"
    )
    for blob in (md.lower(), js.lower()):
        for term in (
            "review_decision",
            "enforcement_action",
        ):
            assert term not in blob, f"Forbidden term {term!r} in H08 fix-plan surface"
