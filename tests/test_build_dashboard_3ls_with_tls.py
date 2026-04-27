from __future__ import annotations

from pathlib import Path

import scripts.build_dashboard_3ls_with_tls as wrapper


def test_returns_tls_exit_code_when_tls_generation_fails(monkeypatch):
    def fake_run(cmd: list[str], cwd: Path, env=None) -> int:
        if "build_tls_dependency_priority.py" in " ".join(cmd):
            return 17
        return 0

    monkeypatch.setattr(wrapper, "_run", fake_run)
    rc = wrapper.main(["--skip-next-build"])
    assert rc == 17


def test_fails_closed_when_artifact_missing_after_successful_tls_step(monkeypatch, tmp_path):
    monkeypatch.setattr(wrapper, "_run", lambda cmd, cwd, env=None: 0)
    monkeypatch.setattr(wrapper, "artifact_path", lambda: tmp_path / "missing.json")
    rc = wrapper.main(["--skip-next-build"])
    assert rc == 1


def test_fails_closed_when_registry_input_missing(monkeypatch, tmp_path):
    run_called = {"value": False}

    def fake_run(cmd: list[str], cwd: Path, env=None) -> int:
        run_called["value"] = True
        return 0

    monkeypatch.setattr(wrapper, "_run", fake_run)
    monkeypatch.setattr(wrapper, "registry_path", lambda: tmp_path / "missing_registry.md")
    rc = wrapper.main(["--skip-next-build"])
    assert rc == 1
    assert run_called["value"] is False


def test_invokes_next_step_builder_after_tls(monkeypatch, tmp_path):
    calls: list[tuple[list[str], Path, dict | None]] = []
    tls_artifact = tmp_path / "artifacts" / "system_dependency_priority_report.json"
    next_artifact = tmp_path / "artifacts" / "next_step_decision_report.json"
    tls_artifact.parent.mkdir(parents=True, exist_ok=True)
    tls_artifact.write_text("{}", encoding="utf-8")
    next_artifact.write_text("{}", encoding="utf-8")

    def fake_run(cmd: list[str], cwd: Path, env=None) -> int:
        calls.append((cmd, cwd, env))
        return 0

    monkeypatch.setattr(wrapper, "_run", fake_run)
    monkeypatch.setattr(wrapper, "artifact_path", lambda: tls_artifact)
    monkeypatch.setattr(wrapper, "next_step_artifact_path", lambda: next_artifact)
    rc = wrapper.main(["--skip-next-build"])

    assert rc == 0
    assert calls[0][0][1].endswith("/scripts/build_tls_dependency_priority.py")
    assert calls[1][0][1].endswith("/scripts/build_next_step_decision.py")


def test_fails_when_next_step_artifact_missing_after_success(monkeypatch, tmp_path):
    tls_artifact = tmp_path / "artifacts" / "system_dependency_priority_report.json"
    tls_artifact.parent.mkdir(parents=True, exist_ok=True)
    tls_artifact.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(wrapper, "_run", lambda cmd, cwd, env=None: 0)
    monkeypatch.setattr(wrapper, "artifact_path", lambda: tls_artifact)
    monkeypatch.setattr(wrapper, "next_step_artifact_path", lambda: tmp_path / "artifacts" / "missing_next_step.json")
    rc = wrapper.main(["--skip-next-build"])
    assert rc == 1


def test_skip_next_step_bypasses_only_when_explicit(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    tls_artifact = tmp_path / "artifacts" / "system_dependency_priority_report.json"
    tls_artifact.parent.mkdir(parents=True, exist_ok=True)
    tls_artifact.write_text("{}", encoding="utf-8")

    def fake_run(cmd: list[str], cwd: Path, env=None) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(wrapper, "_run", fake_run)
    monkeypatch.setattr(wrapper, "artifact_path", lambda: tls_artifact)
    rc = wrapper.main(["--skip-next-build", "--skip-next-step"])
    assert rc == 0
    joined = "\n".join(" ".join(cmd) for cmd in calls)
    assert "build_tls_dependency_priority.py" in joined
    assert "build_next_step_decision.py" not in joined
