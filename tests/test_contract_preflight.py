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


def test_main_skips_when_no_contract_or_example_changes(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    original_parse = preflight._parse_args
    original_detect = preflight.detect_changed_paths
    try:
        preflight._parse_args = lambda: type(
            "Args",
            (),
            {
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "changed_path": ["README.md"],
                "output_dir": str(output_dir),
            },
        )()
        preflight.detect_changed_paths = lambda *_args, **_kwargs: ["README.md"]
        code = preflight.main()
    finally:
        preflight._parse_args = original_parse
        preflight.detect_changed_paths = original_detect

    assert code == 0
    report = json.loads((output_dir / "contract_preflight_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "skipped"
