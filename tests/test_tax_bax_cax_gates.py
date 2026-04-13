from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.system_enforcement_layer import validate_downstream_a2a_consumption_guard


def test_a2a_guard_blocks_without_arbitration_lineage() -> None:
    result = validate_downstream_a2a_consumption_guard(
        {
            "bax_decision": "allow",
            "tax_decision": "complete",
            "cax_outcome": "complete",
            "handoff_policy_permits": True,
        }
    )
    assert result["block"] is True
    assert "missing_arbitration_lineage" in result["reasons"]


def test_done_certification_schema_supports_authority_lineage_refs() -> None:
    schema = load_schema("done_certification_record")
    input_refs = schema["properties"]["input_refs"]["properties"]
    check_results = schema["properties"]["check_results"]["properties"]
    assert "tax_decision_ref" in input_refs
    assert "bax_decision_ref" in input_refs
    assert "cax_arbitration_ref" in input_refs
    assert "cde_decision_ref" in input_refs
    assert "authority_lineage" in check_results
