"""Tests for BR SLO control layer (Prompt BR).

Covers:
- valid inputs → healthy
- missing BG sections → degraded / violated
- missing traceability → violated
- BE-only path (no BF/BG)
- no inputs at all
- schema validation failures
- error budget edge cases
- CLI exit codes (0/1/2)
- resilience to missing timestamps
- artifact schema compliance
- classify_violation thresholds
- compute_slo_status rules
- determine_allowed_to_proceed rules
- error budget computation
- BG with partial section evidence
- malformed JSON inputs
- full pipeline integration
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.slo_control import (  # noqa: E402
    DEGRADED_THRESHOLD,
    HEALTHY_THRESHOLD,
    build_slo_evaluation_artifact,
    classify_violation,
    compute_completeness_sli,
    compute_error_budget,
    compute_slo_status,
    compute_timeliness_sli,
    compute_traceability_integrity_sli,
    compute_traceability_sli,
    determine_allowed_to_proceed,
    load_inputs,
    run_slo_control,
    validate_inputs_against_schema,
    validate_output_against_schema,
)

_SLO_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "slo_evaluation.schema.json"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _minimal_nrr(
    artifact_id: str = "NRR-AABBCC001122",
    bundle_id: str = "bundle-001",
    study_type: str = "p2p_interference",
) -> Dict[str, Any]:
    """Return a minimal valid NRR artifact dict (matches actual schema)."""
    return {
        "artifact_id": artifact_id,
        "artifact_type": "normalized_run_result",
        "schema_version": "1.0.0",
        "source_bundle_id": bundle_id,
        "study_type": study_type,
        "scenario": {
            "scenario_id": "scen-001",
            "scenario_label": "Test Scenario",
            "frequency_range_mhz": {"low_mhz": 3550.0, "high_mhz": 3600.0},
            "assumptions_summary": "Test.",
        },
        "metrics": {
            "metric_set_id": "ms-001",
            "summary_metrics": [
                {
                    "name": "interference_power_dbm",
                    "value": -85.0,
                    "unit": "dBm",
                    "classification": "core",
                    "source_path": "outputs/results_summary.json#metrics[0]",
                }
            ],
            "completeness": {
                "required_metric_count": 3,
                "present_required_metric_count": 3,
                "missing_required_metrics": [],
                "status": "complete",
            },
        },
        "evaluation_signals": {
            "readiness": "ready_for_comparison",
            "outlier_flags": [],
            "threshold_assessments": [],
            "trust_notes": [],
        },
        "provenance": {
            "manifest_author": "test-author",
            "source_case_ids": ["case-001"],
            "creation_context": "SLO test fixture",
            "rng_reference": {"mode": "fixed", "value": 42},
            "results_summary_source": "outputs/results_summary.json",
            "provenance_source": "outputs/provenance.json",
        },
        "generated_at": "2025-01-01T00:00:00+00:00",
    }


def _minimal_bg(
    artifact_id: str = "WPE-AABBCC001122",
    evidence_pack_id: str = "EPK-AABBCC001122",
    num_sections: int = 8,
    num_findings: int = 5,
    be_artifact_id: str = "NRR-AABBCC001122",
    be_bundle_id: str = "bundle-001",
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a minimal valid BG working_paper_evidence_pack artifact dict."""
    from datetime import datetime, timezone as _tz
    ts = generated_at or datetime.now(_tz.utc).isoformat()
    section_keys = [
        "executive_summary",
        "study_objective",
        "technical_findings",
        "comparative_results",
        "operational_implications",
        "limitations_and_caveats",
        "agency_questions",
        "recommended_next_steps",
    ]
    sections = []
    for i, key in enumerate(section_keys[:num_sections]):
        ev_id = f"EVI-{key.upper().replace('_', '')[:8]}{i:02d}"
        sections.append({
            "section_key": key,
            "section_title": key.replace("_", " ").title(),
            "synthesis_status": "populated",
            "evidence_items": [
                {
                    "evidence_id": ev_id,
                    "evidence_type": "metric_observation",
                    "statement": f"Evidence for {key}.",
                    "support": {
                        "metric_name": "interference_margin_db",
                        "value": "-5.0",
                        "unit": "dB",
                        "comparison_context": "Threshold 0 dB.",
                    },
                    "confidence": "high",
                    "traceability": {
                        "source_artifact_id": be_artifact_id,
                        "source_bundle_id": be_bundle_id,
                        "source_path": "tests/fixtures/nrr.json",
                    },
                }
            ],
        })

    findings = [
        {
            "finding_id": f"FND-{i:03d}AABB",
            "priority": "high" if i == 0 else "medium",
            "headline": f"Finding {i}: test headline.",
            "rationale": f"Rationale for finding {i}.",
            "supporting_evidence_ids": [f"EVI-TECHNI{i:02d}"],
        }
        for i in range(num_findings)
    ]

    caveats = [
        {
            "caveat_id": "CAV-001AABB",
            "category": "data_gap",
            "statement": "This is a test caveat.",
            "severity": "warning",
            "supporting_evidence_ids": [],
        }
    ]

    followup_questions = [
        {
            "question_id": "QST-001AABB",
            "target_section": "agency_questions",
            "question": "What is the interference margin?",
            "reason": "Needs agency confirmation.",
            "supporting_evidence_ids": [],
        }
    ]

    return {
        "artifact_id": artifact_id,
        "artifact_type": "working_paper_evidence_pack",
        "schema_version": "1.0.0",
        "evidence_pack_id": evidence_pack_id,
        "study_type": "p2p_interference",
        "source_artifacts": [
            {
                "artifact_type": "normalized_run_result",
                "artifact_id": be_artifact_id,
                "source_bundle_id": be_bundle_id,
                "path_or_reference": "tests/fixtures/nrr.json",
            }
        ],
        "section_evidence": sections,
        "ranked_findings": findings,
        "caveats": caveats,
        "followup_questions": followup_questions,
        "generated_at": ts,
    }


def _write_json(tmp: Path, name: str, data: Dict[str, Any]) -> Path:
    p = tmp / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ===========================================================================
# 1. classify_violation
# ===========================================================================


def test_classify_violation_healthy():
    """SLI >=0.95 returns None (no violation)."""
    assert classify_violation("completeness", 1.0) is None
    assert classify_violation("timeliness", 0.95) is None


def test_classify_violation_degraded_low():
    """SLI in 0.85–0.95 returns low severity."""
    v = classify_violation("completeness", 0.90)
    assert v is not None
    assert v["severity"] == "low"
    assert v["sli"] == "completeness"


def test_classify_violation_degraded_boundary():
    """SLI at exactly 0.85 returns low severity."""
    v = classify_violation("traceability", 0.85)
    assert v is not None
    assert v["severity"] == "low"


def test_classify_violation_medium():
    """SLI in 0.70–0.85 returns medium severity."""
    v = classify_violation("timeliness", 0.75)
    assert v is not None
    assert v["severity"] == "medium"


def test_classify_violation_high():
    """SLI in 0.50–0.70 returns high severity."""
    v = classify_violation("completeness", 0.60)
    assert v is not None
    assert v["severity"] == "high"


def test_classify_violation_critical():
    """SLI <0.50 returns critical severity."""
    v = classify_violation("traceability", 0.0)
    assert v is not None
    assert v["severity"] == "critical"


def test_classify_violation_description_contains_sli_name():
    v = classify_violation("completeness", 0.80)
    assert "completeness" in v["description"]


# ===========================================================================
# 2. compute_slo_status
# ===========================================================================


def test_compute_slo_status_all_healthy():
    slis = {"completeness": 1.0, "timeliness": 1.0, "traceability": 1.0}
    assert compute_slo_status(slis) == "healthy"


def test_compute_slo_status_one_degraded():
    slis = {"completeness": 0.90, "timeliness": 1.0, "traceability": 1.0}
    assert compute_slo_status(slis) == "degraded"


def test_compute_slo_status_one_violated():
    slis = {"completeness": 0.80, "timeliness": 1.0, "traceability": 1.0}
    assert compute_slo_status(slis) == "violated"


def test_compute_slo_status_critical_beats_degraded():
    slis = {"completeness": 0.90, "timeliness": 0.0, "traceability": 0.90}
    assert compute_slo_status(slis) == "violated"


def test_compute_slo_status_all_at_boundary():
    slis = {"completeness": 0.95, "timeliness": 0.95, "traceability": 0.95}
    assert compute_slo_status(slis) == "healthy"


def test_compute_slo_status_empty_slis():
    assert compute_slo_status({}) == "healthy"


def test_slo_status_priority():
    """Verify SLO status priority: violated > degraded > healthy."""
    # One violated SLI, others healthy → overall violated
    slis_violated = {
        "completeness": 0.5,   # clearly violated (0.5 < DEGRADED_THRESHOLD=0.85)
        "timeliness": 1.0,     # healthy
        "traceability": 1.0,   # healthy
    }
    assert compute_slo_status(slis_violated) == "violated"

    # One degraded SLI, none violated → overall degraded
    slis_degraded = {
        "completeness": 0.90,  # degraded (0.90 in [DEGRADED_THRESHOLD=0.85, HEALTHY_THRESHOLD=0.95))
        "timeliness": 1.0,     # healthy
        "traceability": 1.0,   # healthy
    }
    assert compute_slo_status(slis_degraded) == "degraded"


# ===========================================================================
# 3. compute_error_budget
# ===========================================================================


def test_compute_error_budget_perfect():
    eb = compute_error_budget({"a": 1.0, "b": 1.0, "c": 1.0})
    assert eb["remaining"] == pytest.approx(1.0)
    assert eb["burn_rate"] == pytest.approx(0.0)


def test_compute_error_budget_zero():
    eb = compute_error_budget({"a": 0.0, "b": 0.0, "c": 0.0})
    assert eb["remaining"] == pytest.approx(0.0)
    assert eb["burn_rate"] == pytest.approx(1.0)


def test_compute_error_budget_average():
    eb = compute_error_budget({"a": 0.9, "b": 0.8, "c": 1.0})
    assert eb["remaining"] == pytest.approx(0.9, rel=1e-5)
    assert eb["burn_rate"] == pytest.approx(0.1, rel=1e-5)


def test_compute_error_budget_empty():
    eb = compute_error_budget({})
    assert eb["remaining"] == 0.0
    assert eb["burn_rate"] == 1.0


def test_compute_error_budget_burn_rate_bounds():
    eb = compute_error_budget({"a": 1.1})  # clamped
    assert eb["burn_rate"] >= 0.0


# ===========================================================================
# 4. determine_allowed_to_proceed
# ===========================================================================


def test_allow_healthy_low_burn():
    eb = {"remaining": 0.95, "burn_rate": 0.05}
    assert determine_allowed_to_proceed("healthy", eb) is True


def test_block_violated_status():
    eb = {"remaining": 0.90, "burn_rate": 0.10}
    assert determine_allowed_to_proceed("violated", eb) is False


def test_block_high_burn_rate():
    eb = {"remaining": 0.75, "burn_rate": 0.25}
    assert determine_allowed_to_proceed("degraded", eb) is False


def test_allow_degraded_low_burn():
    eb = {"remaining": 0.90, "burn_rate": 0.10}
    assert determine_allowed_to_proceed("degraded", eb) is True


def test_block_burn_rate_exactly_boundary():
    # burn_rate > 0.2 → block; exactly 0.2 → allow
    eb = {"remaining": 0.80, "burn_rate": 0.20}
    assert determine_allowed_to_proceed("degraded", eb) is True


def test_block_burn_rate_just_over_boundary():
    eb = {"remaining": 0.799, "burn_rate": 0.201}
    assert determine_allowed_to_proceed("degraded", eb) is False


# ===========================================================================
# 5. load_inputs
# ===========================================================================


def test_load_inputs_empty():
    loaded = load_inputs([], None, None)
    assert loaded["be_artifacts"] == []
    assert loaded["bf_artifact"] is None
    assert loaded["bg_artifact"] is None
    assert loaded["load_errors"] == []


def test_load_inputs_missing_file():
    loaded = load_inputs(["/nonexistent/path.json"], None, None)
    assert len(loaded["load_errors"]) == 1
    assert "be_artifact load error" in loaded["load_errors"][0]


def test_load_inputs_be_success():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        p = _write_json(tmp, "nrr.json", _minimal_nrr())
        loaded = load_inputs([str(p)], None, None)
        assert len(loaded["be_artifacts"]) == 1
        assert loaded["load_errors"] == []


def test_load_inputs_malformed_json():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bad = tmp / "bad.json"
        bad.write_text("NOT VALID JSON", encoding="utf-8")
        loaded = load_inputs([str(bad)], None, None)
        assert len(loaded["load_errors"]) == 1


def test_load_inputs_bg_success():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        p = _write_json(tmp, "bg.json", _minimal_bg())
        loaded = load_inputs([], None, str(p))
        assert loaded["bg_artifact"] is not None
        assert loaded["load_errors"] == []


# ===========================================================================
# 6. compute_completeness_sli
# ===========================================================================


def test_completeness_no_inputs():
    loaded = load_inputs([], None, None)
    assert compute_completeness_sli(loaded) == 0.0


def test_completeness_be_only():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        p = _write_json(tmp, "nrr.json", _minimal_nrr())
        loaded = load_inputs([str(p)], None, None)
        score = compute_completeness_sli(loaded)
        assert 0.0 < score <= 1.0


def test_completeness_full_bg():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=8, num_findings=5))
        loaded = load_inputs([], None, str(bg_p))
        score = compute_completeness_sli(loaded)
        assert score == pytest.approx(1.0, abs=0.01)


def test_completeness_missing_sections():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=4, num_findings=5))
        loaded = load_inputs([], None, str(bg_p))
        score = compute_completeness_sli(loaded)
        assert score < 1.0


def test_completeness_zero_findings():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg(num_findings=0)
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        score = compute_completeness_sli(loaded)
        assert score <= 0.5


def test_completeness_too_few_findings():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=8, num_findings=1))
        loaded = load_inputs([], None, str(bg_p))
        score = compute_completeness_sli(loaded)
        assert score < 1.0


def test_completeness_too_many_findings():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=8, num_findings=10))
        loaded = load_inputs([], None, str(bg_p))
        score = compute_completeness_sli(loaded)
        assert score <= 0.90


# ===========================================================================
# 7. compute_timeliness_sli
# ===========================================================================


def test_timeliness_no_bg():
    loaded = load_inputs([], None, None)
    assert compute_timeliness_sli(loaded) == 1.0


def test_timeliness_missing_generated_at():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        del bg["generated_at"]
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        assert compute_timeliness_sli(loaded) == 1.0


def test_timeliness_malformed_timestamp():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        bg["generated_at"] = "NOT-A-TIMESTAMP"
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        # Must not crash; should return 1.0 fallback
        score = compute_timeliness_sli(loaded)
        assert score == 1.0


def test_timeliness_fresh_artifact():
    """An artifact generated moments ago should be 1.0."""
    from datetime import datetime, timezone
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        bg["generated_at"] = datetime.now(timezone.utc).isoformat()
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        assert compute_timeliness_sli(loaded) == 1.0


def test_timeliness_future_timestamp_no_crash():
    """A future-dated timestamp should not crash and return 1.0."""
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        bg["generated_at"] = "2099-01-01T00:00:00+00:00"
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        score = compute_timeliness_sli(loaded)
        assert score == 1.0


def test_timeliness_old_artifact():
    """An artifact older than a week should have timeliness < 1.0."""
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        bg["generated_at"] = "2020-01-01T00:00:00+00:00"
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        score = compute_timeliness_sli(loaded)
        assert score < 1.0


# ===========================================================================
# 8. compute_traceability_sli
# ===========================================================================


def test_traceability_no_inputs():
    loaded = load_inputs([], None, None)
    assert compute_traceability_sli(loaded) == 0.0


def test_traceability_be_only():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        p = _write_json(tmp, "nrr.json", _minimal_nrr())
        loaded = load_inputs([str(p)], None, None)
        score = compute_traceability_sli(loaded)
        assert 0.0 < score <= 1.0


def test_traceability_full_bg_with_sources():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        be_p = _write_json(tmp, "nrr.json", _minimal_nrr())
        bg_p = _write_json(tmp, "bg.json", _minimal_bg())
        loaded = load_inputs([str(be_p)], None, str(bg_p))
        score = compute_traceability_sli(loaded)
        assert score > 0.5


def test_traceability_bg_no_source_artifacts():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        bg["source_artifacts"] = []
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        score = compute_traceability_sli(loaded)
        assert score <= 0.5


# ===========================================================================
# 9. build_slo_evaluation_artifact
# ===========================================================================


def test_build_artifact_structure():
    loaded = load_inputs([], None, None)
    slis = {"completeness": 1.0, "timeliness": 1.0, "traceability": 1.0}
    eb = compute_error_budget(slis)
    artifact = build_slo_evaluation_artifact(
        loaded=loaded,
        slis=slis,
        violations=[],
        slo_status="healthy",
        error_budget=eb,
        allowed_to_proceed=True,
        created_at="2025-01-01T00:00:00+00:00",
    )
    assert "artifact_id" in artifact
    assert "evaluation_id" in artifact
    assert artifact["slo_status"] == "healthy"
    assert artifact["allowed_to_proceed"] is True
    assert "slis" in artifact
    assert "violations" in artifact
    assert "error_budget" in artifact
    assert "inputs" in artifact
    assert "created_at" in artifact


def test_build_artifact_evaluation_id_pattern():
    loaded = load_inputs([], None, None)
    slis = {"completeness": 1.0, "timeliness": 1.0, "traceability": 1.0}
    eb = compute_error_budget(slis)
    artifact = build_slo_evaluation_artifact(
        loaded=loaded,
        slis=slis,
        violations=[],
        slo_status="healthy",
        error_budget=eb,
        allowed_to_proceed=True,
    )
    import re
    assert re.match(r"^SLO-[A-Z0-9._-]+$", artifact["evaluation_id"])


# ===========================================================================
# 10. validate_output_against_schema
# ===========================================================================


def test_validate_output_valid_artifact():
    loaded = load_inputs([], None, None)
    slis = {"completeness": 1.0, "timeliness": 1.0, "traceability": 1.0}
    eb = compute_error_budget(slis)
    artifact = build_slo_evaluation_artifact(
        loaded=loaded,
        slis=slis,
        violations=[],
        slo_status="healthy",
        error_budget=eb,
        allowed_to_proceed=True,
        created_at="2025-01-01T00:00:00+00:00",
        lineage_valid=True,
        parent_artifact_ids=["DEC-001"],
    )
    errors = validate_output_against_schema(artifact)
    assert errors == []


def test_validate_output_missing_required_field():
    bad = {"artifact_id": "X", "evaluation_id": "SLO-AAAA"}
    errors = validate_output_against_schema(bad)
    assert len(errors) > 0


def test_validate_output_extra_property_rejected():
    loaded = load_inputs([], None, None)
    slis = {"completeness": 1.0, "timeliness": 1.0, "traceability": 1.0}
    eb = compute_error_budget(slis)
    artifact = build_slo_evaluation_artifact(
        loaded=loaded,
        slis=slis,
        violations=[],
        slo_status="healthy",
        error_budget=eb,
        allowed_to_proceed=True,
        created_at="2025-01-01T00:00:00+00:00",
    )
    artifact["unexpected_field"] = "should fail"
    errors = validate_output_against_schema(artifact)
    assert len(errors) > 0


# ===========================================================================
# 11. run_slo_control integration
# ===========================================================================


def test_run_slo_control_no_inputs():
    result = run_slo_control([], None, None)
    assert "slo_evaluation" in result
    assert result["slo_status"] in ("healthy", "degraded", "violated")
    assert isinstance(result["allowed_to_proceed"], bool)


def test_run_slo_control_be_only_healthy():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        p = _write_json(tmp, "nrr.json", _minimal_nrr())
        result = run_slo_control([str(p)], None, None, parent_artifact_ids=["DEC-001"])
        assert result["slo_evaluation"] is not None
        assert result["schema_errors"] == []


def test_run_slo_control_full_healthy():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        be_p = _write_json(tmp, "nrr.json", _minimal_nrr())
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=8, num_findings=5))
        result = run_slo_control([str(be_p)], None, str(bg_p))
        assert result["slo_status"] == "healthy"
        assert result["allowed_to_proceed"] is True


def test_run_slo_control_missing_bg_sections_degrades():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=2, num_findings=5))
        result = run_slo_control([], None, str(bg_p))
        assert result["slo_status"] in ("degraded", "violated")


def test_run_slo_control_no_traceability_violated():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        # Remove all source artifact references
        bg["source_artifacts"] = []
        for sec in bg.get("section_evidence", []):
            for item in sec.get("evidence_items", []):
                # Clear traceability fields
                if "traceability" in item:
                    item["traceability"]["source_artifact_id"] = ""
                    item["traceability"]["source_bundle_id"] = ""
        bg_p = _write_json(tmp, "bg.json", bg)
        result = run_slo_control([], None, str(bg_p))
        # Traceability should be low
        slis = result["slo_evaluation"]["slis"]
        assert slis["traceability"] <= 0.7


def test_run_slo_control_bad_be_path():
    result = run_slo_control(["/bad/path.json"], None, None)
    assert len(result["load_errors"]) >= 1


def test_run_slo_control_output_schema_valid():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg_p = _write_json(tmp, "bg.json", _minimal_bg())
        result = run_slo_control([], None, str(bg_p), parent_artifact_ids=["DEC-001"])
        assert result["schema_errors"] == []


def test_run_slo_control_deterministic():
    """Same inputs on same timestamp produce same evaluation_id."""
    ts = "2025-06-01T00:00:00+00:00"
    r1 = run_slo_control([], None, None, created_at=ts)
    r2 = run_slo_control([], None, None, created_at=ts)
    assert r1["slo_evaluation"]["evaluation_id"] == r2["slo_evaluation"]["evaluation_id"]


def test_run_slo_control_error_budget_in_result():
    result = run_slo_control([], None, None)
    eb = result["slo_evaluation"]["error_budget"]
    assert "remaining" in eb
    assert "burn_rate" in eb
    assert 0.0 <= eb["remaining"] <= 1.0
    assert eb["burn_rate"] >= 0.0


# ===========================================================================
# 12. CLI exit codes
# ===========================================================================


def _run_cli(argv: list) -> int:
    sys.path.insert(0, str(_REPO_ROOT))
    # Import inline to avoid stale module state
    import importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "slo_control_cli",
        _REPO_ROOT / "scripts" / "slo_control.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return mod.main(argv)
    except SystemExit as exc:
        return int(exc.code)


def test_cli_exit_0_healthy():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        be_p = _write_json(tmp, "nrr.json", _minimal_nrr())
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=8, num_findings=5))
        code = _run_cli([
            "--be-input", str(be_p),
            "--bg-input", str(bg_p),
            "--parent-id", "DEC-001",
            "--output-dir", tmpd,
        ])
        assert code == 0


def test_cli_exit_1_degraded():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        # 7/8 sections → completeness = 0.875 (strictly in degraded band 0.85–<0.95)
        # BE provided → traceability = 1.0 (healthy, not violated)
        # Fresh BG timestamp → timeliness = 1.0 (healthy, not violated)
        # No lineage registry → traceability_integrity = 1.0 (healthy, not violated)
        # Overall: one degraded SLI, none violated → status = "degraded" → exit 1
        be_p = _write_json(tmp, "nrr.json", _minimal_nrr())
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=7, num_findings=5))
        code = _run_cli([
            "--be-input", str(be_p),
            "--bg-input", str(bg_p),
            "--output-dir", tmpd,
        ])
        assert code == 1  # strictly degraded


def test_cli_exit_2_violated():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        # 3/8 sections → completeness = 0.375 (clearly < 0.85, i.e., violated)
        # No BE input → traceability defaults to 0.5 in BE-absent path (also violated)
        # At least one SLI < DEGRADED_THRESHOLD → overall violated → exit 2
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=3, num_findings=5))
        code = _run_cli([
            "--bg-input", str(bg_p),
            "--output-dir", tmpd,
        ])
        assert code == 2  # violated


def test_cli_exit_2_no_inputs():
    with tempfile.TemporaryDirectory() as tmpd:
        code = _run_cli(["--output-dir", tmpd])
        # No inputs → violated (0.0 completeness and traceability)
        assert code == 2


def test_cli_creates_output_file():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        be_p = _write_json(tmp, "nrr.json", _minimal_nrr())
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=8, num_findings=5))
        _run_cli([
            "--be-input", str(be_p),
            "--bg-input", str(bg_p),
            "--output-dir", tmpd,
        ])
        assert (tmp / "slo_evaluation.json").exists()


def test_cli_output_file_is_valid_json():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        be_p = _write_json(tmp, "nrr.json", _minimal_nrr())
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=8, num_findings=5))
        _run_cli([
            "--be-input", str(be_p),
            "--bg-input", str(bg_p),
            "--output-dir", tmpd,
        ])
        content = (tmp / "slo_evaluation.json").read_text(encoding="utf-8")
        data = json.loads(content)
        assert "slo_status" in data


# ===========================================================================
# 13. Edge cases and resilience
# ===========================================================================


def test_resilience_none_be_inputs():
    """load_inputs with None be_paths does not crash."""
    loaded = load_inputs(None, None, None)  # type: ignore[arg-type]
    assert loaded["be_artifacts"] == []


def test_resilience_empty_bg_section_evidence():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        bg["section_evidence"] = []
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        score = compute_completeness_sli(loaded)
        assert 0.0 <= score <= 1.0


def test_resilience_bg_no_ranked_findings():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        bg["ranked_findings"] = []
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        score = compute_completeness_sli(loaded)
        assert score <= 0.5


def test_resilience_bg_none_section_evidence_items():
    """section_evidence items with empty list do not crash traceability."""
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        bg = _minimal_bg()
        bg["section_evidence"][0]["evidence_items"] = []
        bg_p = _write_json(tmp, "bg.json", bg)
        loaded = load_inputs([], None, str(bg_p))
        score = compute_traceability_sli(loaded)
        assert 0.0 <= score <= 1.0


def test_error_budget_burn_rate_never_negative():
    eb = compute_error_budget({"a": 1.0, "b": 1.0, "c": 1.0})
    assert eb["burn_rate"] >= 0.0


def test_validate_inputs_no_schemas_no_crash():
    """validate_inputs_against_schema must not crash when schema files are missing."""
    loaded = {
        "be_artifacts": [{"artifact_id": "x"}],
        "bf_artifact": None,
        "bg_artifact": None,
    }
    # Should not raise
    errors = validate_inputs_against_schema(loaded)
    assert isinstance(errors, list)


def test_run_slo_control_all_slis_in_result():
    result = run_slo_control([], None, None)
    slis = result["slo_evaluation"]["slis"]
    assert "completeness" in slis
    assert "timeliness" in slis
    assert "traceability" in slis


def test_run_slo_control_violations_list_present():
    result = run_slo_control([], None, None)
    assert isinstance(result["slo_evaluation"]["violations"], list)


def test_run_slo_control_inputs_recorded():
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        p = _write_json(tmp, "nrr.json", _minimal_nrr())
        result = run_slo_control([str(p)], None, None)
        inputs = result["slo_evaluation"]["inputs"]
        assert len(inputs["be_artifacts"]) == 1
        assert inputs["bf_artifact"] is None
        assert inputs["bg_artifact"] is None


# ===========================================================================
# 14. Critical defect fixes — BR+BS blocking bundle
# ===========================================================================


def _minimal_slo_artifact(
    parent_artifact_ids: Optional[List[str]] = None,
    lineage_valid: Optional[bool] = None,
) -> Dict[str, Any]:
    """Return a minimal, schema-compliant SLO evaluation artifact dict."""
    loaded = load_inputs([], None, None)
    slis = {
        "completeness": 1.0,
        "timeliness": 1.0,
        "traceability": 1.0,
        "traceability_integrity": 1.0,
    }
    eb = compute_error_budget(slis)
    return build_slo_evaluation_artifact(
        loaded=loaded,
        slis=slis,
        violations=[],
        slo_status="healthy",
        error_budget=eb,
        allowed_to_proceed=True,
        created_at="2025-01-01T00:00:00+00:00",
        lineage_valid=lineage_valid if lineage_valid is not None else True,
        parent_artifact_ids=parent_artifact_ids if parent_artifact_ids is not None else ["DEC-001"],
    )


# --- Schema contract enforcement ---


def test_schema_rejects_missing_lineage_valid():
    """SLO artifact without lineage_valid must be schema-invalid."""
    artifact = _minimal_slo_artifact()
    del artifact["lineage_valid"]
    errors = validate_output_against_schema(artifact)
    assert len(errors) > 0, "Expected schema error for missing lineage_valid"


def test_schema_rejects_missing_parent_artifact_ids():
    """SLO artifact without parent_artifact_ids must be schema-invalid."""
    artifact = _minimal_slo_artifact()
    del artifact["parent_artifact_ids"]
    errors = validate_output_against_schema(artifact)
    assert len(errors) > 0, "Expected schema error for missing parent_artifact_ids"


def test_schema_rejects_empty_parent_artifact_ids():
    """SLO artifact with empty parent_artifact_ids must be schema-invalid (minItems: 1)."""
    artifact = _minimal_slo_artifact(parent_artifact_ids=["DEC-001"])
    artifact["parent_artifact_ids"] = []
    errors = validate_output_against_schema(artifact)
    assert len(errors) > 0, "Expected schema error for empty parent_artifact_ids"


def test_schema_accepts_valid_artifact_with_lineage():
    """A fully-populated artifact including lineage fields must be schema-valid."""
    artifact = _minimal_slo_artifact(parent_artifact_ids=["DEC-001", "SYN-001"])
    errors = validate_output_against_schema(artifact)
    assert errors == [], errors


# --- compute_traceability_sli with known_ids ---


def test_traceability_sli_known_ids_valid_references_score_correctly():
    """Source artifacts whose IDs match known_ids contribute to the linked count."""
    be = _minimal_nrr(artifact_id="NRR-KNOWN", bundle_id="BND-KNOWN")
    bg = _minimal_bg(be_artifact_id="NRR-KNOWN", be_bundle_id="BND-KNOWN")
    loaded = {
        "be_artifacts": [be],
        "bf_artifact": None,
        "bg_artifact": bg,
    }
    score = compute_traceability_sli(loaded)
    # known_ids = {"NRR-KNOWN", "BND-KNOWN"} — source artifact matches → score is high
    assert score > 0.5


def test_traceability_sli_fabricated_ids_do_not_score_as_linked():
    """Source artifacts that reference IDs absent from known_ids must not score as linked."""
    be = _minimal_nrr(artifact_id="NRR-REAL", bundle_id="BND-REAL")
    # BG references completely different (fabricated) IDs not present in the BE artifact
    bg = _minimal_bg(be_artifact_id="NRR-FABRICATED", be_bundle_id="BND-FABRICATED")
    loaded = {
        "be_artifacts": [be],
        "bf_artifact": None,
        "bg_artifact": bg,
    }
    score = compute_traceability_sli(loaded)
    # known_ids = {"NRR-REAL", "BND-REAL"}; source artifact uses fabricated IDs → linked = 0
    # base_score = 0.0; citation rate (presence-only) is at most 0.4 of composite.
    # Final: 0.6 * 0.0 + 0.4 * citation_rate ≤ 0.4
    assert score <= 0.5, f"Fabricated IDs should not score as linked; got {score}"


def test_traceability_sli_no_known_ids_uses_degraded_fallback():
    """When no BE/BF artifacts are provided, known_ids is empty and degraded mode is used."""
    bg = _minimal_bg()
    loaded = {
        "be_artifacts": [],
        "bf_artifact": None,
        "bg_artifact": bg,
    }
    # With empty known_ids, degraded fallback uses presence-only check.
    # The BG source_artifacts entry has artifact_id set → still counts as linked.
    score = compute_traceability_sli(loaded)
    assert 0.0 <= score <= 1.0  # Must not crash; result is deterministic


# --- run_slo_control lineage integration ---


def _malformed_lineage_registry() -> Dict[str, Any]:
    """Return a lineage registry that validate_full_registry reports as invalid."""
    # An slo_evaluation artifact with no parents is an orphan — always invalid.
    return {
        "SLO-ORPHAN": {
            "artifact_id": "SLO-ORPHAN",
            "artifact_type": "slo_evaluation",
            "parent_artifact_ids": [],
            "lineage_depth": 0,
            "root_artifact_ids": [],
            "lineage_valid": False,
            "lineage_errors": ["orphan"],
            "created_at": "2025-01-01T00:00:00+00:00",
            "created_by": "test",
            "version": "1.0.0",
        }
    }


def test_run_slo_control_malformed_lineage_sets_lineage_valid_false():
    """run_slo_control with an invalid lineage registry must set lineage_valid=False."""
    result = run_slo_control(
        be_inputs=[],
        bf_input=None,
        bg_input=None,
        lineage_registry=_malformed_lineage_registry(),
        parent_artifact_ids=["DEC-001"],
    )
    assert result["lineage_valid"] is False
    assert result["slo_evaluation"]["lineage_valid"] is False


def test_run_slo_control_malformed_lineage_blocks_proceed():
    """run_slo_control with an invalid lineage registry must set allowed_to_proceed=False."""
    result = run_slo_control(
        be_inputs=[],
        bf_input=None,
        bg_input=None,
        lineage_registry=_malformed_lineage_registry(),
        parent_artifact_ids=["DEC-001"],
    )
    assert result["allowed_to_proceed"] is False
    assert result["slo_evaluation"]["allowed_to_proceed"] is False


def test_run_slo_control_malformed_lineage_integrity_not_healthy():
    """Invalid lineage registry must not silently return traceability_integrity = 1.0."""
    result = run_slo_control(
        be_inputs=[],
        bf_input=None,
        bg_input=None,
        lineage_registry=_malformed_lineage_registry(),
        parent_artifact_ids=["DEC-001"],
    )
    slis = result["slo_evaluation"]["slis"]
    assert slis["traceability_integrity"] < 1.0, (
        "traceability_integrity must not be 1.0 when lineage registry is invalid"
    )


def test_run_slo_control_records_parent_artifact_ids():
    """run_slo_control must record parent_artifact_ids in the output artifact."""
    result = run_slo_control(
        be_inputs=[],
        bf_input=None,
        bg_input=None,
        parent_artifact_ids=["DEC-001", "SYN-001"],
    )
    artifact = result["slo_evaluation"]
    assert "parent_artifact_ids" in artifact
    assert artifact["parent_artifact_ids"] == ["DEC-001", "SYN-001"]


# --- CLI lineage integration ---


def test_cli_lineage_dir_loads_registry_and_uses_it():
    """CLI --lineage-dir must load all *.json files and pass the registry to run_slo_control."""
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        lineage_dir = tmp / "lineage"
        lineage_dir.mkdir()

        # Write a valid lineage artifact that validate_full_registry will accept as OK.
        # A simulation_input is a root type — always valid with no parents.
        valid_root = {
            "artifact_id": "SIM-IN-001",
            "artifact_type": "simulation_input",
            "parent_artifact_ids": [],
            "lineage_depth": 0,
            "root_artifact_ids": ["SIM-IN-001"],
            "lineage_valid": True,
            "lineage_errors": [],
            "created_at": "2025-01-01T00:00:00+00:00",
            "created_by": "test",
            "version": "1.0.0",
        }
        _write_json(lineage_dir, "sim_in.json", valid_root)

        be_p = _write_json(tmp, "nrr.json", _minimal_nrr())
        bg_p = _write_json(tmp, "bg.json", _minimal_bg(num_sections=8, num_findings=5))

        code = _run_cli([
            "--be-input", str(be_p),
            "--bg-input", str(bg_p),
            "--lineage-dir", str(lineage_dir),
            "--parent-id", "DEC-001",
            "--output-dir", tmpd,
        ])
        # A valid registry with a healthy simulation_input should not break the evaluation.
        assert code in (0, 1, 2)
        # Confirm the output artifact was written
        assert (tmp / "slo_evaluation.json").exists()
        out = json.loads((tmp / "slo_evaluation.json").read_text())
        assert "traceability_integrity" in out["slis"]
        assert out["parent_artifact_ids"] == ["DEC-001"]


def test_cli_invalid_lineage_registry_causes_non_healthy_outcome():
    """CLI with an invalid lineage registry must yield traceability_integrity < 1.0."""
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        lineage_dir = tmp / "lineage"
        lineage_dir.mkdir()

        # Write an orphan slo_evaluation artifact — lineage is broken
        _write_json(lineage_dir, "orphan.json", {
            "artifact_id": "SLO-ORPHAN",
            "artifact_type": "slo_evaluation",
            "parent_artifact_ids": [],
            "lineage_depth": 0,
            "root_artifact_ids": [],
            "lineage_valid": False,
            "lineage_errors": ["orphan"],
            "created_at": "2025-01-01T00:00:00+00:00",
            "created_by": "test",
            "version": "1.0.0",
        })

        code = _run_cli([
            "--lineage-dir", str(lineage_dir),
            "--parent-id", "DEC-001",
            "--output-dir", tmpd,
        ])
        # Broken lineage → traceability_integrity = 0.0 → violated → exit 2
        assert code == 2
        out = json.loads((tmp / "slo_evaluation.json").read_text())
        assert out["slis"]["traceability_integrity"] < 1.0
        assert out["allowed_to_proceed"] is False


def test_cli_missing_lineage_dir_exits_2():
    """CLI with --lineage-dir pointing to a non-existent path must exit with code 2."""
    with tempfile.TemporaryDirectory() as tmpd:
        code = _run_cli([
            "--lineage-dir", "/nonexistent/lineage/dir",
            "--output-dir", tmpd,
        ])
        assert code == 2


def test_cli_empty_lineage_dir_exits_2():
    """CLI with --lineage-dir pointing to an empty directory must exit with code 2."""
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        empty_dir = tmp / "empty_lineage"
        empty_dir.mkdir()
        code = _run_cli([
            "--lineage-dir", str(empty_dir),
            "--output-dir", tmpd,
        ])
        assert code == 2


def test_cli_malformed_lineage_json_exits_2():
    """CLI with --lineage-dir containing malformed JSON must exit with code 2."""
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        lineage_dir = tmp / "bad_lineage"
        lineage_dir.mkdir()
        bad_file = lineage_dir / "bad.json"
        bad_file.write_text("NOT VALID JSON", encoding="utf-8")
        code = _run_cli([
            "--lineage-dir", str(lineage_dir),
            "--output-dir", tmpd,
        ])
        assert code == 2


# ===========================================================================
# 16. Lineage integrity SLI and failure propagation (Fix 6)
# ===========================================================================


def _registry_with_missing_parent() -> Dict[str, Any]:
    """Return a lineage registry where a non-root artifact references a missing parent."""
    return {
        "SIM-OUT-001": {
            "artifact_id": "SIM-OUT-001",
            "artifact_type": "simulation_output",
            "parent_artifact_ids": ["SIM-IN-MISSING"],
            "lineage_depth": 1,
            "root_artifact_ids": ["SIM-IN-MISSING"],
            "lineage_valid": False,
            "lineage_errors": ["missing parent"],
            "created_at": "2025-01-01T00:00:00+00:00",
            "created_by": "test",
            "version": "1.0.0",
        }
    }


def _registry_with_circular_dep() -> Dict[str, Any]:
    """Return a lineage registry with a circular dependency."""
    return {
        "ART-A": {
            "artifact_id": "ART-A",
            "artifact_type": "simulation_output",
            "parent_artifact_ids": ["ART-B"],
            "lineage_depth": 1,
            "root_artifact_ids": ["ART-B"],
            "lineage_valid": False,
            "lineage_errors": ["circular"],
            "created_at": "2025-01-01T00:00:00+00:00",
            "created_by": "test",
            "version": "1.0.0",
        },
        "ART-B": {
            "artifact_id": "ART-B",
            "artifact_type": "simulation_output",
            "parent_artifact_ids": ["ART-A"],
            "lineage_depth": 1,
            "root_artifact_ids": ["ART-A"],
            "lineage_valid": False,
            "lineage_errors": ["circular"],
            "created_at": "2025-01-01T00:00:00+00:00",
            "created_by": "test",
            "version": "1.0.0",
        },
    }


def _valid_lineage_registry() -> Dict[str, Any]:
    """Return a fully valid lineage registry."""
    return {
        "SIM-IN-001": {
            "artifact_id": "SIM-IN-001",
            "artifact_type": "simulation_input",
            "parent_artifact_ids": [],
            "lineage_depth": 0,
            "root_artifact_ids": ["SIM-IN-001"],
            "lineage_valid": True,
            "lineage_errors": [],
            "created_at": "2025-01-01T00:00:00+00:00",
            "created_by": "test",
            "version": "1.0.0",
        },
        "SIM-OUT-001": {
            "artifact_id": "SIM-OUT-001",
            "artifact_type": "simulation_output",
            "parent_artifact_ids": ["SIM-IN-001"],
            "lineage_depth": 1,
            "root_artifact_ids": ["SIM-IN-001"],
            "lineage_valid": True,
            "lineage_errors": [],
            "created_at": "2025-01-01T00:00:00+00:00",
            "created_by": "test",
            "version": "1.0.0",
        },
    }


def test_compute_traceability_integrity_sli_invalid_registry_missing_parent():
    """Registry with a missing parent must yield sli=0.0, lineage_valid=False, non-empty errors."""
    sli_value, lineage_valid, lineage_errors = compute_traceability_integrity_sli(
        _registry_with_missing_parent()
    )
    assert sli_value == 0.0
    assert lineage_valid is False
    assert len(lineage_errors) > 0


def test_compute_traceability_integrity_sli_invalid_registry_circular():
    """Registry with a circular dependency must yield sli=0.0, lineage_valid=False, non-empty errors."""
    sli_value, lineage_valid, lineage_errors = compute_traceability_integrity_sli(
        _registry_with_circular_dep()
    )
    assert sli_value == 0.0
    assert lineage_valid is False
    assert len(lineage_errors) > 0


def test_run_slo_control_lineage_failure_blocks():
    """Invalid lineage registry must block execution: allowed_to_proceed=False, lineage_valid=False."""
    result = run_slo_control(
        be_inputs=[],
        bf_input=None,
        bg_input=None,
        lineage_registry=_registry_with_missing_parent(),
        parent_artifact_ids=["DEC-001"],
        created_at="2025-01-01T00:00:00+00:00",
    )
    assert result["allowed_to_proceed"] is False
    assert result["lineage_valid"] is False
    slo_artifact = result["slo_evaluation"]
    assert slo_artifact["lineage_valid"] is False
    assert slo_artifact["allowed_to_proceed"] is False
    violations = slo_artifact.get("violations", [])
    violation_names = [v["sli"] for v in violations]
    assert "traceability_integrity" in violation_names


def test_run_slo_control_valid_lineage_passes():
    """Fully valid lineage registry must yield lineage_valid=True."""
    result = run_slo_control(
        be_inputs=[],
        bf_input=None,
        bg_input=None,
        lineage_registry=_valid_lineage_registry(),
        parent_artifact_ids=["DEC-001"],
        created_at="2025-01-01T00:00:00+00:00",
    )
    assert result["lineage_valid"] is True
    assert result["slo_evaluation"]["lineage_valid"] is True
    slis = result["slo_evaluation"]["slis"]
    assert slis["traceability_integrity"] == 1.0


def test_parent_artifact_ids_propagation():
    """parent_artifact_ids passed to run_slo_control must appear exactly in the output artifact."""
    parent_ids = ["DEC-FIXED-001", "SYN-FIXED-001"]
    result = run_slo_control(
        be_inputs=[],
        bf_input=None,
        bg_input=None,
        parent_artifact_ids=parent_ids,
        created_at="2025-01-01T00:00:00+00:00",
    )
    artifact = result["slo_evaluation"]
    assert "parent_artifact_ids" in artifact
    assert artifact["parent_artifact_ids"] == parent_ids

