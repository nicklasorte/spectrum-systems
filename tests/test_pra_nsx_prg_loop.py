from __future__ import annotations

import json
from pathlib import Path
import subprocess

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.pra_nsx_prg_loop import (
    PRAnchorError,
    con_workflow_coverage_audit,
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
