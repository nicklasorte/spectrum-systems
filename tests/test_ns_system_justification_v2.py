"""NS-13..15: System justification v2 + fake-system-admission red team."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.system_justification_v2 import (
    CANONICAL_JUSTIFICATION_REASON_CODES,
    SystemJustificationError,
    assert_demoted_system_visibility,
    assert_system_justification,
    validate_active_systems_bulk,
)


def _good_fields() -> dict:
    return {
        "status": "active",
        "failure_prevented": "unbounded execution",
        "signal_improved": "deterministic execution trace",
        "canonical_artifacts_owned": ["pqx_slice_execution_record"],
        "primary_code_paths": ["spectrum_systems/modules/runtime/pqx_execution_authority.py"],
        "upstream_dependencies": ["AEX"],
        "downstream_dependencies": ["EVL", "OBS"],
    }


def test_full_justification_allows() -> None:
    res = assert_system_justification(
        acronym="PQX",
        fields=_good_fields(),
        proof_tests=["tests/test_nx_eval_spine.py"],
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "JUSTIFICATION_OK"


# ---- NS-14: red team — fake system admission ----


def test_red_team_unjustified_plausible_3ls_blocks() -> None:
    """A plausible-looking but unjustified system: name is fine, but no
    failure_prevented and no signal_improved."""
    fields = _good_fields()
    fields["failure_prevented"] = "TBD"
    fields["signal_improved"] = ""
    res = assert_system_justification(
        acronym="ZZZ",
        fields=fields,
        proof_tests=["tests/test_nx_eval_spine.py"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] in {
        "JUSTIFICATION_MISSING_FAILURE_PREVENTED",
        "JUSTIFICATION_MISSING_SIGNAL_IMPROVED",
    }


def test_red_team_demoted_system_claiming_active_blocks() -> None:
    fields = _good_fields()
    fields["status"] = "demoted"
    res = assert_system_justification(
        acronym="HNX",
        fields=fields,
        proof_tests=["tests/test_nx_eval_spine.py"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JUSTIFICATION_MISSING_STATUS"


def test_red_team_placeholder_system_with_runtime_code_blocks() -> None:
    fields = _good_fields()
    fields["failure_prevented"] = "placeholder"
    res = assert_system_justification(
        acronym="ABX",
        fields=fields,
        proof_tests=["tests/test_nx_eval_spine.py"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JUSTIFICATION_MISSING_FAILURE_PREVENTED"


def test_red_team_system_without_measurable_signal_blocks() -> None:
    fields = _good_fields()
    fields["signal_improved"] = "n/a"
    res = assert_system_justification(
        acronym="QQQ",
        fields=fields,
        proof_tests=["tests/test_nx_eval_spine.py"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JUSTIFICATION_MISSING_SIGNAL_IMPROVED"


def test_red_team_system_without_failure_prevented_blocks() -> None:
    fields = _good_fields()
    fields["failure_prevented"] = ""
    res = assert_system_justification(
        acronym="WWW",
        fields=fields,
        proof_tests=["tests/test_nx_eval_spine.py"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JUSTIFICATION_MISSING_FAILURE_PREVENTED"


def test_red_team_system_without_canonical_artifacts_blocks() -> None:
    fields = _good_fields()
    fields["canonical_artifacts_owned"] = []
    res = assert_system_justification(
        acronym="EEE",
        fields=fields,
        proof_tests=["tests/test_nx_eval_spine.py"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JUSTIFICATION_MISSING_CANONICAL_ARTIFACTS"


def test_red_team_system_without_primary_code_paths_blocks() -> None:
    fields = _good_fields()
    fields["primary_code_paths"] = []
    res = assert_system_justification(
        acronym="RRR",
        fields=fields,
        proof_tests=["tests/test_nx_eval_spine.py"],
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JUSTIFICATION_MISSING_PRIMARY_CODE_PATHS"


def test_red_team_system_without_proof_test_blocks() -> None:
    res = assert_system_justification(
        acronym="TTT",
        fields=_good_fields(),
        proof_tests=[],
        require_proof_test=True,
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JUSTIFICATION_NO_PROOF_TEST"


# ---- demoted-system visibility (NS-15) ----


def test_demoted_system_remains_visible_with_must_not_do() -> None:
    res = assert_demoted_system_visibility(
        acronym="HNX",
        fields={
            "status": "demoted",
            "must_not_do": ["execute_work", "issue_closure_state_decisions"],
        },
    )
    assert res["decision"] == "allow"


def test_demoted_system_without_must_not_do_blocks() -> None:
    res = assert_demoted_system_visibility(
        acronym="HNX", fields={"status": "demoted"}
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JUSTIFICATION_DEMOTED_NOT_VISIBLE"


def test_active_system_visibility_allows() -> None:
    res = assert_demoted_system_visibility(
        acronym="PQX", fields={"status": "active"}
    )
    assert res["decision"] == "allow"


# ---- bulk validation ----


def test_bulk_validation_blocks_when_any_system_unjustified() -> None:
    bad = _good_fields()
    bad["failure_prevented"] = ""
    res = validate_active_systems_bulk(
        active_systems={
            "PQX": _good_fields(),
            "BAD": bad,
        },
        proof_tests_by_system={
            "PQX": ["tests/test_nx_eval_spine.py"],
            "BAD": ["tests/test_nx_eval_spine.py"],
        },
    )
    assert res["decision"] == "block"
    assert any("BAD:" in v for v in res["violations"])
    assert res["per_system"]["PQX"]["decision"] == "allow"


def test_canonical_reason_codes_finite() -> None:
    assert "JUSTIFICATION_OK" in CANONICAL_JUSTIFICATION_REASON_CODES
    assert "JUSTIFICATION_NO_PROOF_TEST" in CANONICAL_JUSTIFICATION_REASON_CODES
