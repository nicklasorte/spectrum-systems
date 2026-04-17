from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.pra_nsx_prg_loop import (
    PRAnchorError,
    build_pr_delta,
    build_resolution_failure_record,
    con_workflow_coverage_audit,
    get_repo_name,
    parse_pr_override,
    resolve_pull_request,
)


def _fixture(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_resolve_latest_pr_deterministically() -> None:
    payload = _fixture("tests/fixtures/pra_nsx_prg_pr_input.json")
    resolution, _ = resolve_pull_request(
        pull_requests=payload["pull_requests"],
        repo_name=payload["repo_name"],
    )
    assert resolution["pr_number"] == 1106
    assert resolution["selection_mode"] == "default_latest"


def test_resolve_override_deterministically() -> None:
    payload = _fixture("tests/fixtures/pra_nsx_prg_pr_input.json")
    override = parse_pr_override(pr_number=1105, pr_url="https://github.com/acme/spectrum-systems/pull/1105")
    resolution, _ = resolve_pull_request(
        pull_requests=payload["pull_requests"],
        repo_name=payload["repo_name"],
        override=override,
    )
    assert resolution["pr_number"] == 1105
    assert resolution["override_used"] is True


def test_override_cannot_be_silently_ignored() -> None:
    payload = _fixture("tests/fixtures/pra_nsx_prg_pr_input.json")
    override = parse_pr_override(pr_number=9999)
    try:
        resolve_pull_request(pull_requests=payload["pull_requests"], repo_name=payload["repo_name"], override=override)
    except PRAnchorError as exc:
        assert str(exc) == "override_pr_not_found"
    else:
        raise AssertionError("expected fail-closed override path")


def test_workflow_coverage_audit_flags_unrouted_pytest(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "test.yml").write_text("jobs:\n  test:\n    steps:\n      - run: pytest -q\n", encoding="utf-8")
    audit = con_workflow_coverage_audit(repo_root=tmp_path)
    assert audit["status"] == "fail"
    assert audit["uncovered_workflows"] == [".github/workflows/test.yml"]


def test_workflow_coverage_audit_includes_yaml_extension(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "a.yml").write_text("jobs:\n  test:\n    steps:\n      - run: pytest -q\n", encoding="utf-8")
    (wf / "b.yaml").write_text("jobs:\n  test:\n    steps:\n      - run: pytest -q\n", encoding="utf-8")
    audit = con_workflow_coverage_audit(repo_root=tmp_path)
    assert audit["status"] == "fail"
    assert audit["workflows_checked"] == [".github/workflows/a.yml", ".github/workflows/b.yaml"]
    assert audit["uncovered_workflows"] == [".github/workflows/a.yml", ".github/workflows/b.yaml"]


def test_resolution_failure_record_is_schema_valid() -> None:
    payload = build_resolution_failure_record(repo_name="acme/spectrum-systems", reason="no_resolvable_pr_anchor")
    validate_artifact(payload, "pra_pull_request_resolution_record")
    assert payload["pr_number"] == 0
    assert payload["selected_pr_reason"] == "resolution_failed:no_resolvable_pr_anchor"
    assert payload["state"] == "unresolved"


def test_script_emits_schema_valid_failure_record_for_empty_prs(tmp_path: Path) -> None:
    input_path = tmp_path / "prs.json"
    out = tmp_path / "out"
    input_path.write_text(json.dumps({"repo_name": "acme/spectrum-systems", "pull_requests": []}), encoding="utf-8")
    proc = subprocess.run(
        ["python", "scripts/run_pra_nsx_prg_automation.py", "--pr-input", str(input_path), "--output-dir", str(out)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    payload = json.loads((out / "pra_pull_request_resolution_record.json").read_text(encoding="utf-8"))
    validate_artifact(payload, "pra_pull_request_resolution_record")
    assert payload["selected_pr_reason"] == "resolution_failed:no_resolvable_pr_anchor"


def test_script_emits_schema_valid_failure_record_for_unmatched_override(tmp_path: Path) -> None:
    input_path = tmp_path / "prs.json"
    out = tmp_path / "out"
    input_path.write_text(json.dumps(_fixture("tests/fixtures/pra_nsx_prg_pr_input.json")), encoding="utf-8")
    proc = subprocess.run(
        [
            "python",
            "scripts/run_pra_nsx_prg_automation.py",
            "--pr-input",
            str(input_path),
            "--output-dir",
            str(out),
            "--pr-number",
            "9999",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    payload = json.loads((out / "pra_pull_request_resolution_record.json").read_text(encoding="utf-8"))
    validate_artifact(payload, "pra_pull_request_resolution_record")
    assert payload["selected_pr_reason"] == "resolution_failed:override_pr_not_found"


def test_build_pr_delta_supports_previous_anchor_and_impact_mapping() -> None:
    current_anchor = _fixture("contracts/examples/pra_pull_request_anchor_record.json")
    impact = _fixture("contracts/examples/pra_system_impact_mapping_record.json")
    previous_anchor = dict(current_anchor)
    previous_anchor["changed_files"] = ["scripts/run_shift_left_preflight.py"]
    delta_from_anchor = build_pr_delta(previous_anchor=previous_anchor, current_anchor=current_anchor, impact=impact)
    assert isinstance(delta_from_anchor["new_systems_touched"], list)

    previous_impact = _fixture("contracts/examples/pra_system_impact_mapping_record.json")
    previous_impact["impacted_systems"] = ["GEN"]
    delta_from_impact = build_pr_delta(previous_anchor=previous_impact, current_anchor=current_anchor, impact=impact)
    assert isinstance(delta_from_impact["new_systems_touched"], list)


def test_build_pr_delta_fails_closed_on_incompatible_previous_artifact() -> None:
    current_anchor = _fixture("contracts/examples/pra_pull_request_anchor_record.json")
    impact = _fixture("contracts/examples/pra_system_impact_mapping_record.json")
    incompatible = {"artifact_type": "pra_pull_request_delta_record"}
    try:
        build_pr_delta(previous_anchor=incompatible, current_anchor=current_anchor, impact=impact)
    except PRAnchorError as exc:
        assert str(exc) == "previous_artifact_incompatible_for_delta_comparison"
    else:
        raise AssertionError("expected incompatible previous artifact to fail closed")


def test_script_fails_closed_on_incompatible_previous_artifact(tmp_path: Path) -> None:
    input_path = tmp_path / "prs.json"
    previous_path = tmp_path / "previous.json"
    out = tmp_path / "out"
    input_path.write_text(json.dumps(_fixture("tests/fixtures/pra_nsx_prg_pr_input.json")), encoding="utf-8")
    previous_path.write_text(json.dumps({"artifact_type": "pra_pull_request_delta_record"}), encoding="utf-8")
    proc = subprocess.run(
        [
            "python",
            "scripts/run_pra_nsx_prg_automation.py",
            "--pr-input",
            str(input_path),
            "--output-dir",
            str(out),
            "--previous-anchor",
            str(previous_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "previous_artifact_incompatible_for_delta_comparison" in proc.stdout


def test_get_repo_name_parsing(monkeypatch) -> None:
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pra_nsx_prg_loop.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="git@github.com:acme/widget.git\n"),
    )
    assert get_repo_name(Path(".")) == "acme/widget"

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pra_nsx_prg_loop.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="https://github.com/acme/widget.git\n"),
    )
    assert get_repo_name(Path(".")) == "acme/widget"

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pra_nsx_prg_loop.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="https://github.com/acme/widget\n"),
    )
    assert get_repo_name(Path(".")) == "acme/widget"


def test_chain_script_emits_schema_valid_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "out"
    proc = subprocess.run(
        [
            "python",
            "scripts/run_pra_nsx_prg_automation.py",
            "--pr-input",
            "tests/fixtures/pra_nsx_prg_pr_input.json",
            "--output-dir",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode in {0, 1}

    names = [
        "pra_pull_request_resolution_record",
        "pra_pull_request_anchor_record",
        "pra_changed_scope_extraction_record",
        "pra_ci_review_extraction_record",
        "pra_system_impact_mapping_record",
        "pra_pull_request_delta_record",
        "nsx_next_step_ranking_record",
        "prg_codex_prompt_generation_record",
        "cde_execution_mode_selection_decision",
        "con_shift_left_workflow_coverage_audit_result",
        "con_shift_left_workflow_front_door_enforcement_result",
        "lin_required_lineage_producer_audit_result",
        "obs_required_observability_producer_audit_result",
        "rep_replayability_gap_explainer_result",
        "ril_pra_slh_bypass_red_team_report",
        "fre_tpa_sel_pqx_pra_slh_bypass_fix_pack",
        "final_pra_01_pr_anchor_proof",
    ]
    for name in names:
        payload = json.loads((out / f"{name}.json").read_text(encoding="utf-8"))
        validate_artifact(payload, name)
