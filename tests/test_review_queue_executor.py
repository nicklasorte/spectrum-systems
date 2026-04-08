from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.review_queue_executor import (
    ReviewQueueValidationError,
    run_review_queue_executor,
    validate_review_request_artifact,
)


def _request_payload(tmp_path: Path, **overrides: object) -> dict:
    payload = {
        "artifact_type": "review_request_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "review_id": "rqx-01-unit-001",
        "review_name": "rqx_01_unit_review",
        "review_type": "code_path_review",
        "scope": "Unit test bounded review scope.",
        "run_id": "run-rqx-unit-001",
        "batch_id": "batch-rqx-unit-001",
        "changed_files": ["src/example.py"],
        "produced_artifact_refs": ["artifacts/pqx_runs/run-rqx-unit-001/output.json"],
        "validation_result_refs": ["artifacts/pqx_runs/run-rqx-unit-001/test_results.json"],
        "requested_at": "2026-04-08T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _write_repo_inputs(repo_root: Path, *, failed_validation: bool = False) -> None:
    (repo_root / "src").mkdir(parents=True, exist_ok=True)
    (repo_root / "src/example.py").write_text("print('ok')\n", encoding="utf-8")

    artifact_path = repo_root / "artifacts/pqx_runs/run-rqx-unit-001/output.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps({"status": "complete"}), encoding="utf-8")

    validation_path = repo_root / "artifacts/pqx_runs/run-rqx-unit-001/test_results.json"
    status = "failed" if failed_validation else "passed"
    validation_path.write_text(json.dumps({"status": status}), encoding="utf-8")


def test_review_request_validation_accepts_bounded_contract(tmp_path: Path) -> None:
    request = _request_payload(tmp_path)
    validate_review_request_artifact(request)


def test_review_queue_contract_examples_validate() -> None:
    for artifact_type in (
        "review_request_artifact",
        "review_result_artifact",
        "review_merge_readiness_artifact",
    ):
        validate_artifact(load_example(artifact_type), artifact_type)


def test_executor_writes_markdown_and_structured_artifacts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_repo_inputs(repo_root)
    request = _request_payload(tmp_path)

    result = run_review_queue_executor(
        request,
        repo_root=repo_root,
        output_dir=repo_root / "artifacts/reviews",
        review_docs_dir=repo_root / "docs/reviews",
        generated_at="2026-04-08T00:15:00Z",
    )

    markdown_path = Path(result["markdown_review_path"])
    assert markdown_path.exists()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# rqx_01_unit_review" in markdown
    assert "## Findings" in markdown
    assert "Severity: low" in markdown

    result_artifact = result["review_result_artifact"]
    merge_artifact = result["review_merge_readiness_artifact"]
    assert result_artifact["artifact_type"] == "review_result_artifact"
    assert merge_artifact["artifact_type"] == "review_merge_readiness_artifact"
    assert merge_artifact["verdict"] in {"safe_to_merge", "fix_required", "not_safe_to_merge"}


def test_findings_and_severity_are_preserved_in_markdown(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_repo_inputs(repo_root, failed_validation=True)
    request = _request_payload(tmp_path)

    result = run_review_queue_executor(
        request,
        repo_root=repo_root,
        output_dir=repo_root / "artifacts/reviews",
        review_docs_dir=repo_root / "docs/reviews",
        generated_at="2026-04-08T00:16:00Z",
    )

    assert result["review_result_artifact"]["verdict"] == "fix_required"
    finding = result["review_result_artifact"]["findings"][0]
    markdown = Path(result["markdown_review_path"]).read_text(encoding="utf-8")
    assert finding["severity"] == "high"
    assert f"Severity: {finding['severity']}" in markdown
    assert finding["title"] in markdown


def test_unknown_review_type_fails_closed(tmp_path: Path) -> None:
    request = _request_payload(tmp_path, review_type="unknown_review_type")
    with pytest.raises(ReviewQueueValidationError):
        validate_review_request_artifact(request)


def test_missing_required_input_refs_fail_closed(tmp_path: Path) -> None:
    request = _request_payload(tmp_path)
    request.pop("validation_result_refs")
    with pytest.raises(ReviewQueueValidationError):
        validate_review_request_artifact(request)


def test_bounded_review_output_disables_automatic_fix_execution(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_repo_inputs(repo_root)
    request = _request_payload(tmp_path)

    result = run_review_queue_executor(
        request,
        repo_root=repo_root,
        output_dir=repo_root / "artifacts/reviews",
        review_docs_dir=repo_root / "docs/reviews",
        generated_at="2026-04-08T00:17:00Z",
    )

    review_result = result["review_result_artifact"]
    assert review_result["bounded_review"] is True
    assert review_result["automatic_fix_execution"] == "disabled"
