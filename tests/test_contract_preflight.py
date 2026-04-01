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
