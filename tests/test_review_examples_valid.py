import json
import shutil
import subprocess
from pathlib import Path

import jsonschema
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_REVIEW_PATH = REPO_ROOT / "design-reviews" / "2026-03-14-claude-review-automation.actions.json"
REQUIRED_FIELDS = ("id", "severity", "category", "title", "description")
REQUIRED_FINDING_FIELDS = ("recommended_action", "files_affected", "create_issue")
SCHEMA_PATH = REPO_ROOT / "design-reviews" / "claude-review.schema.json"


def _load_example() -> dict:
    assert EXAMPLE_REVIEW_PATH.is_file(), "2026-03-14-claude-review-automation.actions.json is missing"
    with EXAMPLE_REVIEW_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_example_review_actions_structure() -> None:
    payload = _load_example()
    assert "findings" in payload, "findings list missing from example review actions"
    assert isinstance(payload["findings"], list), "findings must be a list"
    for finding in payload["findings"]:
        assert isinstance(finding, dict), "Each finding must be an object"
        for field in REQUIRED_FIELDS:
            assert field in finding, f"Missing '{field}' in finding: {finding}"
            assert finding[field], f"Field '{field}' must be non-empty"
        for field in REQUIRED_FINDING_FIELDS:
            assert field in finding, f"Missing '{field}' in finding: {finding}"
        assert isinstance(finding["create_issue"], bool), "create_issue must be a boolean"

        recommended = finding["recommended_action"]
        if isinstance(recommended, str):
            assert recommended.strip(), "recommended_action string must be non-empty"
        else:
            assert isinstance(recommended, list) and recommended, "recommended_action must be string or non-empty list"
            assert all(isinstance(item, str) and item.strip() for item in recommended), "recommended_action list items must be non-empty strings"

        files_affected = finding["files_affected"]
        if isinstance(files_affected, str):
            assert files_affected.strip(), "files_affected string must be non-empty"
        else:
            assert isinstance(files_affected, list) and files_affected, "files_affected must be string or non-empty list"
            assert all(isinstance(item, str) and item.strip() for item in files_affected), "files_affected list items must be non-empty strings"


def test_example_actions_matches_summary() -> None:
    payload = _load_example()
    assert payload["summary"]["gaps"], "Summary gaps must not be empty"


def test_example_actions_validates_against_schema() -> None:
    payload = _load_example()
    assert SCHEMA_PATH.is_file(), "claude-review.schema.json is missing"
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        schema = json.load(handle)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.json_path)
    if errors:
        formatted = "\n".join(f"{err.json_path or '$'}: {err.message}" for err in errors)
        pytest.fail(f"Schema validation errors:\n{formatted}")


def test_design_review_markdown_has_actions_pair() -> None:
    review_dir = REPO_ROOT / "design-reviews"
    markdown_files = [
        path for path in review_dir.glob("*.md")
        if path.name not in {"README.md", "claude-review-template.md"}
    ]
    assert markdown_files, "No design review markdown files found in design-reviews/"
    for md in markdown_files:
        paired = md.with_suffix(".actions.json")
        assert paired.is_file(), f"Missing paired actions artifact for {md.name}; expected {paired.name}"


def _install_node_validation_deps() -> None:
    npm = shutil.which("npm")
    if npm is None:
        pytest.skip("npm is required to validate the Node CLI path")
    subprocess.run(
        [npm, "install", "--no-save", "--no-package-lock", "ajv@^8", "ajv-formats@^2"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_cli_validation_path_succeeds() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to run the ingest validation CLI")
    _install_node_validation_deps()
    cmd = [
        node,
        str(REPO_ROOT / "scripts" / "ingest-claude-review.js"),
        "--mode",
        "validate",
        "--schema",
        str(SCHEMA_PATH),
        str(EXAMPLE_REVIEW_PATH),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(
            f"CLI validation failed ({result.returncode}):\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
