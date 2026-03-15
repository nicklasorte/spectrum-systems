import json
from pathlib import Path

import pytest

from scripts import validate_governance_manifest as governance_validator

REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_MANIFEST = REPO_ROOT / "governance" / "examples" / "manifests" / "comment-resolution-engine.spectrum-governance.json"


def load_manifest() -> dict:
    return json.loads(VALID_MANIFEST.read_text(encoding="utf-8"))


def test_validator_accepts_valid_manifest() -> None:
    result = governance_validator.validate_manifest(VALID_MANIFEST)
    assert result["status"] == "pass"
    assert not result["errors"]


def test_validator_rejects_unknown_system_id(tmp_path: Path) -> None:
    manifest = load_manifest()
    manifest["system_id"] = "unknown-system"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = governance_validator.validate_manifest(manifest_path)
    assert result["status"] == "fail"
    assert any("Unknown system_id" in error for error in result["errors"])


def test_validator_rejects_unknown_contract(tmp_path: Path) -> None:
    manifest = load_manifest()
    manifest["contracts"]["nonexistent_contract"] = "1.0.0"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = governance_validator.validate_manifest(manifest_path)
    assert result["status"] == "fail"
    assert any("Unknown contract nonexistent_contract" in error for error in result["errors"])
