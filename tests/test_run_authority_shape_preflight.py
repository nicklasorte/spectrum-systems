"""CLI surface tests for ``scripts/run_authority_shape_preflight.py``.

These tests prove the preflight CLI is dependency-light: it does not import the
``spectrum_systems.governance`` package ``__init__`` (which transitively
requires ``jsonschema``), and the script runs in a subprocess where
``jsonschema`` is shadowed to ``ImportError``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from scripts import run_authority_shape_preflight as preflight_cli
from scripts import run_authority_shape_early_gate as early_gate_cli

REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_args(**overrides):
    defaults = {
        "base_ref": "base",
        "head_ref": "head",
        "changed_files": [],
        "vocabulary": "contracts/governance/authority_shape_vocabulary.json",
        "output": "outputs/authority_shape_preflight/_test_result.json",
        "mode": "suggest-only",
    }
    defaults.update(overrides)
    return type("Args", (), defaults)()


def test_cli_returns_zero_when_no_violations(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"
    monkeypatch.setattr(
        preflight_cli,
        "_parse_args",
        lambda: _make_args(output=str(output_path), mode="suggest-only"),
    )
    monkeypatch.setattr(
        preflight_cli,
        "resolve_changed_files",
        lambda **_: [],
    )
    rc = preflight_cli.main()
    assert rc == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["mode"] == "suggest-only"


def test_cli_returns_nonzero_on_violation(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"
    repo_root = preflight_cli.REPO_ROOT
    sandbox_rel = "scripts/_tmp_authority_shape_violation.py"
    sandbox_path = repo_root / sandbox_rel
    sandbox_path.parent.mkdir(parents=True, exist_ok=True)
    sandbox_path.write_text("promotion_decision = 'pending'\n", encoding="utf-8")

    monkeypatch.setattr(
        preflight_cli,
        "_parse_args",
        lambda: _make_args(output=str(output_path), mode="suggest-only"),
    )
    monkeypatch.setattr(
        preflight_cli,
        "resolve_changed_files",
        lambda **_: [sandbox_rel],
    )
    try:
        rc = preflight_cli.main()
    finally:
        sandbox_path.unlink(missing_ok=True)
    assert rc == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert payload["summary"]["violation_count"] >= 1
    assert any(v["cluster"] in {"promotion", "decision"} for v in payload["violations"])


def test_cli_does_not_import_governance_package_init() -> None:
    """The script must not pull in ``spectrum_systems.governance`` ``__init__``.

    That package eagerly imports ``contract_impact``, which requires
    ``jsonschema``. The preflight is wired to bypass it by file path so it can
    run on the minimal CI surface.
    """
    code = textwrap.dedent(
        """
        import sys
        sys.path.insert(0, %r)
        import scripts.run_authority_shape_preflight  # noqa: F401
        assert "spectrum_systems.governance" not in sys.modules, (
            "preflight CLI must not load spectrum_systems.governance __init__"
        )
        # The script must not have spectrum_systems.contracts in sys.modules
        # because that subtree requires jsonschema.
        assert "spectrum_systems.contracts" not in sys.modules
        print("ok")
        """
    ) % (str(REPO_ROOT),)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_cli_runs_without_jsonschema(tmp_path: Path) -> None:
    """The script must complete end-to-end when ``jsonschema`` is unavailable.

    A meta-path finder shadowed in the subprocess raises ``ImportError`` for
    any ``jsonschema`` import. The preflight must still pass on a clean change
    set and still fail-closed on an authority-shaped leak.
    """
    output = tmp_path / "result.json"
    leak_rel = "scripts/_tmp_no_jsonschema_violation.py"
    leak_path = REPO_ROOT / leak_rel
    leak_path.parent.mkdir(parents=True, exist_ok=True)
    leak_path.write_text("promotion_decision = 'pending'\n", encoding="utf-8")
    safe_rel = "scripts/_tmp_no_jsonschema_safe.py"
    safe_path = REPO_ROOT / safe_rel
    safe_path.write_text("promotion_signal = 'observation_only'\n", encoding="utf-8")
    try:
        runner = textwrap.dedent(
            """
            import sys

            class _JsonSchemaBlocker:
                def find_spec(self, name, *args, **kwargs):
                    if name == "jsonschema" or name.startswith("jsonschema."):
                        raise ImportError("blocked by test: " + name)
                    return None

            sys.meta_path.insert(0, _JsonSchemaBlocker())
            sys.path.insert(0, %r)
            import runpy

            sys.argv = [
                "run_authority_shape_preflight.py",
                "--changed-files",
                %r,
                %r,
                "--suggest-only",
                "--output",
                %r,
            ]
            try:
                runpy.run_path(%r, run_name="__main__")
            except SystemExit as exc:
                print("EXIT:" + str(exc.code))
            """
        ) % (
            str(REPO_ROOT),
            leak_rel,
            safe_rel,
            str(output),
            str(REPO_ROOT / "scripts" / "run_authority_shape_preflight.py"),
        )
        result = subprocess.run(
            [sys.executable, "-c", runner],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert "EXIT:1" in result.stdout, (
            f"expected fail-closed exit when leak present; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["status"] == "fail"
        assert any(v["file"] == leak_rel for v in payload["violations"])
        assert all(v["file"] != safe_rel for v in payload["violations"]), (
            "non-owner using promotion_signal must not be flagged"
        )
    finally:
        leak_path.unlink(missing_ok=True)
        safe_path.unlink(missing_ok=True)


def test_cli_propagates_changed_file_resolution_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        preflight_cli,
        "_parse_args",
        lambda: _make_args(output=str(tmp_path / "result.json")),
    )

    def _raise(**_kwargs):
        raise preflight_cli.ChangedFilesResolutionError("bad refs")

    monkeypatch.setattr(preflight_cli, "resolve_changed_files", _raise)
    try:
        preflight_cli.main()
    except preflight_cli.AuthorityShapePreflightError as exc:
        assert "bad refs" in str(exc)
    else:
        raise AssertionError("expected AuthorityShapePreflightError")


def _make_early_gate_args(**overrides):
    defaults = {
        "base_ref": "base",
        "head_ref": "head",
        "changed_files": [],
        "output": "outputs/authority_shape_preflight/authority_shape_early_gate_result.json",
        "owner_registry": "docs/architecture/system_registry.md",
    }
    defaults.update(overrides)
    return type("Args", (), defaults)()


def test_early_gate_cli_writes_structured_artifact(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "authority_shape_early_gate_result.json"
    repo_root = early_gate_cli.REPO_ROOT
    changed_rel = "contracts/rfx/authority_shape_example.md"
    changed_path = repo_root / changed_rel
    changed_path.parent.mkdir(parents=True, exist_ok=True)
    changed_path.write_text("decision should be avoided in RFX files\n", encoding="utf-8")
    try:
        monkeypatch.setattr(
            early_gate_cli,
            "_parse_args",
            lambda: _make_early_gate_args(output=str(output_path)),
        )
        monkeypatch.setattr(
            early_gate_cli,
            "resolve_changed_files",
            lambda **_: [changed_rel],
        )
        rc = early_gate_cli.main()
    finally:
        changed_path.unlink(missing_ok=True)
    assert rc == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "authority_shape_early_gate_result"
    assert payload["summary"]["review_required_count"] >= 1


def test_early_gate_cli_propagates_changed_file_resolution_error(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        early_gate_cli,
        "_parse_args",
        lambda: _make_early_gate_args(output=str(tmp_path / "result.json")),
    )

    def _raise(**_kwargs):
        raise early_gate_cli.ChangedFilesResolutionError("broken refs")

    monkeypatch.setattr(early_gate_cli, "resolve_changed_files", _raise)
    try:
        early_gate_cli.main()
    except early_gate_cli.AuthorityShapeEarlyGateError as exc:
        assert "broken refs" in str(exc)
    else:
        raise AssertionError("expected AuthorityShapeEarlyGateError")
