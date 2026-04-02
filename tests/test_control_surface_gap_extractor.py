from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.control_surface_gap_extractor import (
    ControlSurfaceGapExtractionError,
    extract_control_surface_gap_packet,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_example(name: str) -> dict:
    path = _REPO_ROOT / "contracts" / "examples" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_inputs() -> tuple[dict, dict, dict, dict, dict]:
    manifest = _load_example("control_surface_manifest")
    enforcement = _load_example("control_surface_enforcement_result")
    obedience = _load_example("control_surface_obedience_result")
    trust_spine = _load_example("trust_spine_evidence_cohesion_result")
    done_certification = _load_example("done_certification_record")
    return manifest, enforcement, obedience, trust_spine, done_certification


def _build_packet() -> dict:
    manifest, enforcement, obedience, trust_spine, done_certification = _valid_inputs()
    return extract_control_surface_gap_packet(
        manifest=manifest,
        enforcement_result=enforcement,
        obedience_result=obedience,
        trust_spine_result=trust_spine,
        done_certification_record=done_certification,
        generated_at="2026-04-02T00:00:00Z",
        trace_id="trace-con-034-test",
    )


def test_happy_path_no_gaps() -> None:
    packet = _build_packet()
    assert packet["overall_decision"] == "ALLOW"
    assert packet["gap_count"] == 0
    assert packet["blocking_gap_count"] == 0


def test_enforcement_block_produces_blocking_gap() -> None:
    manifest, enforcement, obedience, trust_spine, done_certification = _valid_inputs()
    enforcement["enforcement_status"] = "BLOCK"
    enforcement["surfaces_missing_invariants"] = ["contract_preflight_gate"]

    packet = extract_control_surface_gap_packet(
        manifest=manifest,
        enforcement_result=enforcement,
        obedience_result=obedience,
        trust_spine_result=trust_spine,
        done_certification_record=done_certification,
        generated_at="2026-04-02T00:00:00Z",
        trace_id="trace-con-034-test",
    )
    categories = {gap["gap_category"] for gap in packet["gaps"]}
    assert "enforcement_block" in categories
    assert packet["overall_decision"] == "BLOCK"


def test_obedience_insufficient_evidence_produces_blocking_gap() -> None:
    manifest, enforcement, obedience, trust_spine, done_certification = _valid_inputs()
    obedience["overall_decision"] = "BLOCK"
    obedience["missing_obedience_evidence"] = ["sequence_transition_promotion:missing signal"]
    obedience["blocking_reasons"] = ["sequence_transition_promotion:missing signal"]

    packet = extract_control_surface_gap_packet(
        manifest=manifest,
        enforcement_result=enforcement,
        obedience_result=obedience,
        trust_spine_result=trust_spine,
        done_certification_record=done_certification,
        generated_at="2026-04-02T00:00:00Z",
        trace_id="trace-con-034-test",
    )
    categories = {gap["gap_category"] for gap in packet["gaps"]}
    assert "insufficient_runtime_evidence" in categories
    assert "obedience_block" in categories


def test_trust_spine_contradiction_produces_blocking_gap() -> None:
    manifest, enforcement, obedience, trust_spine, done_certification = _valid_inputs()
    trust_spine["overall_decision"] = "BLOCK"
    trust_spine["blocking_reasons"] = ["TRUST_SPINE_POLICY_AUTHORITY_CONTRADICTION"]

    packet = extract_control_surface_gap_packet(
        manifest=manifest,
        enforcement_result=enforcement,
        obedience_result=obedience,
        trust_spine_result=trust_spine,
        done_certification_record=done_certification,
        generated_at="2026-04-02T00:00:00Z",
        trace_id="trace-con-034-test",
    )
    assert any(gap["gap_category"] == "trust_spine_contradiction" for gap in packet["gaps"])
    assert packet["overall_decision"] == "BLOCK"


def test_malformed_input_fails_closed() -> None:
    manifest, enforcement, obedience, trust_spine, done_certification = _valid_inputs()
    enforcement["enforcement_status"] = "WARN"

    with pytest.raises(ControlSurfaceGapExtractionError, match="schema validation"):
        extract_control_surface_gap_packet(
            manifest=manifest,
            enforcement_result=enforcement,
            obedience_result=obedience,
            trust_spine_result=trust_spine,
            done_certification_record=done_certification,
            generated_at="2026-04-02T00:00:00Z",
            trace_id="trace-con-034-test",
        )


def test_deterministic_output_identity_stable() -> None:
    first = _build_packet()
    second = _build_packet()
    assert first["artifact_id"] == second["artifact_id"]
    assert first["gaps"] == second["gaps"]


def test_cli_writes_packet_and_exit_code() -> None:
    output_path = _REPO_ROOT / "outputs" / "control_surface_gap_packet" / "pytest-control_surface_gap_packet.json"
    if output_path.exists():
        output_path.unlink()

    cmd = [
        sys.executable,
        "scripts/build_control_surface_gap_packet.py",
        "--manifest",
        "contracts/examples/control_surface_manifest.json",
        "--enforcement",
        "contracts/examples/control_surface_enforcement_result.json",
        "--obedience",
        "contracts/examples/control_surface_obedience_result.json",
        "--trust-spine",
        "contracts/examples/trust_spine_evidence_cohesion_result.json",
        "--done-certification",
        "contracts/examples/done_certification_record.json",
        "--output",
        str(output_path),
        "--generated-at",
        "2026-04-02T00:00:00Z",
        "--trace-id",
        "trace-con-034-cli",
    ]
    proc = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert output_path.is_file()


def test_schema_and_example_validate() -> None:
    schema = load_schema("control_surface_gap_packet")
    example = _load_example("control_surface_gap_packet")

    from jsonschema import Draft202012Validator, FormatChecker

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)


def test_standards_manifest_registers_gap_packet_contract() -> None:
    manifest = json.loads((_REPO_ROOT / "contracts" / "standards-manifest.json").read_text(encoding="utf-8"))
    contracts = manifest.get("contracts", [])
    match = [entry for entry in contracts if entry.get("artifact_type") == "control_surface_gap_packet"]
    assert len(match) == 1
    assert match[0]["example_path"] == "contracts/examples/control_surface_gap_packet.json"
