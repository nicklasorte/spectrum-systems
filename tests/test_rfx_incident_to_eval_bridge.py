"""Tests for rfx_incident_to_eval_bridge (RFX-N14)."""

from spectrum_systems.modules.runtime.rfx_incident_to_eval_bridge import (
    build_rfx_incident_to_eval_bridge,
)


def _incident(**kw):
    base = {
        "incident_id": "inc-001",
        "classification": "authority_drift_fixture_violation",
        "trace_ref": "trace-001",
        "description": "Authority verb found in fixture.",
        "reproduction_inputs": {"fixture_text": "bad phrase"},
        "expected_outcome": "fixture_rejected",
    }
    base.update(kw)
    return base


# RT-N14: incident produces no EVL candidate and no rationale → must fail.
def test_rt_n14_no_candidate_no_rationale_fails():
    result = build_rfx_incident_to_eval_bridge(
        incidents=[{"incident_id": "x", "trace_ref": "t"}]  # no classification → no candidate
    )
    assert "rfx_bridge_no_eval_candidate" in result["reason_codes_emitted"]
    assert result["status"] == "incomplete"


def test_rt_n14_eval_skip_without_rationale_fails():
    result = build_rfx_incident_to_eval_bridge(
        incidents=[_incident(eval_skip=True, eval_skip_rationale="")]
    )
    assert "rfx_bridge_missing_rationale" in result["reason_codes_emitted"]


def test_rt_n14_incident_with_candidate_passes():
    result = build_rfx_incident_to_eval_bridge(
        incidents=[_incident()], evl_target_ref="evl-001"
    )
    assert result["status"] == "complete"
    assert len(result["eval_candidates"]) == 1


def test_eval_skip_with_rationale_ok():
    result = build_rfx_incident_to_eval_bridge(
        incidents=[_incident(eval_skip=True, eval_skip_rationale="covered by existing eval-002")]
    )
    assert "rfx_bridge_missing_rationale" not in result["reason_codes_emitted"]
    assert result["signals"]["skip_with_rationale_count"] == 1


def test_empty_incidents_flagged():
    result = build_rfx_incident_to_eval_bridge(incidents=[])
    assert "rfx_bridge_empty" in result["reason_codes_emitted"]


def test_missing_incident_id_flagged():
    result = build_rfx_incident_to_eval_bridge(incidents=[_incident(incident_id="")])
    assert "rfx_bridge_missing_incident_id" in result["reason_codes_emitted"]


def test_missing_trace_ref_flagged():
    result = build_rfx_incident_to_eval_bridge(incidents=[_incident(trace_ref=None)])
    assert "rfx_bridge_missing_trace_ref" in result["reason_codes_emitted"]


def test_candidate_id_is_stable():
    r1 = build_rfx_incident_to_eval_bridge(incidents=[_incident()])
    r2 = build_rfx_incident_to_eval_bridge(incidents=[_incident()])
    assert r1["eval_candidates"][0]["eval_candidate_id"] == r2["eval_candidates"][0]["eval_candidate_id"]


def test_conversion_rate_signal():
    result = build_rfx_incident_to_eval_bridge(incidents=[_incident(), _incident(incident_id="inc-002")])
    assert result["signals"]["conversion_rate"] == 1.0


def test_artifact_type():
    result = build_rfx_incident_to_eval_bridge(incidents=[_incident()])
    assert result["artifact_type"] == "rfx_incident_to_eval_bridge"


def test_missing_trace_ref_does_not_produce_candidate():
    # P2 fix: missing trace_ref must fail closed — no partial candidate emitted.
    result = build_rfx_incident_to_eval_bridge(incidents=[_incident(trace_ref=None)])
    assert result["eval_candidates"] == []
    assert "rfx_bridge_no_eval_candidate" in result["reason_codes_emitted"]


def test_numeric_incident_id_does_not_raise():
    # P1 fix: numeric IDs from JSON payloads must not raise AttributeError.
    result = build_rfx_incident_to_eval_bridge(
        incidents=[_incident(incident_id=42)]
    )
    assert result["artifact_type"] == "rfx_incident_to_eval_bridge"
    assert len(result["eval_candidates"]) == 1


def test_numeric_id_field_does_not_raise():
    result = build_rfx_incident_to_eval_bridge(
        incidents=[{"id": 99, "classification": "auth_drift", "trace_ref": "t-1"}]
    )
    assert result["artifact_type"] == "rfx_incident_to_eval_bridge"


def test_non_dict_incident_does_not_raise():
    # P1 fix: non-dict incident rows must emit rfx_bridge_malformed_incident, not AttributeError.
    result = build_rfx_incident_to_eval_bridge(incidents=["not-a-dict"])
    assert "rfx_bridge_malformed_incident" in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_incident_to_eval_bridge"


def test_mixed_incidents_malformed_skipped():
    # P1 fix: malformed rows are skipped; valid rows still produce candidates.
    result = build_rfx_incident_to_eval_bridge(
        incidents=[_incident(), "bad-row"],
    )
    assert "rfx_bridge_malformed_incident" in result["reason_codes_emitted"]
    assert len(result["eval_candidates"]) == 1


def test_numeric_eval_skip_rationale_does_not_raise():
    # P1 fix: non-string truthy eval_skip_rationale must not raise AttributeError.
    result = build_rfx_incident_to_eval_bridge(
        incidents=[_incident(eval_skip=True, eval_skip_rationale=42)]
    )
    assert result["artifact_type"] == "rfx_incident_to_eval_bridge"
    assert "rfx_bridge_missing_rationale" not in result["reason_codes_emitted"]
    assert result["signals"]["skip_with_rationale_count"] == 1


def test_whitespace_only_trace_ref_flagged():
    # P1 fix: whitespace-only trace_ref must be treated as absent.
    result = build_rfx_incident_to_eval_bridge(incidents=[_incident(trace_ref="   ")])
    assert "rfx_bridge_missing_trace_ref" in result["reason_codes_emitted"]
    assert result["eval_candidates"] == []


def test_whitespace_only_trace_ref_fails_closed():
    # P1 fix: whitespace-only trace_ref must produce no eval candidate and status=incomplete.
    result = build_rfx_incident_to_eval_bridge(incidents=[_incident(trace_ref="   ")])
    assert "rfx_bridge_no_eval_candidate" in result["reason_codes_emitted"]
    assert result["status"] == "incomplete"


def test_string_false_eval_skip_not_treated_as_skip():
    # P2 fix: serialized string "false" from JSON must not be treated as eval_skip=True;
    # only a literal True boolean must trigger the skip path.
    result = build_rfx_incident_to_eval_bridge(incidents=[_incident(eval_skip="false")])
    assert "rfx_bridge_missing_rationale" not in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_incident_to_eval_bridge"


def test_non_iterable_incidents_does_not_raise():
    # P1 fix: truthy non-iterable incidents (e.g. integer 1 from bad deserialization)
    # must not raise TypeError; must emit rfx_bridge_empty.
    result = build_rfx_incident_to_eval_bridge(incidents=1)
    assert "rfx_bridge_empty" in result["reason_codes_emitted"]
    assert result["artifact_type"] == "rfx_incident_to_eval_bridge"
