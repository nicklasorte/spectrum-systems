from spectrum_systems.contracts import load_example
from spectrum_systems.governance.rgp02_gate import REQUIRED_CONTRACTS, validate_bounded_family_inputs


def _valid_payloads() -> dict:
    return {name: load_example(name) for name in REQUIRED_CONTRACTS}


def test_gate_happy_path_passes() -> None:
    result = validate_bounded_family_inputs(_valid_payloads())
    assert result.passed is True
    assert result.reason_codes == ()


def test_gate_blocks_missing_required_artifact() -> None:
    artifacts = _valid_payloads()
    artifacts.pop("eval_slice_summary")
    result = validate_bounded_family_inputs(artifacts)
    assert result.passed is False
    assert "missing:eval_slice_summary" in result.reason_codes


def test_gate_blocks_malformed_artifact() -> None:
    artifacts = _valid_payloads()
    artifacts["context_preflight_result"] = {"artifact_type": "context_preflight_result"}
    result = validate_bounded_family_inputs(artifacts)
    assert result.passed is False
    assert "invalid:context_preflight_result" in result.reason_codes


def test_gate_is_replay_stable() -> None:
    artifacts = _valid_payloads()
    first = validate_bounded_family_inputs(artifacts)
    second = validate_bounded_family_inputs(artifacts)
    assert first == second


def test_gate_rejects_unknown_required_contract() -> None:
    artifacts = _valid_payloads()
    artifacts["nonexistent_contract"] = {"artifact_type": "nonexistent_contract"}
    result = validate_bounded_family_inputs(artifacts, required=("nonexistent_contract",))
    assert result.passed is False
    assert result.reason_codes == ("invalid:nonexistent_contract",)
