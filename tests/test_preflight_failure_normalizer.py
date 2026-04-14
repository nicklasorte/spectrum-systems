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
