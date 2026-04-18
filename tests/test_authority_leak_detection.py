from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.authority_leak_rules import find_forbidden_vocabulary, load_authority_registry
from scripts.authority_shape_detector import detect_authority_shapes


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "contracts" / "governance" / "authority_registry.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_canonical_owner_authority_emission_passes() -> None:
    registry = load_authority_registry(REGISTRY_PATH)
    owner_file = REPO_ROOT / "spectrum_systems" / "modules" / "runtime" / "cde_decision_flow.py"
    original = owner_file.read_text(encoding="utf-8") if owner_file.exists() else ""
    owner_file.write_text(original + "\nOWNER_TEST = {'decision': 'allow', 'certification_status': 'certified'}\n", encoding="utf-8")
    try:
        assert find_forbidden_vocabulary(owner_file, registry) == []
        assert detect_authority_shapes(owner_file, registry) == []
    finally:
        owner_file.write_text(original, encoding="utf-8")


def test_non_owner_emits_authority_field_fails() -> None:
    registry = load_authority_registry(REGISTRY_PATH)
    test_file = REPO_ROOT / "spectrum_systems" / "modules" / "runtime" / "tmp_non_owner_authority.py"
    test_file.write_text("payload = {'decision': 'allow'}\n", encoding="utf-8")
    try:
        violations = find_forbidden_vocabulary(test_file, registry)
        assert any(v["rule"] == "forbidden_field" and v["token"] == "decision" for v in violations)
    finally:
        test_file.unlink(missing_ok=True)


def test_disguised_authority_shape_fails() -> None:
    registry = load_authority_registry(REGISTRY_PATH)
    payload = {
        "artifact_type": "runtime_observation",
        "observation": "counts only",
        "decision": "allow",
        "enforcement_action": "freeze",
    }
    path = REPO_ROOT / "contracts" / "examples" / "tmp_disguised_authority_shape.json"
    _write_json(path, payload)
    try:
        violations = detect_authority_shapes(path, registry)
        assert any(v["rule"] == "authority_shape_outcome_action" for v in violations)
    finally:
        path.unlink(missing_ok=True)


def test_fxa_1100_transcript_regression_case_fails() -> None:
    registry = load_authority_registry(REGISTRY_PATH)
    payload = {
        "artifact_type": "transcript_control_input_signal",
        "non_authority_assertions": [
            "preparatory_only",
            "not_control_authority",
            "not_certification_authority",
        ],
        "observations": ["candidate signal"],
        "replay_hash": "abc123",
        "decision": "allow",
    }
    path = REPO_ROOT / "contracts" / "examples" / "tmp_transcript_control_input_signal_regression.json"
    _write_json(path, payload)
    try:
        violations = detect_authority_shapes(path, registry)
        assert any(v["rule"] == "preparatory_contains_authority" for v in violations)
    finally:
        path.unlink(missing_ok=True)


def test_authority_leak_guard_cli_fails_on_non_owner_authority() -> None:
    violator = REPO_ROOT / "spectrum_systems" / "modules" / "runtime" / "tmp_authority_violator.py"
    violator.write_text("payload = {'decision': 'allow', 'enforcement_action': 'freeze'}\n", encoding="utf-8")
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/run_authority_leak_guard.py",
                "--changed-files",
                "spectrum_systems/modules/runtime/tmp_authority_violator.py",
                "--output",
                "outputs/authority_leak_guard/test_authority_leak_guard_result.json",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1
        assert "forbidden_field" in (proc.stdout + proc.stderr)
    finally:
        violator.unlink(missing_ok=True)


def test_bne_fix_evidence_examples_are_authority_clean() -> None:
    registry = load_authority_registry(REGISTRY_PATH)
    for rel in (
        "contracts/examples/global_invariant_check_record.json",
        "contracts/examples/eval_coverage_artifact.json",
        "contracts/examples/promotion_gate_evidence_record.json",
        "contracts/examples/certification_evidence_record.json",
    ):
        path = REPO_ROOT / rel
        assert find_forbidden_vocabulary(path, registry) == []
        assert detect_authority_shapes(path, registry) == []
