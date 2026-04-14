from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import scripts.run_contract_preflight as preflight
from spectrum_systems.contracts import validate_artifact

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_preflight_wrapper_builder_stays_compatible_with_governed_preflight(tmp_path: Path, monkeypatch) -> None:
    wrapper_rel = "outputs/contract_preflight/test_preflight_wrapper_compat.json"
    wrapper_path = REPO_ROOT / wrapper_rel
    build = subprocess.run(
        [
            sys.executable,
            "scripts/build_preflight_pqx_wrapper.py",
            "--base-ref",
            "HEAD~1",
            "--head-ref",
            "HEAD",
            "--changed-path",
            "scripts/build_preflight_pqx_wrapper.py",
            "--output",
            wrapper_rel,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr or build.stdout

    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
    validate_artifact(wrapper, "codex_pqx_task_wrapper")
    assert wrapper["governance"]["authority_evidence_ref"] == "artifacts/pqx_runs/preflight.pqx_slice_execution_record.json"

    output_dir = tmp_path / "preflight-out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "event_name": "push",
                "base_ref": "HEAD",
                "head_ref": "HEAD",
                "changed_path": ["scripts/build_preflight_pqx_wrapper.py"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": "artifacts/pqx_runs/preflight.pqx_slice_execution_record.json",
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=["scripts/build_preflight_pqx_wrapper.py"],
            changed_path_detection_mode="explicit_paths",
            refs_attempted=[],
            fallback_used=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        preflight,
        "build_impact_map",
        lambda *_args, **_kwargs: {
            "producers": [],
            "fixtures_or_builders": [],
            "consumers": [],
            "required_smoke_tests": [],
            "contract_impact_artifact": {},
        },
    )
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 0
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
