from __future__ import annotations

from pathlib import Path

import scripts.build_dashboard_3ls_with_tls as wrapper


def test_returns_tls_exit_code_when_tls_generation_fails(monkeypatch):
    def fake_run(cmd: list[str], cwd: Path) -> int:
        if "build_tls_dependency_priority.py" in " ".join(cmd):
            return 17
        return 0

    monkeypatch.setattr(wrapper, "_run", fake_run)
    rc = wrapper.main(["--skip-next-build"])
    assert rc == 17


def test_fails_closed_when_artifact_missing_after_successful_tls_step(monkeypatch, tmp_path):
    monkeypatch.setattr(wrapper, "_run", lambda cmd, cwd: 0)
    monkeypatch.setattr(wrapper, "artifact_path", lambda: tmp_path / "missing.json")
    rc = wrapper.main(["--skip-next-build"])
    assert rc == 1


def test_invokes_next_build_after_tls_and_artifact_check(monkeypatch, tmp_path):
    calls: list[tuple[list[str], Path]] = []
    artifact = tmp_path / "artifacts" / "system_dependency_priority_report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{}", encoding="utf-8")

    def fake_run(cmd: list[str], cwd: Path) -> int:
        calls.append((cmd, cwd))
        return 0

    monkeypatch.setattr(wrapper, "_run", fake_run)
    monkeypatch.setattr(wrapper, "artifact_path", lambda: artifact)
    rc = wrapper.main([])

    assert rc == 0
    assert calls[0][0][1] == "scripts/build_tls_dependency_priority.py"
    assert calls[1][0] == ["next", "build"]
