from __future__ import annotations

import json
from pathlib import Path

from scripts import run_contract_preflight as preflight
from spectrum_systems.modules.runtime.pqx_execution_policy import (
    PQXExecutionPolicyError,
    classify_changed_paths as classify_pqx_policy_changed_paths,
    evaluate_pqx_execution_policy,
)


def _governed_wrapper_payload(changed_paths: list[str] | None = None) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "artifact_type": "codex_pqx_task_wrapper",
        "wrapper_id": "wrap-preflight-1",
        "task_identity": {
            "task_id": "task-preflight",
            "run_id": "run-preflight",
            "step_id": "AI-01",
            "step_name": "preflight task",
        },
        "task_source": {"source_type": "codex_prompt", "prompt": "preflight"},
        "execution_intent": {"execution_context": "pqx_governed", "mode": "governed"},
        "governance": {
            "classification": "governed_pqx_required",
            "pqx_required": True,
            "authority_state": "authoritative_governed_pqx",
            "authority_resolution": "explicit_pqx_context",
            "authority_evidence_ref": "data/pqx_runs/AI-01/example.pqx_slice_execution_record.json",
            "contract_preflight_result_artifact_path": "outputs/contract_preflight/contract_preflight_result_artifact.json",
        },
        "changed_paths": changed_paths or ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        "metadata": {
            "requested_at": "2026-04-02T00:00:00Z",
            "dependencies": [],
            "policy_version": "1.0.0",
            "authority_notes": None,
        },
        "pqx_execution_request": {
            "schema_version": "1.1.0",
            "run_id": "run-preflight",
            "step_id": "AI-01",
            "step_name": "preflight task",
            "dependencies": [],
            "requested_at": "2026-04-02T00:00:00Z",
            "prompt": "preflight",
            "roadmap_version": "docs/roadmaps/system_roadmap.md",
            "row_snapshot": {
                "row_index": 0,
                "step_id": "AI-01",
                "step_name": "preflight task",
                "dependencies": [],
                "status": "ready",
            },
        },
    }


def test_classify_changed_contracts_detects_governed_surfaces() -> None:
    classified = preflight.classify_changed_contracts(
        [
            "contracts/schemas/roadmap_eligibility_artifact.schema.json",
            "contracts/examples/roadmap_eligibility_artifact.json",
            "contracts/review-output.schema.json",
            "README.md",
        ]
    )

    assert classified["changed_contract_paths"] == ["contracts/schemas/roadmap_eligibility_artifact.schema.json"]
    assert classified["changed_example_paths"] == ["contracts/examples/roadmap_eligibility_artifact.json"]
    assert classified["changed_governed_definitions"] == ["contracts/review-output.schema.json"]


def test_build_impact_map_includes_required_roadmap_smoke_tests(monkeypatch) -> None:
    def _fake_analyze_contract_impact(**_: object) -> dict[str, object]:
        return {
            "impacted_test_paths": ["tests/test_roadmap_eligibility.py", "tests/helpers/replay_result_builder.py"],
            "impacted_runtime_paths": ["spectrum_systems/orchestration/roadmap_eligibility.py"],
            "impacted_script_paths": ["scripts/run_roadmap_eligibility.py"],
        }

    monkeypatch.setattr(preflight, "analyze_contract_impact", _fake_analyze_contract_impact)

    impact = preflight.build_impact_map(
        repo_root=Path("."),
        changed_contract_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        changed_example_paths=[],
    )

    assert "tests/test_roadmap_eligibility.py" in impact["required_smoke_tests"]
    assert "tests/test_next_step_decision.py" in impact["required_smoke_tests"]
    assert "tests/test_next_step_decision_policy.py" in impact["required_smoke_tests"]
    assert "tests/test_cycle_runner.py" in impact["required_smoke_tests"]


def test_schema_name_from_example_supports_example_suffix() -> None:
    assert preflight._schema_name_from_example("contracts/examples/contract_preflight_result_artifact.example.json") == (
        "contract_preflight_result_artifact"
    )


def test_schema_name_from_stage_contract_subdir_maps_to_stage_contract_schema() -> None:
    assert preflight._schema_name_from_example("contracts/examples/stage_contracts/pqx_stage_contract.json") == "stage_contract"
    assert preflight._schema_name_from_example("contracts/examples/stage_contracts/prompt_queue_stage_contract.json") == "stage_contract"


def test_validate_examples_accepts_stage_contract_subdir_examples() -> None:
    failures = preflight.validate_examples(
        [
            "contracts/examples/stage_contracts/pqx_stage_contract.json",
            "contracts/examples/stage_contracts/prompt_queue_stage_contract.json",
        ]
    )
    assert failures == []


def test_detect_changed_paths_uses_explicit_paths_first() -> None:
    detected = preflight.detect_changed_paths(
        repo_root=Path("."),
        base_ref="origin/main",
        head_ref="HEAD",
        explicit=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
    )

    assert detected.changed_paths == ["contracts/schemas/roadmap_eligibility_artifact.schema.json"]
    assert detected.changed_path_detection_mode == "explicit_paths"
    assert detected.fallback_used is False


def test_classify_evaluation_surfaces_marks_runtime_changes_as_evaluated() -> None:
    classified_contracts = preflight.classify_changed_contracts([])
    evaluation = preflight.classify_evaluation_surfaces(
        ["spectrum_systems/modules/runtime/evaluation_control.py"],
        classified_contracts,
    )

    assert evaluation["evaluation_mode"] == "full"
    assert evaluation["path_classifications"][0]["classification"] == "evaluated"
    assert evaluation["path_classifications"][0]["surface"] == "runtime_module"


def test_classify_evaluation_surfaces_marks_contract_tied_tests_as_evaluated() -> None:
    classified_contracts = preflight.classify_changed_contracts([])
    evaluation = preflight.classify_evaluation_surfaces(
        ["tests/test_contract_preflight.py"],
        classified_contracts,
    )

    assert evaluation["evaluation_mode"] == "full"
    assert evaluation["path_classifications"][0]["classification"] == "evaluated"
    assert evaluation["path_classifications"][0]["surface"] == "contract_tied_tests"


def test_pqx_policy_classifier_marks_governed_paths_deterministically() -> None:
    result = classify_pqx_policy_changed_paths(
        [
            "README.md",
            "contracts/schemas/roadmap_eligibility_artifact.schema.json",
            "scripts/pqx_runner.py",
        ]
    )
    assert result["classification"] == "governed_pqx_required"
    assert "contracts/schemas/roadmap_eligibility_artifact.schema.json" in result["governed_paths"]
    assert "scripts/pqx_runner.py" in result["governed_paths"]
    assert "README.md" in result["non_governed_paths"]


def test_pqx_policy_classifier_rejects_malformed_changed_paths_fail_closed() -> None:
    try:
        classify_pqx_policy_changed_paths(["../outside.txt"])
    except PQXExecutionPolicyError as exc:
        assert "must not traverse parent directories" in str(exc)
    else:
        raise AssertionError("expected malformed changed path to fail closed")


def test_pqx_policy_blocks_governed_changes_without_pqx_context() -> None:
    decision = evaluate_pqx_execution_policy(
        changed_paths=["spectrum_systems/modules/runtime/pqx_slice_runner.py"],
        execution_context="direct",
    )
    as_dict = decision.to_dict()
    assert as_dict["classification"] == "governed_pqx_required"
    assert as_dict["status"] == "block"
    assert as_dict["authority_state"] == "non_authoritative_direct_run"
    assert "GOVERNED_CHANGES_REQUIRE_PQX_CONTEXT" in as_dict["blocking_reasons"]


def test_pqx_policy_allows_exploration_only_changes_as_non_authoritative() -> None:
    decision = evaluate_pqx_execution_policy(
        changed_paths=["docs/governance/default_pqx_execution_policy.md"],
        execution_context="exploration",
    )
    as_dict = decision.to_dict()
    assert as_dict["classification"] == "exploration_only_or_non_governed"
    assert as_dict["status"] == "allow"
    assert as_dict["authority_state"] == "non_authoritative_direct_run"


def test_pqx_policy_allows_governed_changes_with_explicit_pqx_context() -> None:
    decision = evaluate_pqx_execution_policy(
        changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        execution_context="pqx_governed",
    )
    as_dict = decision.to_dict()
    assert as_dict["classification"] == "governed_pqx_required"
    assert as_dict["status"] == "allow"
    assert as_dict["authority_state"] == "authoritative_governed_pqx"


def test_pqx_policy_commit_range_without_context_is_pending_evidence() -> None:
    decision = evaluate_pqx_execution_policy(
        changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        execution_context=None,
        changed_path_detection_mode="base_head_diff",
    )
    as_dict = decision.to_dict()
    assert as_dict["status"] == "pending_evidence"
    assert as_dict["authority_state"] == "authority_unknown_pending_evidence"
    assert as_dict["blocking_reasons"] == ["PENDING_GOVERNED_PQX_AUTHORITY_EVIDENCE"]


def test_detect_changed_paths_uses_base_head_when_available(monkeypatch) -> None:
    monkeypatch.setattr(preflight, "_diff_name_only", lambda *_args, **_kwargs: (["contracts/schemas/a.schema.json"], None))

    detected = preflight.detect_changed_paths(repo_root=Path("."), base_ref="base", head_ref="head", explicit=[])

    assert detected.changed_paths == ["contracts/schemas/a.schema.json"]
    assert detected.changed_path_detection_mode == "base_head_diff"


def test_detect_changed_paths_handles_missing_head_ref_without_crash(monkeypatch) -> None:
    calls = []

    def _fake_diff(_repo: Path, base: str, head: str) -> tuple[list[str], str | None]:
        calls.append((base, head))
        if base == "origin/main":
            return [], "fatal: ambiguous argument 'origin/main..HEAD'"
        if base == "HEAD" and head == "HEAD":
            return [], None
        return [], "fatal: missing"

    monkeypatch.setattr(preflight, "_diff_name_only", _fake_diff)
    monkeypatch.setattr(preflight, "_github_sha_pair", lambda: None)
    monkeypatch.setattr(preflight, "_local_workspace_changes", lambda _repo: ["contracts/schemas/b.schema.json"])

    detected = preflight.detect_changed_paths(repo_root=Path("."), base_ref="origin/main", head_ref="HEAD", explicit=[])

    assert ("origin/main", "HEAD") in calls
    assert detected.changed_path_detection_mode == "local_workspace_status"
    assert detected.fallback_used is True


def test_detect_changed_paths_uses_current_head_fallback_when_explicit_head_is_missing(monkeypatch) -> None:
    calls = []

    def _fake_diff(_repo: Path, base: str, head: str) -> tuple[list[str], str | None]:
        calls.append((base, head))
        if head == "missing-head":
            return [], "fatal: bad object missing-head"
        if head == "HEAD":
            return ["contracts/schemas/roadmap_eligibility_artifact.schema.json"], None
        return [], "fatal: missing"

    monkeypatch.setattr(preflight, "_diff_name_only", _fake_diff)

    detected = preflight.detect_changed_paths(
        repo_root=Path("."),
        base_ref="base",
        head_ref="missing-head",
        explicit=[],
    )

    assert ("base", "missing-head") in calls
    assert ("base", "HEAD") in calls
    assert detected.changed_path_detection_mode == "base_to_current_head_fallback"
    assert detected.changed_paths == ["contracts/schemas/roadmap_eligibility_artifact.schema.json"]


def test_detect_changed_paths_degrades_to_full_governed_scan(monkeypatch) -> None:
    monkeypatch.setattr(preflight, "_diff_name_only", lambda *_args, **_kwargs: ([], "fatal: unavailable"))
    monkeypatch.setattr(preflight, "_github_sha_pair", lambda: None)
    monkeypatch.setattr(preflight, "_local_workspace_changes", lambda _repo: [])

    class _Result:
        returncode = 1
        combined_output = "fatal: bad revision"

    monkeypatch.setattr(preflight, "_run", lambda *_args, **_kwargs: _Result())
    monkeypatch.setattr(preflight, "_all_governed_paths", lambda _repo: ["contracts/schemas/roadmap_eligibility_artifact.schema.json"])

    detected = preflight.detect_changed_paths(repo_root=Path("."), base_ref="origin/main", head_ref="HEAD", explicit=[])

    assert detected.changed_path_detection_mode == "degraded_full_governed_scan"
    assert detected.changed_paths == ["contracts/schemas/roadmap_eligibility_artifact.schema.json"]
    assert detected.fallback_used is True
    assert any("degraded" in warning for warning in detected.warnings)


def test_detect_changed_paths_skips_non_governed_local_fallback(monkeypatch) -> None:
    monkeypatch.setattr(preflight, "_diff_name_only", lambda *_args, **_kwargs: ([], "fatal: unavailable"))
    monkeypatch.setattr(preflight, "_github_sha_pair", lambda: None)
    monkeypatch.setattr(preflight, "_local_workspace_changes", lambda _repo: ["README.md"])

    class _Result:
        returncode = 0
        stdout = ""
        combined_output = ""

    monkeypatch.setattr(preflight, "_run", lambda *_args, **_kwargs: _Result())
    monkeypatch.setattr(preflight, "_all_governed_paths", lambda _repo: ["contracts/schemas/roadmap_eligibility_artifact.schema.json"])

    detected = preflight.detect_changed_paths(repo_root=Path("."), base_ref="origin/main", head_ref="HEAD", explicit=[])
    assert detected.changed_path_detection_mode == "degraded_full_governed_scan"
    assert detected.changed_paths == ["contracts/schemas/roadmap_eligibility_artifact.schema.json"]


def test_detect_changed_paths_skips_non_governed_working_tree_fallback(monkeypatch) -> None:
    monkeypatch.setattr(preflight, "_diff_name_only", lambda *_args, **_kwargs: ([], "fatal: unavailable"))
    monkeypatch.setattr(preflight, "_github_sha_pair", lambda: None)
    monkeypatch.setattr(preflight, "_local_workspace_changes", lambda _repo: [])

    class _Result:
        returncode = 0
        stdout = "README.md\nscripts/run_contract_preflight.py\n"
        combined_output = ""

    monkeypatch.setattr(preflight, "_run", lambda *_args, **_kwargs: _Result())
    monkeypatch.setattr(preflight, "_all_governed_paths", lambda _repo: ["contracts/schemas/roadmap_eligibility_artifact.schema.json"])

    detected = preflight.detect_changed_paths(repo_root=Path("."), base_ref="origin/main", head_ref="HEAD", explicit=[])
    assert detected.changed_path_detection_mode == "degraded_full_governed_scan"
    assert detected.changed_paths == ["contracts/schemas/roadmap_eligibility_artifact.schema.json"]


def test_masking_detection_labels_contract_masking() -> None:
    masked = preflight.detect_masked_failures(
        [
            {
                "path": "tests/test_next_step_decision.py",
                "output": "jsonschema.ValidationError: required property 'eligible_step_ids'",
            }
        ]
    )

    assert masked == [
        {
            "path": "tests/test_next_step_decision.py",
            "classification": "contract masking introduced",
            "reason": "schema/contract failure signature detected before targeted test assertions",
        }
    ]


def test_resolve_test_targets_fixture_mapping_without_rg_dependency(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    (tests_dir / "fixtures").mkdir(parents=True)
    (tests_dir / "test_alpha.py").write_text(
        "def test_uses_fixture_name():\n    assert 'fixture_alpha' is not None\n",
        encoding="utf-8",
    )
    (tests_dir / "test_beta.py").write_text("def test_other():\n    assert True\n", encoding="utf-8")

    targets = preflight.resolve_test_targets(tmp_path, ["tests/fixtures/fixture_alpha.json"])
    assert targets == ["tests/test_alpha.py"]


def test_resolve_test_targets_does_not_invoke_rg(monkeypatch, tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    (tests_dir / "helpers").mkdir(parents=True)
    (tests_dir / "test_helper_usage.py").write_text(
        "def test_helper_ref():\n    name = 'my_helper'\n    assert name\n",
        encoding="utf-8",
    )

    called_commands: list[list[str]] = []
    original_run = preflight._run

    def _capture_run(command: list[str], cwd: Path):
        called_commands.append(command)
        return original_run(command, cwd)

    monkeypatch.setattr(preflight, "_run", _capture_run)
    targets = preflight.resolve_test_targets(tmp_path, ["tests/helpers/my_helper.py"])
    assert targets == ["tests/test_helper_usage.py"]
    assert not any(command and command[0] in {"rg", "ripgrep"} for command in called_commands)


def test_resolve_test_targets_ignores_unreadable_test_files(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    unreadable = tests_dir / "test_unreadable.py"
    unreadable.write_bytes(b"\xff\xfe\x00\x00")
    (tests_dir / "test_readable.py").write_text("def test_ok():\n    marker = 'fixture_zeta'\n    assert marker\n", encoding="utf-8")

    targets = preflight.resolve_test_targets(tmp_path, ["tests/fixtures/fixture_zeta.json"])
    assert targets == ["tests/test_readable.py"]


def test_resolve_required_surface_tests_uses_trust_spine_cohesion_override() -> None:
    targets = preflight.resolve_required_surface_tests(Path("."), ["scripts/run_trust_spine_evidence_cohesion.py"])
    assert "tests/test_trust_spine_evidence_cohesion.py" in targets["scripts/run_trust_spine_evidence_cohesion.py"]


def test_resolve_required_surface_tests_uses_ops03_override() -> None:
    targets = preflight.resolve_required_surface_tests(Path("."), ["scripts/run_ops03_adversarial_stress_testing.py"])
    assert "tests/test_run_ops03_adversarial_stress_testing.py" in targets[
        "scripts/run_ops03_adversarial_stress_testing.py"
    ]


def test_main_report_includes_changed_path_fallback_metadata(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    wrapper_path = tmp_path / "wrapper.json"
    wrapper_path.write_text(
        json.dumps(_governed_wrapper_payload(["contracts/schemas/roadmap_eligibility_artifact.schema.json"])),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": [],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": "data/pqx_runs/AI-01/example.pqx_slice_execution_record.json",
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
            changed_path_detection_mode="degraded_full_governed_scan",
            refs_attempted=["origin/main..HEAD"],
            fallback_used=True,
            warnings=["changed-path detection degraded; running full governed contract scan"],
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
    assert report["changed_path_detection"]["changed_path_detection_mode"] == "degraded_full_governed_scan"
    assert report["changed_path_detection"]["fallback_used"] is True
    preflight_artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert preflight_artifact["artifact_type"] == "contract_preflight_result_artifact"
    assert preflight_artifact["control_signal"]["strategy_gate_decision"] == "WARN"
    assert preflight_artifact["control_surface_gap_status"] == "not_run"
    assert preflight_artifact["control_surface_gap_blocking"] is False


def test_preflight_blocks_when_gap_bridge_reports_blocking(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": [],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=[],
            changed_path_detection_mode="explicit_paths",
            refs_attempted=[],
            fallback_used=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        preflight,
        "evaluate_control_surface_gap_bridge",
        lambda *_args, **_kwargs: {
            "status": "conversion_failed",
            "gap_result": None,
            "gap_result_path": None,
            "pqx_work_items": None,
            "pqx_work_items_path": None,
            "conversion_error": "failed conversion",
            "blocking": True,
        },
    )

    code = preflight.main()
    assert code == 2
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["preflight_status"] == "failed"
    assert artifact["control_surface_gap_status"] == "conversion_failed"
    assert artifact["control_surface_gap_blocking"] is True


def test_preflight_blocks_when_trust_spine_cohesion_reports_block(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["scripts/run_contract_preflight.py"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "evaluate_trust_spine_cohesion",
        lambda *_args, **_kwargs: {
            "artifact_type": "trust_spine_evidence_cohesion_result",
            "overall_decision": "BLOCK",
            "blocking_reasons": ["MISSING_REQUIRED_EVIDENCE:outputs/control_surface_manifest/control_surface_manifest.json"],
            "artifact_path": str(output_dir / "trust_spine_evidence_cohesion_result.json"),
        },
    )
    monkeypatch.setattr(
        preflight,
        "classify_evaluation_surfaces",
        lambda *_args, **_kwargs: {
            "required_paths": [],
            "evaluation_mode": "no-op",
            "evaluated_surfaces": [],
            "path_classifications": [],
        },
    )
    monkeypatch.setattr(
        preflight,
        "evaluate_control_surface_gap_bridge",
        lambda *_args, **_kwargs: {
            "status": "not_run",
            "gap_result": None,
            "gap_result_path": None,
            "pqx_work_items": None,
            "pqx_work_items_path": None,
            "conversion_error": None,
            "blocking": False,
        },
    )

    code = preflight.main()
    assert code == 2
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert "trust-spine evidence cohesion" in report["recommended_repair_areas"]


def test_evaluate_trust_spine_cohesion_skips_when_required_artifacts_are_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(preflight, "_CONTROL_SURFACE_MANIFEST_PATH", tmp_path / "missing_manifest.json")
    monkeypatch.setattr(preflight, "_CONTROL_SURFACE_ENFORCEMENT_PATH", tmp_path / "missing_enforcement.json")
    monkeypatch.setattr(preflight, "_CONTROL_SURFACE_OBEDIENCE_PATH", tmp_path / "missing_obedience.json")
    monkeypatch.setattr(preflight, "_TRUST_SPINE_INVARIANT_PATH", tmp_path / "missing_invariant.json")
    monkeypatch.setattr(preflight, "_DONE_CERTIFICATION_PATH", tmp_path / "missing_done.json")

    result = preflight.evaluate_trust_spine_cohesion(["scripts/run_trust_spine_evidence_cohesion.py"], tmp_path)
    assert result is None


def test_map_preflight_control_signal_freezes_in_hardening_on_unrepaired_downstream() -> None:
    report = {
        "status": "failed",
        "changed_path_detection": {
            "changed_path_detection_mode": "base_head_diff",
        },
        "schema_example_failures": [],
        "producer_failures": [],
        "fixture_failures": [{"path": "tests/helpers/foo.py"}],
        "consumer_failures": [],
        "masked_failures": [],
    }

    signal = preflight.map_preflight_control_signal(report=report, hardening_flow=True)
    assert signal["strategy_gate_decision"] == "FREEZE"


def test_map_preflight_control_signal_blocks_skipped_status() -> None:
    signal = preflight.map_preflight_control_signal(
        report={
            "status": "skipped",
            "changed_path_detection": {"changed_path_detection_mode": "base_head_diff"},
            "schema_example_failures": [],
            "producer_failures": [],
            "fixture_failures": [],
            "consumer_failures": [],
            "masked_failures": [],
        },
        hardening_flow=False,
    )
    assert signal["strategy_gate_decision"] == "BLOCK"


def test_main_irrelevant_changed_file_reports_explicit_no_op(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["README.md"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
            },
        )(),
    )

    code = preflight.main()
    assert code == 0
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["changed_path_detection"]["evaluation_mode"] == "no-op"
    assert report["skip_reason"] == "explicit no-op: changed paths have no applicable contract surface"
    assert report["pqx_execution_policy"]["authority_state"] == "non_authoritative_direct_run"
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["pqx_required_context_enforcement"]["status"] == "allow"
    assert artifact["pqx_required_context_enforcement"]["classification"] == "exploration_only_or_non_governed"


def test_main_blocks_governed_changes_without_pqx_context(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["spectrum_systems/modules/runtime/pqx_slice_runner.py"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "direct",
            },
        )(),
    )
    monkeypatch.setattr(preflight, "resolve_required_surface_tests", lambda *_args, **_kwargs: {"spectrum_systems/modules/runtime/pqx_slice_runner.py": ["tests/test_pqx_slice_runner.py"]})
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 2
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["pqx_execution_policy"]["status"] == "block"
    assert report["pqx_execution_policy"]["authority_state"] == "non_authoritative_direct_run"
    assert "GOVERNED_CHANGES_REQUIRE_PQX_CONTEXT" in report["invariant_violations"]
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["pqx_required_context_enforcement"]["status"] == "block"
    assert "GOVERNED_REQUIRES_PQX_GOVERNED_CONTEXT" in artifact["pqx_required_context_enforcement"]["blocking_reasons"]


def test_main_commit_range_without_context_warns_without_naive_direct_run_block(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": [],
                "output_dir": str(output_dir),
                "hardening_flow": False,
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
            changed_path_detection_mode="base_head_diff",
            refs_attempted=["origin/main..HEAD"],
            fallback_used=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        preflight,
        "resolve_governed_pqx_authority_evidence",
        lambda *_args, **_kwargs: {
            "resolution_status": "missing",
            "authority_state": "authority_unknown_pending_evidence",
            "blocking_reasons": ["MISSING_GOVERNED_PQX_AUTHORITY_EVIDENCE"],
            "evidence_ref": None,
            "evidence_kind": "pqx_slice_execution_record",
        },
    )
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 0
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["pqx_required_context_enforcement"]["status"] == "allow"
    assert report["pqx_required_context_enforcement"]["authority_state"] == "unknown_pending_execution"
    assert report["pqx_required_context_enforcement"]["requires_pqx_execution"] is True
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["control_signal"]["strategy_gate_decision"] == "ALLOW"
    assert artifact["pqx_required_context_enforcement"]["authority_state"] == "unknown_pending_execution"


def test_main_commit_range_without_context_allows_when_authority_evidence_resolves(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": [],
                "output_dir": str(output_dir),
                "hardening_flow": False,
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
            changed_path_detection_mode="base_head_diff",
            refs_attempted=["origin/main..HEAD"],
            fallback_used=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        preflight,
        "resolve_governed_pqx_authority_evidence",
        lambda *_args, **_kwargs: {
            "resolution_status": "resolved",
            "authority_state": "authoritative_governed_pqx",
            "blocking_reasons": [],
            "evidence_ref": "data/pqx_runs/AI-01/pqx-slice-20260402T000000Z.pqx_slice_execution_record.json",
            "evidence_kind": "pqx_slice_execution_record",
        },
    )
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 0
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["pqx_required_context_enforcement"]["status"] == "allow"
    assert report["pqx_required_context_enforcement"]["authority_state"] == "unknown_pending_execution"
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["pqx_required_context_enforcement"]["enforcement_decision"] == "allow"


def test_resolve_explicit_authority_evidence_ref_accepts_sequential_trace(tmp_path: Path) -> None:
    record_path = tmp_path / "run-1.pqx_slice_execution_record.json"
    record_path.write_text(
        json.dumps(
            {
                "artifact_type": "pqx_slice_execution_record",
                "status": "completed",
                "certification_status": "certified",
            }
        ),
        encoding="utf-8",
    )
    trace_path = tmp_path / "pqx_trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "artifact_type": "pqx_sequential_execution_trace",
                "authority_evidence_refs": [str(record_path)],
            }
        ),
        encoding="utf-8",
    )
    resolved = preflight._resolve_explicit_authority_evidence_ref(Path("."), str(trace_path))
    assert resolved["resolution_status"] == "resolved"
    assert resolved["evidence_kind"] == "pqx_slice_execution_record"


def test_main_governed_context_with_trace_authority_ref_allows(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    wrapper_path = tmp_path / "wrapper.json"
    wrapper_path.write_text(
        json.dumps(_governed_wrapper_payload(["contracts/schemas/roadmap_eligibility_artifact.schema.json"])),
        encoding="utf-8",
    )
    repo_tmp_dir = preflight.REPO_ROOT / "outputs" / "test-preflight-authority"
    repo_tmp_dir.mkdir(parents=True, exist_ok=True)
    record_path = repo_tmp_dir / "run-1.pqx_slice_execution_record.json"
    record_path.write_text(
        json.dumps(
            {
                "artifact_type": "pqx_slice_execution_record",
                "status": "completed",
                "certification_status": "certified",
            }
        ),
        encoding="utf-8",
    )
    trace_path = repo_tmp_dir / "pqx_trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "artifact_type": "pqx_sequential_execution_trace",
                "authority_evidence_refs": [str(record_path.relative_to(preflight.REPO_ROOT))],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": str(trace_path.relative_to(preflight.REPO_ROOT)),
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
            changed_path_detection_mode="explicit_paths",
            refs_attempted=[],
            fallback_used=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 0
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["pqx_required_context_enforcement"]["status"] == "allow"


def test_main_governed_context_with_invalid_authority_ref_blocks(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    wrapper_path = tmp_path / "wrapper.json"
    wrapper_path.write_text(
        json.dumps(_governed_wrapper_payload(["contracts/schemas/roadmap_eligibility_artifact.schema.json"])),
        encoding="utf-8",
    )
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps({"artifact_type": "unknown"}), encoding="utf-8")
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": str(bad_path),
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
            changed_path_detection_mode="explicit_paths",
            refs_attempted=[],
            fallback_used=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 2
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["pqx_required_context_enforcement"]["status"] == "block"


def test_main_commit_range_governed_with_valid_authority_allows(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    wrapper_path = tmp_path / "wrapper.json"
    wrapper_path.write_text(
        json.dumps(_governed_wrapper_payload(["contracts/schemas/roadmap_eligibility_artifact.schema.json"])),
        encoding="utf-8",
    )
    repo_tmp_dir = preflight.REPO_ROOT / "outputs" / "test-preflight-authority-commit-range"
    repo_tmp_dir.mkdir(parents=True, exist_ok=True)
    record_path = repo_tmp_dir / "run-2.pqx_slice_execution_record.json"
    record_path.write_text(
        json.dumps({"artifact_type": "pqx_slice_execution_record", "status": "completed", "certification_status": "certified"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": [],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": str(record_path.relative_to(preflight.REPO_ROOT)),
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
            changed_path_detection_mode="base_head_diff",
            refs_attempted=["origin/main..HEAD"],
            fallback_used=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 0
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["control_signal"]["strategy_gate_decision"] == "ALLOW"


def test_main_commit_range_with_explicit_direct_execution_blocks(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": [],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "direct",
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
            changed_path_detection_mode="base_head_diff",
            refs_attempted=["origin/main..HEAD"],
            fallback_used=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 2
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["pqx_required_context_enforcement"]["enforcement_decision"] == "block"
    assert artifact["pqx_required_context_enforcement"]["authority_state"] == "non_authoritative_direct_run"


def test_main_governed_context_with_valid_wrapper_allows(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    wrapper_path = tmp_path / "wrapper.json"
    wrapper_path.write_text(
        json.dumps(_governed_wrapper_payload(["contracts/schemas/roadmap_eligibility_artifact.schema.json"])),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": "data/pqx_runs/AI-01/example.pqx_slice_execution_record.json",
            },
        )(),
    )
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 0
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["pqx_required_context_enforcement"]["status"] == "allow"
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["schema_version"] == "1.2.0"
    assert artifact["pqx_required_context_enforcement"]["status"] == "allow"


def test_main_ci_style_base_head_with_wrapper_records_allow_state(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    wrapper_path = tmp_path / "wrapper.json"
    changed = ["contracts/schemas/roadmap_eligibility_artifact.schema.json"]
    wrapper_path.write_text(json.dumps(_governed_wrapper_payload(changed)), encoding="utf-8")
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": [],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": "data/pqx_runs/AI-01/example.pqx_slice_execution_record.json",
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=changed,
            changed_path_detection_mode="base_head_diff",
            refs_attempted=["origin/main..HEAD"],
            fallback_used=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 0
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["control_signal"]["strategy_gate_decision"] == "ALLOW"
    assert artifact["pqx_required_context_enforcement"]["status"] == "allow"


def test_main_explicit_changed_paths_without_context_blocks_as_non_pqx_direct(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
            },
        )(),
    )
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 2
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["pqx_execution_policy"]["status"] == "block"
    assert report["pqx_execution_policy"]["authority_resolution"] == "pqx_required_context_enforcement_block"
    assert "GOVERNED_CHANGES_REQUIRE_PQX_CONTEXT" in report["invariant_violations"]


def test_main_required_surface_without_eval_target_fails_closed(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["spectrum_systems/modules/runtime/policy_backtesting.py"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
            },
        )(),
    )
    monkeypatch.setattr(preflight, "resolve_required_surface_tests", lambda *_args, **_kwargs: {"spectrum_systems/modules/runtime/policy_backtesting.py": []})

    code = preflight.main()
    assert code == 2
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["missing_required_surface"] == [
        {
            "path": "spectrum_systems/modules/runtime/policy_backtesting.py",
            "reason": "required contract surface changed but no deterministic evaluation target was found",
        }
    ]


def test_required_surface_override_map_is_loaded_from_governance_file(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "docs" / "governance").mkdir(parents=True, exist_ok=True)
    (repo_root / "docs" / "governance" / "preflight_required_surface_test_overrides.json").write_text(
        json.dumps(
            {
                "spectrum_systems/modules/runtime/ai_adapter.py": [
                    "tests/test_task_registry_ai_adapter_eval_slice_runner.py"
                ]
            }
        ),
        encoding="utf-8",
    )
    merged = preflight._load_required_surface_override_map(repo_root)
    assert (
        merged["spectrum_systems/modules/runtime/ai_adapter.py"]
        == ["tests/test_task_registry_ai_adapter_eval_slice_runner.py"]
    )


def test_main_passes_only_contract_schema_paths_into_impact_analyzer(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    wrapper_path = tmp_path / "wrapper.json"
    wrapper_path.write_text(
        json.dumps(
            _governed_wrapper_payload(
                [
                    "contracts/schemas/roadmap_eligibility_artifact.schema.json",
                    "contracts/comment-resolution-matrix.schema.json",
                ]
            )
        ),
        encoding="utf-8",
    )
    captured: dict[str, list[str]] = {}

    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": [],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": "data/pqx_runs/AI-01/example.pqx_slice_execution_record.json",
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "detect_changed_paths",
        lambda *_args, **_kwargs: preflight.ChangedPathDetectionResult(
            changed_paths=[
                "contracts/schemas/roadmap_eligibility_artifact.schema.json",
                "contracts/comment-resolution-matrix.schema.json",
            ],
            changed_path_detection_mode="base_head_diff",
            refs_attempted=["origin/main..HEAD"],
            fallback_used=False,
            warnings=[],
        ),
    )

    def _fake_build_impact_map(_repo_root: Path, changed_contract_paths: list[str], _changed_example_paths: list[str]):
        captured["changed_contract_paths"] = list(changed_contract_paths)
        return {
            "producers": [],
            "fixtures_or_builders": [],
            "consumers": [],
            "required_smoke_tests": [],
            "contract_impact_artifact": {
                "artifact_type": "contract_impact_artifact",
                "schema_version": "1.0.0",
                "impact_id": "f11d5d12f47f7547d6119d91d4d5633c59dca95f3f899f1fdd0a4af11e0189ce",
                "generated_at": "2026-04-01T00:00:00Z",
                "analyzer_version": "1.0.0",
                "standards_manifest_path": "contracts/standards-manifest.json",
                "changed_contract_paths": ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
                "changed_example_paths": [],
                "impacted_consumer_paths": [],
                "impacted_test_paths": [],
                "impacted_runtime_paths": [],
                "impacted_script_paths": [],
                "compatibility_class": "compatible",
                "blocking": False,
                "blocking_reasons": [],
                "required_remediations": [],
                "safe_to_execute": True,
                "evidence_refs": ["contracts/standards-manifest.json"],
                "summary": "test",
            },
        }

    monkeypatch.setattr(preflight, "build_impact_map", _fake_build_impact_map)
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 0
    assert captured["changed_contract_paths"] == ["contracts/schemas/roadmap_eligibility_artifact.schema.json"]


def test_build_preflight_result_artifact_emits_impacted_seams() -> None:
    report = {
        "status": "passed",
        "changed_contracts": ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        "changed_path_detection": {
            "changed_path_detection_mode": "base_head_diff",
        },
        "impact": {
            "producers": [
                "spectrum_systems/orchestration/cycle_runner.py",
                "spectrum_systems/orchestration/next_step_decision.py",
            ],
            "fixtures_or_builders": ["tests/fixtures/autonomous_cycle/cycle_status_blocked_manifest.json"],
            "consumers": ["tests/test_roadmap_eligibility.py"],
        },
        "masked_failures": [],
        "recommended_repair_areas": [],
        "schema_example_failures": [],
        "producer_failures": [],
        "fixture_failures": [],
        "consumer_failures": [],
    }

    artifact = preflight.build_preflight_result_artifact(
        report=report,
        json_report_path=Path("outputs/contract_preflight/contract_preflight_report.json"),
        markdown_report_path=Path("outputs/contract_preflight/contract_preflight_report.md"),
        hardening_flow=False,
    )

    assert artifact["impacted_producers"] == report["impact"]["producers"]
    assert artifact["impacted_fixtures"] == report["impact"]["fixtures_or_builders"]
    assert artifact["impacted_consumers"] == report["impact"]["consumers"]
    assert artifact["control_signal"]["strategy_gate_decision"] == "ALLOW"


def test_contract_preflight_example_references_existing_impacted_paths() -> None:
    example = json.loads(Path("contracts/examples/contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    for rel_path in (
        example["impacted_producers"]
        + example["impacted_fixtures"]
        + example["impacted_consumers"]
    ):
        assert Path(rel_path).exists(), f"preflight seam path missing: {rel_path}"


def test_main_contract_preflight_blocks_when_control_surface_enforcement_blocks(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["spectrum_systems/modules/runtime/control_surface_manifest.py"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
            },
        )(),
    )
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        preflight,
        "evaluate_control_surface_enforcement",
        lambda _paths: {
            "artifact_type": "control_surface_enforcement_result",
            "enforcement_status": "BLOCK",
            "blocking_reasons": ["REQUIRED_SURFACES_TEST_COVERAGE_MISSING"],
        },
    )

    code = preflight.main()
    assert code == 2
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["control_surface_enforcement"]["enforcement_status"] == "BLOCK"
    assert "REQUIRED_SURFACES_TEST_COVERAGE_MISSING" in report["invariant_violations"]


def test_control_surface_enforcement_not_invoked_for_enforcement_only_paths() -> None:
    assert preflight.evaluate_control_surface_enforcement(
        ["spectrum_systems/modules/runtime/control_surface_enforcement.py"]
    ) is None


def test_control_surface_enforcement_builds_manifest_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)

    def _fake_build_manifest() -> dict[str, object]:
        return {
            "artifact_type": "control_surface_manifest",
            "schema_version": "1.0.0",
            "generated_at": "2026-04-05T00:00:00Z",
            "required_surfaces": [],
            "required_tests": [],
        }

    def _fake_run_control_surface_enforcement(*, manifest_path: Path, manifest_ref: str) -> dict[str, object]:
        assert manifest_path.is_file()
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert payload["artifact_type"] == "control_surface_manifest"
        assert manifest_ref == "outputs/control_surface_manifest/control_surface_manifest.json"
        return {
            "artifact_type": "control_surface_enforcement_result",
            "enforcement_status": "ALLOW",
            "blocking_reasons": [],
            "manifest_ref": manifest_ref,
        }

    monkeypatch.setattr(preflight, "build_control_surface_manifest", _fake_build_manifest)
    monkeypatch.setattr(preflight, "run_control_surface_enforcement", _fake_run_control_surface_enforcement)

    result = preflight.evaluate_control_surface_enforcement(["scripts/build_control_surface_manifest.py"])

    assert result is not None
    assert result["enforcement_status"] == "ALLOW"


def test_control_surface_enforcement_fails_closed_when_manifest_build_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)

    def _raise_build_error() -> dict[str, object]:
        raise preflight.ControlSurfaceManifestError("manifest generation failed")

    monkeypatch.setattr(preflight, "build_control_surface_manifest", _raise_build_error)

    result = preflight.evaluate_control_surface_enforcement(["scripts/build_control_surface_manifest.py"])

    assert result is not None
    assert result["enforcement_status"] == "BLOCK"
    assert result["blocking_reasons"] == ["CONTROL_SURFACE_ENFORCEMENT_INPUT_INVALID"]
    assert "manifest generation failed" in result["error"]


def test_resolve_required_surface_tests_maps_con035_governance_paths() -> None:
    targets = preflight.resolve_required_surface_tests(
        Path("."),
        [
            "scripts/pqx_runner.py",
            "spectrum_systems/modules/runtime/control_surface_gap_loader.py",
        ],
    )
    for path in (
        "scripts/pqx_runner.py",
        "spectrum_systems/modules/runtime/control_surface_gap_loader.py",
    ):
        assert "tests/test_control_surface_gap_to_pqx.py" in targets[path]
        assert "tests/test_pqx_slice_runner.py" in targets[path]


def test_validate_control_surface_gap_packet_test_expectations_fail_closed() -> None:
    failures = preflight.validate_control_surface_gap_packet_test_expectations(
        changed_paths=["scripts/pqx_runner.py"],
        resolved_targets_by_path={"scripts/pqx_runner.py": ["tests/test_pqx_slice_runner.py"]},
    )
    assert failures == [
        {
            "path": "scripts/pqx_runner.py",
            "reason": (
                "control_surface_gap_packet governance path requires deterministic tests: "
                "tests/test_control_surface_gap_to_pqx.py"
            ),
        }
    ]


def test_main_contract_preflight_allows_con035_changed_paths_when_required_tests_present(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    wrapper_path = tmp_path / "wrapper.json"
    changed_paths = [
        "scripts/pqx_runner.py",
        "spectrum_systems/modules/runtime/control_surface_gap_loader.py",
        "spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py",
        "spectrum_systems/modules/runtime/pqx_slice_runner.py",
    ]
    wrapper_path.write_text(json.dumps(_governed_wrapper_payload(changed_paths)), encoding="utf-8")
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": changed_paths,
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": "data/pqx_runs/AI-01/example.pqx_slice_execution_record.json",
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "evaluate_control_surface_gap_bridge",
        lambda _output_dir: {
            "status": "not_run",
            "gap_result": None,
            "gap_result_path": None,
            "pqx_work_items": None,
            "pqx_work_items_path": None,
            "conversion_error": None,
            "blocking": False,
        },
    )
    monkeypatch.setattr(preflight, "evaluate_trust_spine_cohesion", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "evaluate_control_surface_enforcement", lambda _paths: None)

    code = preflight.main()
    assert code == 0
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["preflight_status"] == "passed"
    assert artifact["control_signal"]["strategy_gate_decision"] == "ALLOW"


def test_resolve_wrapper_path_normalizes_repo_relative_path() -> None:
    resolved = preflight._resolve_wrapper_path(Path("/repo"), "outputs/contract_preflight/wrapper.json")
    assert resolved == Path("/repo/outputs/contract_preflight/wrapper.json")


def test_main_governed_preflight_auto_builds_missing_wrapper(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    wrapper_path = tmp_path / "missing-wrapper.json"
    changed = ["contracts/schemas/roadmap_eligibility_artifact.schema.json"]
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": changed,
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": str(wrapper_path),
                "authority_evidence_ref": "data/pqx_runs/AI-01/example.pqx_slice_execution_record.json",
            },
        )(),
    )

    def _fake_run(command: list[str], cwd: Path):
        if "build_preflight_pqx_wrapper.py" in " ".join(command):
            wrapper_path.write_text(json.dumps(_governed_wrapper_payload(changed)), encoding="utf-8")
            return preflight.CommandResult(command=command, returncode=0, stdout="ok", stderr="")
        return preflight.CommandResult(command=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(preflight, "_run", _fake_run)
    monkeypatch.setattr(preflight, "build_impact_map", lambda *_args, **_kwargs: {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": [], "contract_impact_artifact": {}})
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "resolve_test_targets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])

    code = preflight.main()
    assert code == 0
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["pqx_required_context_enforcement"]["status"] == "allow"
    assert report["changed_path_detection"]["pqx_wrapper_resolution"]["built"] is True


def test_main_contract_preflight_blocks_con035_when_required_test_mapping_missing(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    changed_paths = ["scripts/pqx_runner.py"]
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": changed_paths,
                "output_dir": str(output_dir),
                "hardening_flow": False,
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "resolve_required_surface_tests",
        lambda *_args, **_kwargs: {"scripts/pqx_runner.py": ["tests/test_pqx_slice_runner.py"]},
    )
    monkeypatch.setattr(
        preflight,
        "evaluate_control_surface_gap_bridge",
        lambda _output_dir: {
            "status": "not_run",
            "gap_result": None,
            "gap_result_path": None,
            "pqx_work_items": None,
            "pqx_work_items_path": None,
            "conversion_error": None,
            "blocking": False,
        },
    )
    monkeypatch.setattr(preflight, "evaluate_trust_spine_cohesion", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(preflight, "run_targeted_pytests", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "validate_examples", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(preflight, "evaluate_control_surface_enforcement", lambda _paths: None)

    code = preflight.main()
    assert code == 2
    artifact = json.loads((output_dir / "contract_preflight_result_artifact.json").read_text(encoding="utf-8"))
    assert artifact["preflight_status"] == "failed"
    assert artifact["control_signal"]["strategy_gate_decision"] == "BLOCK"
    diagnosis = json.loads((output_dir / "preflight_block_diagnosis_record.json").read_text(encoding="utf-8"))
    plan = json.loads((output_dir / "preflight_repair_plan_record.json").read_text(encoding="utf-8"))
    rerun = json.loads((output_dir / "preflight_repair_result_record.json").read_text(encoding="utf-8"))
    assert diagnosis["failure_class"] in {
        "missing_required_artifact",
        "contract_mismatch",
        "schema_violation",
        "lineage_missing",
        "authority_evidence_missing",
        "invalid_wrapper",
        "non_repairable_policy_violation",
        "internal_preflight_error",
        "unknown_preflight_failure",
    }
    assert "eligibility_decision" in plan
    assert "rerun_allowed" in rerun


def test_preflight_blocks_when_system_registry_guard_fails(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["docs/proposal.md"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": None,
                "authority_evidence_ref": None,
            },
        )(),
    )
    monkeypatch.setattr(
        preflight,
        "evaluate_system_registry_guard",
        lambda **_kwargs: {
            "artifact_type": "system_registry_guard_result",
            "status": "fail",
            "normalized_reason_codes": ["NEW_SYSTEM_MISSING_REGISTRATION"],
            "changed_files": ["docs/proposal.md"],
            "required_actions": ["Register the new system in the canonical registry."],
        },
    )
    monkeypatch.setattr(preflight, "evaluate_control_surface_gap_bridge", lambda _out: {"status": "not_run", "gap_result": None, "gap_result_path": None, "pqx_work_items": None, "pqx_work_items_path": None, "conversion_error": None, "blocking": False})
    monkeypatch.setattr(preflight, "evaluate_trust_spine_cohesion", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(preflight, "evaluate_pqx_execution_policy", lambda **_kwargs: type("Policy", (), {"to_dict": lambda self: {"status": "allow", "classification": "exploration_only_or_non_governed", "execution_context": "pqx_governed"}})())
    monkeypatch.setattr(preflight, "enforce_pqx_required_context", lambda **_kwargs: type("Enf", (), {"to_dict": lambda self: {"status": "allow", "classification": "exploration_only_or_non_governed", "execution_context": "pqx_governed", "wrapper_present": False, "wrapper_context_valid": True, "authority_context_valid": True, "authority_state": "non_authoritative_direct_run", "requires_pqx_execution": False, "enforcement_decision": "allow", "blocking_reasons": []}})())

    code = preflight.main()

    assert code == 2
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert "NEW_SYSTEM_MISSING_REGISTRATION" in report["invariant_violations"]
    assert (output_dir / "system_registry_guard_result.json").is_file()


def test_preflight_push_event_normalizes_empty_cli_refs_from_push_env(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_BASE_SHA", "")
    monkeypatch.setenv("GITHUB_HEAD_SHA", "")
    monkeypatch.setenv("GITHUB_BEFORE_SHA", "78f6cd4c28268e03eab3794497feb26378f620c2")
    monkeypatch.setenv("GITHUB_SHA", "cafecb6682f83c47134a7d01ae818643d1136811")

    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "",
                "head_ref": "",
                "event_name": "push",
                "changed_path": ["README.md"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": None,
                "authority_evidence_ref": None,
            },
        )(),
    )

    code = preflight.main()
    assert code == 0
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    ref_context = report["changed_path_detection"]["ref_context"]
    assert ref_context["normalization_strategy"] == "push_before_sha_fallback"
    assert ref_context["base_ref"] == "78f6cd4c28268e03eab3794497feb26378f620c2"
    assert ref_context["head_ref"] == "cafecb6682f83c47134a7d01ae818643d1136811"
    assert report["status"] == "passed"


def test_preflight_workflow_dispatch_without_refs_blocks_with_precise_reason(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "",
                "head_ref": "",
                "event_name": "workflow_dispatch",
                "changed_path": [],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": None,
                "authority_evidence_ref": None,
            },
        )(),
    )

    code = preflight.main()
    assert code == 2
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert "unsupported_event_context" in report["invariant_violations"]
    diagnosis = json.loads((output_dir / "preflight_block_diagnosis_record.json").read_text(encoding="utf-8"))
    assert diagnosis["reason_codes"] == ["unsupported_event_context"]


def test_preflight_cli_refs_override_env_push_fallback(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_BEFORE_SHA", "env-base")
    monkeypatch.setenv("GITHUB_SHA", "env-head")
    monkeypatch.setattr(
        preflight,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "explicit-base",
                "head_ref": "explicit-head",
                "event_name": "push",
                "changed_path": ["README.md"],
                "output_dir": str(output_dir),
                "hardening_flow": False,
                "execution_context": "pqx_governed",
                "pqx_wrapper_path": None,
                "authority_evidence_ref": None,
            },
        )(),
    )

    code = preflight.main()
    assert code == 0
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    ref_context = report["changed_path_detection"]["ref_context"]
    assert ref_context["normalization_strategy"] == "explicit_cli_pair"
    assert ref_context["base_ref"] == "explicit-base"
    assert ref_context["head_ref"] == "explicit-head"
