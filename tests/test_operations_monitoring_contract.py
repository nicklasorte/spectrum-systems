from __future__ import annotations

from spectrum_systems.contracts import load_example, validate_artifact


def _classify_numeric(*, value: float, normal_max: float, warning_max: float, freeze_max: float) -> str:
    if value <= normal_max:
        return "normal"
    if value <= warning_max:
        return "warning"
    if value <= freeze_max:
        return "freeze"
    return "block"


def _classify_replay_rate(*, value: float, normal_min: float, warning_min: float, freeze_min: float) -> str:
    if value >= normal_min:
        return "normal"
    if value >= warning_min:
        return "warning"
    if value >= freeze_min:
        return "freeze"
    return "block"


def test_monitoring_contract_schema_validation() -> None:
    contract = load_example("operations_monitoring_contract")
    validate_artifact(contract, "operations_monitoring_contract")


def test_deterministic_threshold_evaluation() -> None:
    contract = load_example("operations_monitoring_contract")
    thresholds = contract["thresholds"]

    assert _classify_numeric(value=0.03, **{k: thresholds["override_rate"][k] for k in ("normal_max", "warning_max", "freeze_max")}) == "normal"
    assert _classify_numeric(value=0.08, **{k: thresholds["override_rate"][k] for k in ("normal_max", "warning_max", "freeze_max")}) == "warning"
    assert _classify_numeric(value=0.12, **{k: thresholds["override_rate"][k] for k in ("normal_max", "warning_max", "freeze_max")}) == "freeze"
    assert _classify_numeric(value=0.22, **{k: thresholds["override_rate"][k] for k in ("normal_max", "warning_max", "freeze_max")}) == "block"

    assert _classify_replay_rate(value=0.99, **{k: thresholds["replay_match_rate"][k] for k in ("normal_min", "warning_min", "freeze_min")}) == "normal"
    assert _classify_replay_rate(value=0.96, **{k: thresholds["replay_match_rate"][k] for k in ("normal_min", "warning_min", "freeze_min")}) == "warning"
    assert _classify_replay_rate(value=0.92, **{k: thresholds["replay_match_rate"][k] for k in ("normal_min", "warning_min", "freeze_min")}) == "freeze"
    assert _classify_replay_rate(value=0.70, **{k: thresholds["replay_match_rate"][k] for k in ("normal_min", "warning_min", "freeze_min")}) == "block"


def test_severity_mapping_correctness() -> None:
    contract = load_example("operations_monitoring_contract")
    assert set(contract["severity_mapping"].keys()) == {"normal", "warning", "freeze", "block"}
    assert contract["required_actions"]["normal"] == "none"
    assert contract["required_actions"]["warning"] == "observe"
    assert contract["required_actions"]["freeze"] == "investigate"
    assert contract["required_actions"]["block"] == "intervene"


def test_operator_action_mapping_correctness() -> None:
    contract = load_example("operations_monitoring_contract")
    action_by_severity = {rule["severity"]: rule["required_action"] for rule in contract["escalation_rules"]}
    assert action_by_severity == {
        "normal": "none",
        "warning": "observe",
        "freeze": "investigate",
        "block": "intervene",
    }


def test_integration_references_present_in_outputs() -> None:
    build_summary = load_example("build_summary")
    handoff = load_example("batch_handoff_bundle")
    trust = load_example("trust_posture_snapshot")

    for artifact in (build_summary, handoff, trust):
        assert artifact["monitoring_contract_ref"].startswith("operations_monitoring_contract:OMC-")
        assert artifact["operational_severity"] in {"normal", "warning", "freeze", "block"}
        assert artifact["operational_required_action"] in {"none", "observe", "investigate", "intervene"}
        assert artifact["operational_escalation_state"] in {"none", "watch", "paused", "remediation_required"}
