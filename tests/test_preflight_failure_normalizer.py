from spectrum_systems.modules.runtime.preflight_failure_normalizer import normalize_preflight_failure


def test_no_unknown_failure() -> None:
    report = {}
    result = normalize_preflight_failure(report)
    assert result["failure_class"] == "internal_preflight_error"


def test_schema_maps_correctly() -> None:
    report = {"schema_example_failures": ["x"]}
    result = normalize_preflight_failure(report)
    assert result["failure_class"] == "schema_violation"


def test_missing_surface_maps_to_contract_mismatch() -> None:
    report = {"missing_required_surface": ["x"]}
    result = normalize_preflight_failure(report)
    assert result["failure_class"] == "contract_mismatch"


def test_pr_pytest_execution_gap_maps_to_inventory_regression() -> None:
    report = {"invariant_violations": ["PR_PYTEST_EXECUTION_REQUIRED"]}
    result = normalize_preflight_failure(report)
    assert result["failure_class"] == "test_inventory_regression"


def test_preflight_pass_without_execution_maps_to_inventory_regression() -> None:
    report = {"invariant_violations": ["PREFLIGHT_PASS_WITHOUT_PYTEST_EXECUTION"]}
    result = normalize_preflight_failure(report)
    assert result["failure_class"] == "test_inventory_regression"
