from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration import cycle_runner
from spectrum_systems.modules.runtime.judgment_engine import retrieve_precedents, run_judgment, select_policy


_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle"


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture(name: str) -> dict:
    return _load(_FIXTURES / name)


def _manifest(tmp_path: Path, *, state: str = "roadmap_under_review") -> tuple[dict, Path]:
    roadmap_path = _REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"
    review_path = tmp_path / "roadmap_review.json"
    review_payload = _fixture("roadmap_review_approved.json")
    review_payload["schema_version"] = "1.1.0"
    review_payload["governance_provenance"] = {
        "strategy_authority": {
            "path": "docs/architecture/system_strategy.md",
            "version": "2026-03-30",
        },
        "source_authorities": [
            {
                "source_id": "SRE-MAPPING",
                "path": "docs/source_structured/mapping_google_sre_reliability_principles_to_spectrum_systems.json",
            }
        ],
        "invariant_checks": [
            {"invariant_id": "strategy_alignment", "status": "pass", "detail": "aligned"},
            {"invariant_id": "source_grounding", "status": "pass", "detail": "bounded refs"},
        ],
        "drift_findings": [],
    }
    _write(review_path, review_payload)

    pqx_request = {
        "step_id": "AI-01",
        "roadmap_path": str(roadmap_path),
        "state_path": str(tmp_path / "pqx_state.json"),
        "runs_root": str(tmp_path / "pqx_runs"),
        "pqx_output_text": "deterministic pqx output",
    }
    pqx_request_path = tmp_path / "pqx_request.json"
    _write(pqx_request_path, pqx_request)
    eligibility_path = tmp_path / "roadmap_eligibility.json"
    _write(
        eligibility_path,
        {
            "artifact_type": "roadmap_eligibility_artifact",
            "schema_version": "1.0.0",
            "artifact_version": "1.0.0",
            "roadmap_ref": "docs/roadmaps/system_roadmap.md",
            "evaluated_at": "2026-03-30T00:00:00Z",
            "identity_basis": {
                "roadmap_artifact_id": "roadmap-cycle-test",
                "roadmap_digest": "a542be4e4e3d2a77e6a508d46267f37754378291a075e59977fe80c0baab1128",
            },
            "eligible_step_ids": ["AI-01"],
            "recommended_next_step_ids": ["AI-01"],
            "blocked_steps": [],
            "summary": {
                "total_steps": 1,
                "completed_steps": 0,
                "eligible_steps": 1,
                "blocked_steps": 0,
            },
            "artifact_id": "c1bfd40c7ea68193b177e33a01da488ff42d8d59cd6ab745ee019ec83afe83a1",
        },
    )

    base = {
        "cycle_id": "cycle-test",
        "current_state": state,
        "roadmap_artifact_path": str(roadmap_path),
        "strategy_authority": {
            "path": "docs/architecture/system_strategy.md",
            "version": "2026-03-30",
        },
        "source_authorities": [
            {
                "source_id": "SRE-MAPPING",
                "path": "docs/source_structured/mapping_google_sre_reliability_principles_to_spectrum_systems.json",
                "title": "Mapping Google SRE Reliability Principles to Spectrum Systems",
            }
        ],
        "roadmap_review_artifact_paths": [str(review_path)],
        "execution_report_paths": [],
        "implementation_review_paths": [],
        "fix_roadmap_path": None,
        "fix_roadmap_markdown_path": None,
        "fix_group_refs": [],
        "fix_execution_report_paths": [],
        "certification_record_path": None,
        "blocking_issues": [],
        "next_action": "await_roadmap_approval",
        "roadmap_approval_state": "approved",
        "hard_gates": {
            "roadmap_approved": True,
            "execution_contracts_pinned": True,
            "review_templates_present": True,
        },
        "pqx_execution_request_path": str(pqx_request_path),
        "pqx_request_ref": None,
        "execution_started_at": None,
        "execution_completed_at": None,
        "certification_status": "pending",
        "certification_summary": None,
        "done_certification_input_refs": {
            "replay_result_ref": "a",
            "regression_result_ref": "b",
            "certification_pack_ref": "c",
            "error_budget_ref": "d",
            "policy_ref": "e",
        },
        "required_judgments": [],
        "required_judgment_eval_types": ["evidence_coverage", "policy_alignment", "replay_consistency"],
        "judgment_scope": "autonomous_cycle",
        "judgment_environment": "prod",
        "judgment_policy_paths": [str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy.json")],
        "judgment_policy_lifecycle_paths": [str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy_lifecycle_record.json")],
        "judgment_policy_rollout_paths": [str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy_rollout_record.json")],
        "judgment_input_context": {
            "quality_score": 0.95,
            "evidence_complete": True,
            "risk_level": "low",
            "scope_tag": "autonomous_cycle",
        },
        "judgment_evidence_refs": [str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json")],
        "judgment_precedent_record_paths": [str(_REPO_ROOT / "contracts" / "examples" / "judgment_record.json")],
        "judgment_replay_reference_path": None,
        "judgment_record_path": None,
        "judgment_application_record_path": None,
        "judgment_eval_result_path": None,
        "next_step_decision_artifact_path": None,
        "roadmap_eligibility_artifact_path": str(eligibility_path),
        "eligible_step_ids_snapshot": ["AI-01"],
        "recommended_next_step_ids": ["AI-01"],
        "selected_step_id": "AI-01",
        "selected_step_status": "authorized",
        "decision_summary": "Preseeded eligibility decision summary.",
        "decision_blocked": False,
        "decision_block_reason": None,
        "eligibility_summary_snapshot": {
            "total_steps": 1,
            "completed_steps": 0,
            "eligible_steps": 1,
            "blocked_steps": 0,
        },
        "drift_remediation_artifact_path": None,
        "fix_plan_artifact_path": None,
        "updated_at": "2026-03-30T00:00:00Z",
    }
    path = tmp_path / "cycle_manifest.json"
    _write(path, base)
    return base, path


def _seed_implementation_reviews(manifest: dict, tmp_path: Path) -> None:
    claude_path = tmp_path / "implementation_review_claude.json"
    codex_path = tmp_path / "implementation_review_codex.json"
    _write(claude_path, _fixture("implementation_review_claude.json"))
    _write(codex_path, _fixture("implementation_review_codex.json"))
    manifest["implementation_review_paths"] = [str(claude_path), str(codex_path)]


def test_cycle_runner_happy_path_execution_ready_through_certified_done(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="execution_ready")

    execution_result = cycle_runner.run_cycle(manifest_path)
    assert execution_result["next_state"] == "execution_complete_unreviewed"

    updated = _load(manifest_path)
    assert updated["current_state"] == "execution_complete_unreviewed"
    assert updated["execution_report_paths"]

    report_payload = _load(Path(updated["execution_report_paths"][0]))
    produced = report_payload["produced_artifacts"]
    slice_record_path = next(path for path in produced if path.endswith(".pqx_slice_execution_record.json"))
    slice_record = _load(Path(slice_record_path))
    emitted = slice_record["artifacts_emitted"]

    runs_root = Path(updated["pqx_execution_request_path"]).parent / "pqx_runs"

    def _resolve(name: str) -> str:
        rel = next(path for path in emitted if path.endswith(name))
        return str(runs_root / rel)

    refs = {
        "replay_result_ref": _resolve(".replay_result.json"),
        "regression_result_ref": _resolve(".regression_run_result.json"),
        "certification_pack_ref": _resolve(".control_loop_certification_pack.json"),
        "error_budget_ref": _resolve(".error_budget_status.json"),
        "policy_ref": _resolve(".control_decision.json"),
    }

    updated["current_state"] = "certification_pending"
    updated["done_certification_input_refs"] = refs
    _write(manifest_path, updated)

    certification_result = cycle_runner.run_cycle(manifest_path)
    assert certification_result["next_state"] == "certified_done"

    final_manifest = _load(manifest_path)
    assert final_manifest["current_state"] == "certified_done"
    assert Path(final_manifest["certification_record_path"]).is_file()
    assert final_manifest["certification_status"] == "passed"


def test_cycle_runner_review_to_fix_reentry_happy_path(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="implementation_reviews_complete")
    _seed_implementation_reviews(manifest, tmp_path)
    _write(manifest_path, manifest)

    fix_roadmap_result = cycle_runner.run_cycle(manifest_path)
    assert fix_roadmap_result["next_state"] == "fix_roadmap_ready"

    after_fix_roadmap = _load(manifest_path)
    assert after_fix_roadmap["current_state"] == "fix_roadmap_ready"
    assert Path(after_fix_roadmap["fix_roadmap_path"]).is_file()
    assert Path(after_fix_roadmap["fix_roadmap_markdown_path"]).is_file()
    assert after_fix_roadmap["fix_group_refs"]

    reentry_result = cycle_runner.run_cycle(manifest_path)
    assert reentry_result["next_state"] == "fixes_in_progress"

    after_reentry = _load(manifest_path)
    assert after_reentry["current_state"] == "fixes_in_progress"
    assert len(after_reentry["fix_execution_report_paths"]) == len(after_reentry["fix_group_refs"])

    in_progress_result = cycle_runner.run_cycle(manifest_path)
    assert in_progress_result["next_state"] == "fixes_complete_unreviewed"

    complete_result = cycle_runner.run_cycle(manifest_path)
    assert complete_result["next_state"] == "certification_pending"

    final_manifest = _load(manifest_path)
    final_manifest["certification_record_path"] = str(_REPO_ROOT / "contracts" / "examples" / "done_certification_record.json")
    _write(manifest_path, final_manifest)

    cert_result = cycle_runner.run_cycle(manifest_path)
    assert cert_result["next_state"] == "certified_done"


def test_cycle_runner_blocks_when_pqx_output_artifact_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, manifest_path = _manifest(tmp_path, state="execution_ready")

    def _bad_handoff(**_: object) -> dict:
        return {
            "report_path": str(tmp_path / "missing_execution_report.json"),
            "report_payload": {
                "started_at": "2026-03-30T00:00:00Z",
                "completed_at": "2026-03-30T00:01:00Z",
            },
            "pqx_result": {"status": "complete", "result": str(tmp_path / "missing.result.json")},
            "pqx_result_payload": {},
        }

    monkeypatch.setattr(cycle_runner, "handoff_to_pqx", _bad_handoff)
    result = cycle_runner.run_cycle(manifest_path)

    assert result["status"] == "blocked"
    assert "pqx handoff failed" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_pqx_request_step_not_authorized(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="execution_ready")
    request = _load(Path(manifest["pqx_execution_request_path"]))
    request["step_id"] = "CTRL-99"
    _write(Path(manifest["pqx_execution_request_path"]), request)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "step_id must match manifest selected_step_id" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_required_review_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="execution_complete_unreviewed")
    codex_path = tmp_path / "implementation_review_codex.json"
    _write(codex_path, _fixture("implementation_review_codex.json"))
    manifest["implementation_review_paths"] = [str(codex_path)]
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "dual implementation reviews required" in " ".join(result["blocking_issues"])


def test_cycle_runner_persists_remediation_and_fix_plan_when_decision_blocks(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="certification_pending")
    manifest["done_certification_input_refs"] = {}
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"

    updated = _load(manifest_path)
    assert updated["drift_remediation_artifact_path"] is not None
    assert updated["fix_plan_artifact_path"] is not None
    assert Path(updated["drift_remediation_artifact_path"]).is_file()
    assert Path(updated["fix_plan_artifact_path"]).is_file()

    decision_payload = _load(Path(updated["next_step_decision_artifact_path"]))
    assert decision_payload["remediation_required"] is True
    assert decision_payload["drift_remediation_artifact_path"] == updated["drift_remediation_artifact_path"]
    assert decision_payload["fix_plan_artifact_path"] == updated["fix_plan_artifact_path"]


def test_cycle_runner_blocks_when_eligibility_artifact_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_under_review")
    manifest["roadmap_eligibility_artifact_path"] = str(tmp_path / "missing_eligibility.json")
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "roadmap_eligibility_artifact_path" in " ".join(result["blocking_issues"])


def test_cycle_runner_persists_selected_step_linkage(tmp_path: Path) -> None:
    _, manifest_path = _manifest(tmp_path, state="roadmap_under_review")

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "ok"

    updated = _load(manifest_path)
    assert updated["selected_step_id"] == "AI-01"
    assert updated["selected_step_status"] == "authorized"
    assert updated["roadmap_eligibility_artifact_path"]
    assert updated["eligible_step_ids_snapshot"] == ["AI-01"]
    assert updated["recommended_next_step_ids"] == ["AI-01"]
    assert isinstance(updated["decision_summary"], str) and updated["decision_summary"]
    assert updated["decision_blocked"] is False


def test_cycle_runner_blocks_on_invalid_review_artifact(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="execution_complete_unreviewed")
    bad_review = tmp_path / "bad_review.json"
    _write(bad_review, {"artifact_type": "implementation_review_artifact"})
    manifest["implementation_review_paths"] = [str(bad_review)]
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "implementation_review_artifact failed schema validation" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_fix_roadmap_generation_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="implementation_reviews_complete")
    _seed_implementation_reviews(manifest, tmp_path)
    _write(manifest_path, manifest)

    def _fail_generate(**_: object) -> dict:
        raise ValueError("generator exploded")

    monkeypatch.setattr(cycle_runner, "generate_fix_roadmap", _fail_generate)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "fix roadmap generation failed" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_fix_execution_reports_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="fixes_in_progress")
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "missing required artifact: fix_execution_report_paths" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_on_invalid_execution_report(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="execution_in_progress")

    bad_report = tmp_path / "bad_execution_report.json"
    _write(bad_report, {"artifact_type": "execution_report_artifact"})
    manifest["execution_report_paths"] = [str(bad_report)]
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "failed schema validation" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_on_failed_or_missing_certification(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="certification_pending")
    manifest["done_certification_input_refs"] = {}
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert any(
        token in " ".join(result["blocking_issues"])
        for token in ("done certification handoff failed", "next-step decision blocked progression")
    )


def test_cycle_runner_judgment_happy_path_allows_progression(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "ok"
    assert result["next_state"] == "execution_ready"
    updated = _load(manifest_path)
    assert Path(updated["judgment_record_path"]).is_file()
    assert Path(updated["judgment_application_record_path"]).is_file()
    assert Path(updated["judgment_eval_result_path"]).is_file()
    eval_payload = _load(Path(updated["judgment_eval_result_path"]))
    required = {item["eval_type"] for item in eval_payload["eval_results"] if item.get("passed") is True}
    assert {"evidence_coverage", "policy_alignment", "replay_consistency"}.issubset(required)


def test_cycle_runner_blocks_when_required_eval_missing_from_result(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    _write(manifest_path, manifest)
    cycle_runner.run_cycle(manifest_path)

    updated = _load(manifest_path)
    eval_path = Path(updated["judgment_eval_result_path"])
    eval_payload = _load(eval_path)
    eval_payload["eval_results"] = [entry for entry in eval_payload["eval_results"] if entry["eval_type"] != "evidence_coverage"]
    _write(eval_path, eval_payload)
    updated["current_state"] = "roadmap_approved"
    _write(manifest_path, updated)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "missing required judgment eval: evidence_coverage" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_evidence_coverage_fails(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    _write(manifest_path, manifest)
    cycle_runner.run_cycle(manifest_path)

    updated = _load(manifest_path)
    eval_path = Path(updated["judgment_eval_result_path"])
    eval_payload = _load(eval_path)
    for entry in eval_payload["eval_results"]:
        if entry["eval_type"] == "evidence_coverage":
            entry["passed"] = False
            entry["score"] = 0.0
            break
    _write(eval_path, eval_payload)
    updated["current_state"] = "roadmap_approved"
    _write(manifest_path, updated)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "failing required judgment eval: evidence_coverage" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_policy_alignment_fails_without_deviation(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    _write(manifest_path, manifest)
    cycle_runner.run_cycle(manifest_path)

    updated = _load(manifest_path)
    eval_path = Path(updated["judgment_eval_result_path"])
    eval_payload = _load(eval_path)
    for entry in eval_payload["eval_results"]:
        if entry["eval_type"] == "policy_alignment":
            entry["passed"] = False
            entry["score"] = 0.0
            break
    _write(eval_path, eval_payload)
    updated["current_state"] = "roadmap_approved"
    _write(manifest_path, updated)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "failing required judgment eval: policy_alignment" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_replay_consistency_fails(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    _write(manifest_path, manifest)
    cycle_runner.run_cycle(manifest_path)

    updated = _load(manifest_path)
    eval_path = Path(updated["judgment_eval_result_path"])
    eval_payload = _load(eval_path)
    for entry in eval_payload["eval_results"]:
        if entry["eval_type"] == "replay_consistency":
            entry["passed"] = False
            entry["score"] = 0.0
            break
    _write(eval_path, eval_payload)
    updated["current_state"] = "roadmap_approved"
    _write(manifest_path, updated)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "failing required judgment eval: replay_consistency" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_required_judgment_inputs_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    manifest["judgment_input_context"] = {"quality_score": 0.95}
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "required judgment failed" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_required_lifecycle_artifacts_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    manifest["judgment_policy_lifecycle_paths"] = []
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "missing required judgment lifecycle artifacts" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_canary_selection_without_rollout_artifact(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    canary_policy = _load(_REPO_ROOT / "contracts" / "examples" / "judgment_policy.json")
    canary_policy["artifact_version"] = "1.1.0"
    canary_policy["status"] = "canary"
    policy_path = tmp_path / "canary_policy.json"
    _write(policy_path, canary_policy)
    lifecycle = _load(_REPO_ROOT / "contracts" / "examples" / "judgment_policy_lifecycle_record.json")
    lifecycle["to_version"] = "1.1.0"
    lifecycle["lifecycle_action"] = "enter_canary"
    lifecycle["resulting_status"] = "canary"
    lifecycle_path = tmp_path / "lifecycle.json"
    _write(lifecycle_path, lifecycle)
    manifest["judgment_policy_paths"] = [str(policy_path)]
    manifest["judgment_policy_lifecycle_paths"] = [str(lifecycle_path)]
    manifest["judgment_policy_rollout_paths"] = []
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "no applicable governed judgment policy found" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_required_judgment_artifacts_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    fake = tmp_path / "judgment_record.json"
    _write(fake, _load(_REPO_ROOT / "contracts" / "examples" / "judgment_record.json"))
    manifest["judgment_record_path"] = str(fake)
    manifest["judgment_application_record_path"] = None
    manifest["judgment_eval_result_path"] = None
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "missing required artifact: judgment artifacts" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_judgment_outcome_block(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]
    manifest["judgment_input_context"]["risk_level"] = "high"
    manifest["judgment_input_context"]["quality_score"] = 0.4
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "judgment outcome block prevents progression" in " ".join(result["blocking_issues"])


def test_precedent_retrieval_deterministic_order_and_scores() -> None:
    retrieval = {
        "required": True,
        "method_id": "exact-field-overlap",
        "method_version": "1.0.0",
        "query_fields": ["scope_tag", "risk_level"],
        "threshold": 0.5,
        "top_k": 3,
        "similarity_basis": "matching scope_tag and risk_level fields",
    }
    context = {"scope_tag": "autonomous_cycle", "risk_level": "low"}
    paths = [
        str(_REPO_ROOT / "contracts" / "examples" / "judgment_record.json"),
        str(_REPO_ROOT / "contracts" / "examples" / "judgment_record.json"),
    ]
    first = retrieve_precedents(precedent_paths=paths, retrieval=retrieval, query_context=context)
    second = retrieve_precedents(precedent_paths=paths, retrieval=retrieval, query_context=context)
    assert first == second


def test_policy_selection_and_application_deterministic() -> None:
    policy_paths = [str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy.json")]
    selected_a, matched_a = select_policy(
        policy_paths=policy_paths,
        judgment_type="artifact_release_readiness",
        scope="autonomous_cycle",
        environment="prod",
    )
    selected_b, matched_b = select_policy(
        policy_paths=policy_paths,
        judgment_type="artifact_release_readiness",
        scope="autonomous_cycle",
        environment="prod",
    )
    assert selected_a["artifact_id"] == selected_b["artifact_id"]
    assert matched_a == matched_b

    args = dict(
        cycle_id="cycle-deterministic",
        judgment_type="artifact_release_readiness",
        scope="autonomous_cycle",
        environment="prod",
        policy_paths=policy_paths,
        context={"quality_score": 0.95, "evidence_complete": True, "risk_level": "low", "scope_tag": "autonomous_cycle"},
        evidence_refs=[str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json")],
        precedent_paths=[str(_REPO_ROOT / "contracts" / "examples" / "judgment_record.json")],
        created_at="2026-03-30T00:00:00Z",
        trace_id="trace-0001",
        lifecycle_records=[
            {
                "policy_id": "judgment-policy-artifact-release-readiness-v1",
                "to_version": "1.0.0",
                "lifecycle_action": "promote_active",
                "resulting_status": "active",
            }
        ],
        rollout_records=[],
        governed_runtime=True,
    )
    out_a = run_judgment(**args)
    out_b = run_judgment(**args)
    assert out_a == out_b
    eval_a = next(item for item in out_a["judgment_eval_result"]["eval_results"] if item["eval_type"] == "evidence_coverage")
    eval_b = next(item for item in out_b["judgment_eval_result"]["eval_results"] if item["eval_type"] == "evidence_coverage")
    assert eval_a["score"] == eval_b["score"]


def test_judgment_application_records_conflicts_and_deviations(tmp_path: Path) -> None:
    policy = _load(_REPO_ROOT / "contracts" / "examples" / "judgment_policy.json")
    policy["precedent_retrieval"]["required"] = False
    policy["precedent_retrieval"]["threshold"] = 1.0
    policy["decision_rules"].insert(
        1,
        {
            "rule_id": "also-approve",
            "outcome": "approve",
            "priority": 1,
            "all_conditions": [],
            "rationale_template": "secondary always-on approval path",
        },
    )
    policy["decision_rules"].insert(
        2,
        {
            "rule_id": "conflicting-block",
            "outcome": "block",
            "priority": 1,
            "all_conditions": [],
            "rationale_template": "conflict generation rule",
        },
    )
    policy_path = tmp_path / "policy.json"
    _write(policy_path, policy)
    out = run_judgment(
        cycle_id="cycle-conflict",
        judgment_type="artifact_release_readiness",
        scope="autonomous_cycle",
        environment="prod",
        policy_paths=[str(policy_path)],
        context={"quality_score": 0.95, "evidence_complete": True, "risk_level": "low", "scope_tag": "autonomous_cycle"},
        evidence_refs=[str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json")],
        precedent_paths=[],
        created_at="2026-03-30T00:00:00Z",
    )
    app = out["judgment_application_record"]
    assert app["conflicts"]
    assert app["deviations"]


def test_cycle_runner_deterministic_replay_for_same_review_driven_inputs(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    for run_dir in (first_dir, second_dir):
        manifest, manifest_path = _manifest(run_dir, state="implementation_reviews_complete")
        _seed_implementation_reviews(manifest, run_dir)
        _write(manifest_path, manifest)

    first_fix_roadmap = cycle_runner.run_cycle(first_dir / "cycle_manifest.json")
    second_fix_roadmap = cycle_runner.run_cycle(second_dir / "cycle_manifest.json")

    assert (first_fix_roadmap["status"], first_fix_roadmap["next_state"], first_fix_roadmap["next_action"]) == (
        second_fix_roadmap["status"],
        second_fix_roadmap["next_state"],
        second_fix_roadmap["next_action"],
    )

    first_reentry = cycle_runner.run_cycle(first_dir / "cycle_manifest.json")
    second_reentry = cycle_runner.run_cycle(second_dir / "cycle_manifest.json")
    assert (first_reentry["status"], first_reentry["next_state"], first_reentry["next_action"]) == (
        second_reentry["status"],
        second_reentry["next_state"],
        second_reentry["next_action"],
    )


def test_cycle_runner_blocks_when_replay_reference_required_but_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_approved")
    manifest["required_judgments"] = ["artifact_release_readiness"]

    policy = _load(_REPO_ROOT / "contracts" / "examples" / "judgment_policy.json")
    policy["judgment_eval_requirements"]["replay_consistency"]["require_reference_artifact"] = True
    policy_path = tmp_path / "judgment_policy_require_ref.json"
    _write(policy_path, policy)
    manifest["judgment_policy_paths"] = [str(policy_path)]
    manifest["judgment_replay_reference_path"] = None
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "failing required judgment eval: replay_consistency" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_strategy_authority_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_under_review")
    manifest.pop("strategy_authority", None)
    _write(manifest_path, manifest)

    with pytest.raises(Exception, match="strategy_authority"):
        cycle_runner.run_cycle(manifest_path)


def test_cycle_runner_blocks_when_source_authorities_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_under_review")
    manifest["source_authorities"] = []
    _write(manifest_path, manifest)

    with pytest.raises(Exception, match="non-empty"):
        cycle_runner.run_cycle(manifest_path)


def test_cycle_runner_blocks_when_strategy_authority_path_invalid(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_under_review")
    manifest["strategy_authority"]["path"] = "docs/architecture/not_strategy.md"
    _write(manifest_path, manifest)

    with pytest.raises(Exception, match="was expected"):
        cycle_runner.run_cycle(manifest_path)


def test_cycle_runner_blocks_when_source_authority_path_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_under_review")
    manifest["source_authorities"][0]["path"] = str(tmp_path / "missing_source.md")
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "missing required artifact: source_authority.path" in " ".join(result["blocking_issues"])


def test_cycle_runner_blocks_when_roadmap_review_provenance_missing(tmp_path: Path) -> None:
    manifest, manifest_path = _manifest(tmp_path, state="roadmap_under_review")
    review_path = Path(manifest["roadmap_review_artifact_paths"][0])
    review_payload = _load(review_path)
    review_payload.pop("governance_provenance", None)
    _write(review_path, review_payload)
    _write(manifest_path, manifest)

    result = cycle_runner.run_cycle(manifest_path)
    assert result["status"] == "blocked"
    assert "governance_provenance" in " ".join(result["blocking_issues"])


def test_cycle_runner_deterministic_governance_blocking(tmp_path: Path) -> None:
    first_dir = tmp_path / "first-governance-block"
    second_dir = tmp_path / "second-governance-block"
    for run_dir in (first_dir, second_dir):
        manifest, manifest_path = _manifest(run_dir, state="roadmap_under_review")
        manifest["source_authorities"][0]["source_id"] = "NOT-IN-SOURCE-INDEX"
        _write(manifest_path, manifest)

    first = cycle_runner.run_cycle(first_dir / "cycle_manifest.json")
    second = cycle_runner.run_cycle(second_dir / "cycle_manifest.json")
    assert first == second
