import json
from pathlib import Path


def test_regression_pack_fixtures_exist() -> None:
    root = Path("tests/fixtures/trust_regression_pack")
    assert (root / "pass_proof.json").exists()
    assert (root / "block_proof.json").exists()
    assert (root / "freeze_proof.json").exists()


def test_regression_pack_statuses_cover_core_paths() -> None:
    root = Path("tests/fixtures/trust_regression_pack")
    statuses = {json.loads((root / name).read_text())["final_status"] for name in ["pass_proof.json", "block_proof.json", "freeze_proof.json"]}
    assert statuses == {"pass", "block", "freeze"}
