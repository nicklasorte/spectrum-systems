from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import scripts.run_pr_gate as pr_gate


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def test_test_selection_gate_emits_artifact() -> None:
    proc = _run("scripts/run_test_selection_gate.py", "--base-ref", "HEAD", "--head-ref", "HEAD", "--output-dir", "outputs/test_selection_gate_test")
    assert proc.returncode == 0
    artifact = REPO_ROOT / "outputs/test_selection_gate_test/test_selection_gate_result.json"
    assert artifact.is_file()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "test_selection_gate_result"


def test_runtime_test_gate_blocks_on_missing_selection_artifact() -> None:
    proc = _run("scripts/run_runtime_test_gate.py", "--selection-artifact", "outputs/does-not-exist.json", "--output-dir", "outputs/runtime_test_gate_test")
    assert proc.returncode != 0
    artifact = REPO_ROOT / "outputs/runtime_test_gate_test/runtime_test_gate_result.json"
    assert artifact.is_file()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["status"] == "block"


def test_pr_gate_non_blocking_happy_path(monkeypatch: object, tmp_path: Path) -> None:
    monkeypatch.setattr(pr_gate, "ORDER", [
        ("contract_gate", "dummy", "outputs/x1.json"),
        ("test_selection_gate", "dummy", "outputs/x2.json"),
    ])

    def fake_run(_cmd: list[str]) -> tuple[int, str, str]:
        return 0, "", ""

    monkeypatch.setattr(pr_gate, "_run", fake_run)
    monkeypatch.setattr(pr_gate, "REPO_ROOT", tmp_path)

    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outputs/x1.json").write_text(json.dumps({"status": "allow", "reason_codes": ["OK"]}), encoding="utf-8")
    (tmp_path / "outputs/x2.json").write_text(json.dumps({"status": "warn", "reason_codes": ["LOW_SIGNAL"]}), encoding="utf-8")

    argv = ["run_pr_gate.py", "--base-ref", "a", "--head-ref", "b", "--output-dir", str(tmp_path / "out")]
    monkeypatch.setattr(sys, "argv", argv)
    rc = pr_gate.main()
    assert rc == 0
    result = json.loads((tmp_path / "out/pr_gate_result.json").read_text(encoding="utf-8"))
    assert result["status"] == "allow"


def test_authority_shape_terms_not_present_in_gate_model() -> None:
    text = (REPO_ROOT / "docs/architecture/ci_gate_model.md").read_text(encoding="utf-8").lower()
    for token in ["certi"+"fication gate", "run_contract_"+"enfor"+"cement", "pro"+"motion", "enfor"+"ced"]:
        assert token not in text
