import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_PATH = REPO_ROOT / "docs" / "review-readiness-checklist.md"
EVIDENCE_PATH = REPO_ROOT / "docs" / "review-evidence-standard.md"
REVIEW_TO_ACTION_PATH = REPO_ROOT / "docs" / "review-to-action-standard.md"
REVIEWS_DIR = REPO_ROOT / "docs" / "reviews"
ACTIONS_DIR = REPO_ROOT / "docs" / "review-actions"
DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def test_readiness_docs_exist() -> None:
    assert CHECKLIST_PATH.is_file(), "review-readiness-checklist.md is missing"
    assert EVIDENCE_PATH.is_file(), "review-evidence-standard.md is missing"


def test_review_to_action_references_evidence_requirements() -> None:
    text = REVIEW_TO_ACTION_PATH.read_text(encoding="utf-8").lower()
    required_phrases = (
        "acceptance criteria",
        "evidence placeholder",
        "target repository",
        "blocking relationships",
        "reconcile prior findings",
    )
    for phrase in required_phrases:
        assert phrase in text, f"'review-to-action-standard.md' must mention '{phrase}'"


def test_reviews_have_action_trackers_with_matching_dates() -> None:
    review_files = [
        path
        for path in REVIEWS_DIR.iterdir()
        if path.is_file() and DATE_PREFIX.match(path.name)
    ]
    assert review_files, "No dated review artifacts found in docs/reviews/"

    action_files = [
        path
        for path in ACTIONS_DIR.iterdir()
        if path.is_file() and DATE_PREFIX.match(path.name)
    ]
    for review in review_files:
        date_stem = review.name[:10]
        matches = [action for action in action_files if action.name.startswith(date_stem)]
        assert matches, f"Missing action tracker in docs/review-actions/ for {review.name}"
