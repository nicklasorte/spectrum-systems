from __future__ import annotations

import json
from pathlib import Path

from scripts import run_contract_preflight as preflight


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


def test_main_report_includes_changed_path_fallback_metadata(tmp_path: Path, monkeypatch) -> None:
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


def test_main_passes_only_contract_schema_paths_into_impact_analyzer(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "out"
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
