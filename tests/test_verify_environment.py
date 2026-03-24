from unittest.mock import patch

import scripts.verify_environment as verify_environment


def test_run_checks_all_pass_when_prereqs_available() -> None:
    with patch.object(
        verify_environment,
        "_check_python_package",
        return_value=verify_environment.CheckResult("jsonschema", True, "ok"),
    ), patch.object(
        verify_environment,
        "_check_node_runtime",
        return_value=verify_environment.CheckResult("node", True, "ok"),
    ):
        checks = verify_environment.run_checks()

    assert [check.ok for check in checks] == [True, True, True, True]
    assert checks[0].name == "python_runtime"


def test_check_python_package_reports_missing_dependency() -> None:
    with patch("scripts.verify_environment.importlib.import_module", side_effect=ModuleNotFoundError):
        result = verify_environment._check_python_package("jsonschema")

    assert result.ok is False
    assert "requirements-dev.txt" in result.detail


def test_check_node_runtime_reports_missing_binary() -> None:
    with patch("scripts.verify_environment.shutil.which", return_value=None):
        result = verify_environment._check_node_runtime()

    assert result.ok is False
    assert "not found in PATH" in result.detail


def test_main_returns_nonzero_on_failures() -> None:
    failing = [
        verify_environment.CheckResult("python", True, "ok"),
        verify_environment.CheckResult("jsonschema", True, "ok"),
        verify_environment.CheckResult("pytest", True, "ok"),
        verify_environment.CheckResult("node", False, "missing"),
    ]
    with patch.object(verify_environment, "run_checks", return_value=failing):
        code = verify_environment.main([])

    assert code == 1
