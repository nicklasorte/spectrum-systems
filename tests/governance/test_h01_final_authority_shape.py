"""Authority-shape preflight regression tests for H01 final hardening.

Asserts that the H01 final review/fix artifacts and the routing module
contain no protected authority-shape vocabulary outside owner paths. These
tests run the AGS-001 shape preflight directly against the H01 surfaces
that previously leaked authority-shape tokens.

The tests do not weaken the guard, do not add allowlists, and do not move
the H01 artifacts onto canonical owner paths. They simply assert that the
H01 surfaces are clean against the unmodified vocabulary.
"""
from __future__ import annotations

import importlib.util
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
_preflight = _load("_h01_final_shape_preflight", _PREFLIGHT_PATH)
_VOCAB_PATH = (
    REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"
)


H01_FINAL_SURFACES = [
    "spectrum_systems/modules/orchestration/tlc_router.py",
    "scripts/run_3ls_authority_preflight.py",
    "contracts/review_artifact/H01_final_review.json",
    "contracts/review_actions/H01_final_fix_actions.json",
    "docs/reviews/H01_final_review.md",
    "docs/review-actions/H01_final_fix_plan.md",
]


def _scan(rel_paths: list[str]):
    vocab = _preflight.load_vocabulary(_VOCAB_PATH)
    result = _preflight.evaluate_preflight(
        repo_root=REPO_ROOT,
        changed_files=rel_paths,
        vocab=vocab,
        mode="suggest-only",
    )
    return result.to_dict()


def test_h01_final_surfaces_pass_authority_shape_preflight() -> None:
    """All H01 final surfaces must be shape-preflight-clean."""
    result = _scan(H01_FINAL_SURFACES)
    assert result["status"] == "pass", (
        f"AGS-001 violations on H01 final surfaces: {result['violations']}"
    )
    assert result["summary"]["violation_count"] == 0


def test_tlc_router_has_no_protected_authority_vocabulary() -> None:
    result = _scan(["spectrum_systems/modules/orchestration/tlc_router.py"])
    assert result["summary"]["violation_count"] == 0


def test_h01_final_review_uses_review_signal_vocabulary() -> None:
    """The H01 final review JSON uses non-authority review_signal language."""
    import json

    review = json.loads(
        (REPO_ROOT / "contracts" / "review_artifact" / "H01_final_review.json").read_text(
            encoding="utf-8"
        )
    )
    assert "review_signal" in review
    assert review["review_signal"] == "accepted_review_signal"
    forbidden_keys = {"review_decision", "decision", "approval"}
    assert forbidden_keys.isdisjoint(review.keys())
    forbidden_values = {"approve", "approved", "approver", "decision"}
    assert review["review_signal"] not in forbidden_values


def test_h01_final_review_markdown_avoids_protected_terms() -> None:
    text = (REPO_ROOT / "docs" / "reviews" / "H01_final_review.md").read_text(
        encoding="utf-8"
    )
    lowered = text.lower()
    for term in (
        "review_decision",
        "enforcement_action",
        "test_control_routing_enforcement",
    ):
        assert term not in lowered, f"Forbidden term {term!r} in H01_final_review.md"


def test_h01_final_fix_plan_avoids_protected_terms() -> None:
    md = (REPO_ROOT / "docs" / "review-actions" / "H01_final_fix_plan.md").read_text(
        encoding="utf-8"
    )
    js = (REPO_ROOT / "contracts" / "review_actions" / "H01_final_fix_actions.json").read_text(
        encoding="utf-8"
    )
    for blob in (md.lower(), js.lower()):
        for term in (
            "review_decision",
            "enforcement_action",
            "test_control_routing_enforcement",
        ):
            assert term not in blob, f"Forbidden term {term!r} in H01 fix-plan surface"
