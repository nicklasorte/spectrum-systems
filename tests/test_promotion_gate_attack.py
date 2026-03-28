"""Tests for VAL-01 promotion gate attack validation module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from spectrum_systems.modules.governance import promotion_gate_attack as pga

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DECISION_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "evaluation_enforcement_bridge" / "decision_allow.json"
_CERTIFICATION_FIXTURE = _REPO_ROOT / "contracts" / "examples" / "done_certification_record.json"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _prepare_refs(tmp_path: Path) -> Dict[str, str]:
    decision = _load_json(_DECISION_FIXTURE)
    certification = _load_json(_CERTIFICATION_FIXTURE)
    decision_path = _write_json(tmp_path / "decision.json", decision)
    certification_path = _write_json(tmp_path / "done_certification_valid.json", certification)
    return {
        "enforcement_input_ref": decision_path,
        "valid_done_certification_ref": certification_path,
    }


def _case(result: Dict[str, Any], case_type: str) -> Dict[str, Any]:
    return next(case for case in result["attack_cases"] if case["case_type"] == case_type)


def test_missing_certification_blocks(tmp_path: Path) -> None:
    result = pga.run_promotion_gate_attack(_prepare_refs(tmp_path))
    case = _case(result, "missing_certification")
    assert case["actual_outcome"] == "block"
    assert case["passed"] is True


def test_malformed_certification_blocks(tmp_path: Path) -> None:
    refs = _prepare_refs(tmp_path)
    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text("{\"broken\":", encoding="utf-8")
    refs["malformed_done_certification_ref"] = str(malformed_path)

    result = pga.run_promotion_gate_attack(refs)
    case = _case(result, "malformed_certification")
    assert case["actual_outcome"] == "block"
    assert case["passed"] is True


def test_failed_certification_blocks(tmp_path: Path) -> None:
    refs = _prepare_refs(tmp_path)
    failed = _load_json(Path(refs["valid_done_certification_ref"]))
    failed["final_status"] = "FAILED"
    failed["system_response"] = "block"
    failed["blocking_reasons"] = ["failed done certification"]
    refs["failed_done_certification_ref"] = _write_json(tmp_path / "failed.json", failed)

    result = pga.run_promotion_gate_attack(refs)
    case = _case(result, "failed_certification")
    assert case["actual_outcome"] == "block"
    assert case["passed"] is True


def test_incomplete_certification_blocks(tmp_path: Path) -> None:
    result = pga.run_promotion_gate_attack(_prepare_refs(tmp_path))
    case = _case(result, "structurally_valid_but_incomplete_certification")
    assert case["actual_outcome"] == "block"
    assert case["passed"] is True


def test_mismatched_trace_blocks(tmp_path: Path) -> None:
    result = pga.run_promotion_gate_attack(_prepare_refs(tmp_path))
    case = _case(result, "mismatched_trace_certification")
    assert case["actual_outcome"] == "block"
    assert case["passed"] is True


def test_corrupted_payload_blocks(tmp_path: Path) -> None:
    result = pga.run_promotion_gate_attack(_prepare_refs(tmp_path))
    case = _case(result, "corrupted_certification_payload")
    assert case["actual_outcome"] == "block"
    assert case["passed"] is True


def test_any_bypass_marks_attack_failed(tmp_path: Path, monkeypatch) -> None:
    refs = _prepare_refs(tmp_path)

    original_bridge = pga.run_enforcement_bridge

    def _bypass(path: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if context and context.get("done_certification_path") is None:
            return {
                "action_id": "attack-bypass-001",
                "decision_id": "decision-allow-001",
                "summary_id": "summary-allow-001",
                "status": "advisory",
                "action_type": "allow",
                "enforcement_scope": "promotion",
                "allowed_to_proceed": True,
                "reasons": ["bypass"],
                "required_human_actions": [],
                "certification_gate": {
                    "artifact_reference": "missing",
                    "certification_decision": "missing",
                    "certification_status": "missing",
                    "block_reason": "bypass",
                },
                "created_at": "2026-03-28T00:00:00Z",
            }
        return original_bridge(path, context=context)

    monkeypatch.setattr(pga, "run_enforcement_bridge", _bypass)

    result = pga.run_promotion_gate_attack(refs)
    assert result["summary"]["bypass_detected"] is True
    assert result["final_status"] == "FAILED"
