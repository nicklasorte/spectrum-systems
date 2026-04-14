from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.test_inventory_integrity import evaluate_test_inventory_integrity, refresh_baseline


def _write_repo(tmp_path: Path, *, with_pytest_ini: bool = True, testpaths: str = "tests", test_body: str = "def test_ok():\n    assert True\n") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    if with_pytest_ini:
        (repo / "pytest.ini").write_text(f"[pytest]\ntestpaths = {testpaths}\npythonpath = .\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_sample.py").write_text(test_body, encoding="utf-8")
    return repo


def test_success_when_config_imports_and_inventory_align(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    baseline_path = repo / "docs" / "governance" / "baseline.json"
    refresh_baseline(repo_root=repo, baseline_path=baseline_path, suite_targets=["tests/test_sample.py"])

    result = evaluate_test_inventory_integrity(
        repo_root=repo,
        baseline_path=baseline_path,
        suite_targets=["tests/test_sample.py"],
        execution_cwd=repo,
    )

    assert result.failure_class == "success"
    assert result.blocking is False
    assert result.payload["selected_count"] == 1


def test_failure_when_testpaths_missing_directory(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path, testpaths="missing_tests")
    baseline = repo / "docs" / "governance" / "baseline.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(json.dumps({"expected_count": 0, "expected_nodeids": []}), encoding="utf-8")

    result = evaluate_test_inventory_integrity(repo_root=repo, baseline_path=baseline, execution_cwd=repo)
    assert result.failure_class == "testpaths_missing"
    assert result.blocking is True


def test_failure_when_working_directory_mismatch(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    baseline = repo / "docs" / "governance" / "baseline.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(json.dumps({"expected_count": 0, "expected_nodeids": []}), encoding="utf-8")

    result = evaluate_test_inventory_integrity(repo_root=repo, baseline_path=baseline, execution_cwd=tmp_path)
    assert result.failure_class == "working_directory_mismatch"


def test_failure_when_imports_break_collection(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path, test_body="import does_not_exist\n\ndef test_ok():\n    assert True\n")
    baseline = repo / "docs" / "governance" / "baseline.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(json.dumps({"expected_count": 1, "expected_nodeids": ["tests/test_sample.py::test_ok"]}), encoding="utf-8")

    result = evaluate_test_inventory_integrity(
        repo_root=repo,
        baseline_path=baseline,
        suite_targets=["tests/test_sample.py"],
        execution_cwd=repo,
    )
    assert result.failure_class == "import_resolution_failure"


def test_failure_when_selected_inventory_drops_below_baseline(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    baseline = repo / "docs" / "governance" / "baseline.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(
        json.dumps(
            {
                "expected_count": 2,
                "expected_nodeids": [
                    "tests/test_sample.py::test_ok",
                    "tests/test_sample.py::test_missing",
                ],
            }
        ),
        encoding="utf-8",
    )

    result = evaluate_test_inventory_integrity(
        repo_root=repo,
        baseline_path=baseline,
        suite_targets=["tests/test_sample.py"],
        execution_cwd=repo,
    )
    assert result.failure_class == "unexpected_test_inventory_regression"
    assert "tests/test_sample.py::test_missing" in result.payload["baseline_missing_nodeids"]


def test_failure_when_node_inventory_changes_even_with_plausible_count(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path, test_body="def test_new_name():\n    assert True\n")
    baseline = repo / "docs" / "governance" / "baseline.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(
        json.dumps(
            {
                "expected_count": 1,
                "expected_nodeids": ["tests/test_sample.py::test_old_name"],
            }
        ),
        encoding="utf-8",
    )

    result = evaluate_test_inventory_integrity(
        repo_root=repo,
        baseline_path=baseline,
        suite_targets=["tests/test_sample.py"],
        execution_cwd=repo,
    )
    assert result.failure_class == "unexpected_test_inventory_regression"
    assert result.payload["baseline_unexpected_nodeids"] == ["tests/test_sample.py::test_new_name"]


def test_success_when_baseline_intentionally_refreshed(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    baseline = repo / "docs" / "governance" / "baseline.json"
    refreshed = refresh_baseline(repo_root=repo, baseline_path=baseline, suite_targets=["tests/test_sample.py"])
    assert refreshed["expected_count"] == 1

    result = evaluate_test_inventory_integrity(
        repo_root=repo,
        baseline_path=baseline,
        suite_targets=["tests/test_sample.py"],
        execution_cwd=repo,
    )
    assert result.failure_class == "success"


def test_deterministic_artifact_generation(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    baseline = repo / "docs" / "governance" / "baseline.json"
    refresh_baseline(repo_root=repo, baseline_path=baseline, suite_targets=["tests/test_sample.py"])

    first = evaluate_test_inventory_integrity(
        repo_root=repo,
        baseline_path=baseline,
        suite_targets=["tests/test_sample.py"],
        execution_cwd=repo,
    ).payload
    second = evaluate_test_inventory_integrity(
        repo_root=repo,
        baseline_path=baseline,
        suite_targets=["tests/test_sample.py"],
        execution_cwd=repo,
    ).payload

    assert first["failure_class"] == second["failure_class"]
    assert first["selected_nodeids"] == second["selected_nodeids"]


def test_execution_only_without_selected_targets_fails_closed(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    baseline = repo / "docs" / "governance" / "baseline.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(json.dumps({"expected_count": 1, "expected_nodeids": ["tests/test_sample.py::test_ok"]}), encoding="utf-8")
    result = evaluate_test_inventory_integrity(
        repo_root=repo,
        baseline_path=baseline,
        suite_targets=["tests/does_not_exist.py"],
        execution_cwd=repo,
    )
    assert result.failure_class in {"collection_failure", "no_tests_discovered"}
    assert result.blocking is True
