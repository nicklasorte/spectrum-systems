"""SMALL-BATCH-RISK-01 — tests for the small-batch risk record.

Tests the observation-only governed-PR-surface-breadth measurement
artifact:
- schema/example consistency
- surface class counting (schemas + examples + manifest, runtime +
  scripts + tests, generated artifacts, workflow surface, dashboard
  surface)
- risk_level threshold guidance (low / medium / high / very_high /
  unknown)
- recommended_batches emitted for high and very_high risk levels
- unknown classification produces unknown risk_level with reason_codes
- APR integration: AEX phase output_artifact_refs contains the
  small_batch_risk_record artifact ref
- artifact never enables automatic blocking (authority_scope is
  observation_only and the schema has no required field that flips
  PR-ready)
- vocabulary safety: schema/example/script/test do not contain
  reserved authority verbs

Authority scope: observation_only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact
from scripts import build_small_batch_risk_record as builder_mod
from scripts.build_small_batch_risk_record import (
    build_small_batch_risk_record,
    classify_surface,
)
from scripts.run_agent_pr_precheck import aex_required_surface_check

_EXAMPLE_PATH = (
    REPO_ROOT / "contracts" / "examples" / "small_batch_risk_record.example.json"
)
_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "schemas" / "small_batch_risk_record.schema.json"
)
_BUILDER_PATH = REPO_ROOT / "scripts" / "build_small_batch_risk_record.py"
_TEST_PATH = REPO_ROOT / "tests" / "test_small_batch_risk_record.py"

_FORBIDDEN_AUTHORITY_TOKENS = (
    "approve",
    "approval",
    "certify",
    "certification",
    "promote",
    "promotion",
    "enforce",
    "enforcement",
    "decide",
    "decision",
    "authorize",
    "authorization",
    "verdict",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build(changed_paths: list[str]) -> dict:
    return build_small_batch_risk_record(
        base_ref="origin/main",
        head_ref="HEAD",
        changed_paths=list(changed_paths),
        record_id="sbr-test-0000000000000000",
        created_at="2026-05-02T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Schema / example consistency
# ---------------------------------------------------------------------------


def test_example_validates_against_schema():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    validate_artifact(data, "small_batch_risk_record")


def test_example_authority_scope_is_observation_only():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert data["authority_scope"] == "observation_only"


def test_example_required_fields_present():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    required = {
        "artifact_type",
        "schema_version",
        "record_id",
        "created_at",
        "base_ref",
        "head_ref",
        "changed_file_count",
        "changed_paths",
        "governed_surface_classes",
        "governed_surface_count",
        "generated_artifact_touch_count",
        "schema_touch_count",
        "example_touch_count",
        "manifest_touch_count",
        "runtime_touch_count",
        "script_touch_count",
        "test_touch_count",
        "docs_touch_count",
        "workflow_touch_count",
        "dashboard_touch_count",
        "contract_surface_touched",
        "generated_surface_touched",
        "workflow_surface_touched",
        "dashboard_surface_touched",
        "risk_level",
        "reason_codes",
        "split_recommendation",
        "split_findings",
        "recommended_batches",
        "authority_scope",
    }
    assert required <= set(data.keys())


def test_schema_is_observation_only_const():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["authority_scope"]["const"] == "observation_only"


def test_schema_does_not_contain_reserved_authority_tokens():
    text = _SCHEMA_PATH.read_text(encoding="utf-8").lower()
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        assert token not in text, (
            f"reserved authority token {token!r} appears in small batch risk schema"
        )


def test_example_does_not_contain_reserved_authority_tokens():
    text = _EXAMPLE_PATH.read_text(encoding="utf-8").lower()
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        assert token not in text, (
            f"reserved authority token {token!r} appears in small batch risk example"
        )


def test_builder_does_not_contain_reserved_authority_tokens():
    text = _BUILDER_PATH.read_text(encoding="utf-8").lower()
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        assert token not in text, (
            f"reserved authority token {token!r} appears in small batch risk builder"
        )


def test_test_file_does_not_contain_reserved_authority_tokens_outside_lint_list():
    # Read the test file; the only acceptable occurrences are inside the
    # _FORBIDDEN_AUTHORITY_TOKENS literal list itself. We strip that list
    # and confirm no other occurrences remain.
    text = _TEST_PATH.read_text(encoding="utf-8")
    start = text.find("_FORBIDDEN_AUTHORITY_TOKENS")
    end = text.find(")", start) + 1
    sanitized = (text[:start] + text[end:]).lower()
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        assert token not in sanitized, (
            f"reserved authority token {token!r} appears in small batch risk test "
            "outside the lint constant"
        )


# ---------------------------------------------------------------------------
# Builder behavior — risk_level thresholds
# ---------------------------------------------------------------------------


def test_one_docs_file_yields_low_risk():
    record = _build(["docs/reviews/SMALL-BATCH-RISK-01_redteam.md"])
    validate_artifact(record, "small_batch_risk_record")
    assert record["risk_level"] == "low"
    assert record["split_recommendation"] == "keep_together"
    assert record["governed_surface_count"] == 1
    assert record["docs_touch_count"] == 1


def test_schemas_examples_manifest_yield_high_or_split_consideration():
    record = _build(
        [
            "contracts/schemas/some_record.schema.json",
            "contracts/examples/some_record.example.json",
            "contracts/standards-manifest.json",
        ]
    )
    validate_artifact(record, "small_batch_risk_record")
    assert record["risk_level"] in {"high", "very_high"}
    assert record["split_recommendation"] in {"consider_split", "split_recommended"}
    assert record["schema_touch_count"] == 1
    assert record["example_touch_count"] == 1
    assert record["manifest_touch_count"] == 1
    assert record["contract_surface_touched"] is True


def test_runtime_scripts_tests_yield_high_risk():
    record = _build(
        [
            "spectrum_systems/modules/runtime/example_module.py",
            "scripts/run_example.py",
            "tests/test_example.py",
        ]
    )
    validate_artifact(record, "small_batch_risk_record")
    assert record["risk_level"] in {"high", "very_high"}
    assert record["runtime_touch_count"] == 1
    assert record["script_touch_count"] == 1
    assert record["test_touch_count"] == 1


def test_generated_artifacts_touched_records_count():
    record = _build(
        [
            "artifacts/tls/system_dependency_priority_report.json",
            "governance/reports/ecosystem-health.json",
        ]
    )
    validate_artifact(record, "small_batch_risk_record")
    assert record["generated_artifact_touch_count"] >= 1
    assert record["generated_surface_touched"] is True


def test_workflow_touched_sets_flag():
    record = _build([".github/workflows/pr-pytest.yml"])
    validate_artifact(record, "small_batch_risk_record")
    assert record["workflow_touch_count"] == 1
    assert record["workflow_surface_touched"] is True


def test_dashboard_touched_sets_flag():
    record = _build(
        [
            "apps/dashboard-3ls/app/page.tsx",
            "artifacts/dashboard_metrics/eval_candidate_record.json",
        ]
    )
    validate_artifact(record, "small_batch_risk_record")
    assert record["dashboard_touch_count"] == 2
    assert record["dashboard_surface_touched"] is True
    # Dashboard paths must not double-count as generated artifacts.
    assert record["generated_artifact_touch_count"] == 0


def test_five_or_more_surface_classes_yields_very_high():
    record = _build(
        [
            "contracts/schemas/x.schema.json",
            "spectrum_systems/modules/runtime/y.py",
            "scripts/z.py",
            "tests/test_w.py",
            ".github/workflows/v.yml",
        ]
    )
    validate_artifact(record, "small_batch_risk_record")
    assert record["risk_level"] == "very_high"
    assert record["split_recommendation"] == "split_recommended"


def test_schema_runtime_generated_workflow_combination_is_very_high():
    # Even with only 4 surface classes, the schema + runtime + generated
    # + workflow combination is flagged as very_high.
    record = _build(
        [
            "contracts/schemas/x.schema.json",
            "spectrum_systems/modules/runtime/y.py",
            "artifacts/tls/system_dependency_priority_report.json",
            ".github/workflows/v.yml",
        ]
    )
    validate_artifact(record, "small_batch_risk_record")
    assert record["risk_level"] == "very_high"
    assert (
        "schema_runtime_generated_workflow_combination"
        in record["reason_codes"]
    )


def test_unknown_path_classification_yields_unknown_with_reason_codes(monkeypatch):
    # Force the canonical classifier to return a sentinel that is not in
    # the surface-class enum. The builder must classify this as unknown
    # and emit reason_codes.
    def force_unknown(_path: str) -> str:
        return "unrecognised_surface_class_sentinel"

    monkeypatch.setattr(builder_mod, "classify_surface", force_unknown)

    record = _build(["spectrum_systems/modules/runtime/some_runtime.py"])
    validate_artifact(record, "small_batch_risk_record")
    assert record["risk_level"] == "unknown"
    assert record["reason_codes"], "unknown risk_level requires reason_codes"
    assert "path_classification_failed" in record["reason_codes"]
    assert record["split_recommendation"] == "human_review_required"


def test_high_risk_emits_recommended_batches():
    record = _build(
        [
            "contracts/schemas/x.schema.json",
            "spectrum_systems/modules/runtime/y.py",
            "tests/test_z.py",
        ]
    )
    validate_artifact(record, "small_batch_risk_record")
    assert record["risk_level"] in {"high", "very_high"}
    assert record["split_findings"], "high/very_high require split_findings"
    assert record["recommended_batches"], (
        "high/very_high require recommended_batches"
    )
    for batch in record["recommended_batches"]:
        assert batch["observation_only"] is True
        assert batch["paths"]
        assert batch["batch_name"]


def test_very_high_risk_emits_recommended_batches():
    record = _build(
        [
            "contracts/schemas/x.schema.json",
            "contracts/examples/x.example.json",
            "spectrum_systems/modules/runtime/y.py",
            "scripts/z.py",
            "tests/test_w.py",
            ".github/workflows/v.yml",
        ]
    )
    validate_artifact(record, "small_batch_risk_record")
    assert record["risk_level"] == "very_high"
    assert record["split_findings"]
    assert record["recommended_batches"]


def test_low_risk_does_not_emit_split_findings():
    record = _build(["docs/reviews/SMALL-BATCH-RISK-01_redteam.md"])
    assert record["split_findings"] == []
    assert record["recommended_batches"] == []


def test_no_changed_paths_yields_low_with_reason_code():
    record = _build([])
    validate_artifact(record, "small_batch_risk_record")
    assert record["risk_level"] == "low"
    assert record["changed_file_count"] == 0
    assert record["governed_surface_count"] == 0


# ---------------------------------------------------------------------------
# Surface class classification — counting parity with surface flags
# ---------------------------------------------------------------------------


def test_classify_surface_dashboard_priority_over_generated():
    # Dashboard paths under artifacts/dashboard_* must not be classified
    # as generated artifacts.
    assert classify_surface("artifacts/dashboard_metrics/foo.json") == "dashboard"
    assert classify_surface("artifacts/dashboard_cases/foo.json") == "dashboard"
    assert (
        classify_surface("apps/dashboard-3ls/app/api/intelligence/route.ts")
        == "dashboard"
    )


def test_classify_surface_known_classes_only():
    paths = [
        "contracts/schemas/x.schema.json",
        "contracts/examples/x.example.json",
        "contracts/standards-manifest.json",
        "spectrum_systems/modules/runtime/x.py",
        "scripts/x.py",
        "tests/test_x.py",
        "docs/reviews/x.md",
        "docs/review-actions/x.md",
        "docs/governance/x.json",
        "artifacts/tls/x.json",
        ".github/workflows/x.yml",
        "apps/dashboard-3ls/app/page.tsx",
        "README.md",
    ]
    for p in paths:
        cls = classify_surface(p)
        assert cls in {
            "contracts_schemas",
            "contracts_examples",
            "standards_manifest",
            "runtime",
            "scripts",
            "tests",
            "docs_reviews",
            "docs_review_actions",
            "docs_governance",
            "generated_artifacts",
            "github_workflows",
            "dashboard",
            "other",
        }, f"unknown surface class for path {p}: {cls}"


def test_governed_surface_count_excludes_other_class():
    # README.md classifies as "other" and should not be counted toward
    # governed_surface_count.
    record = _build(["README.md"])
    validate_artifact(record, "small_batch_risk_record")
    assert record["governed_surface_count"] == 0
    assert "other" not in record["governed_surface_classes"]


# ---------------------------------------------------------------------------
# No automatic block behavior
# ---------------------------------------------------------------------------


def test_artifact_does_not_carry_block_or_gate_fields():
    record = _build(
        [
            "contracts/schemas/x.schema.json",
            "spectrum_systems/modules/runtime/y.py",
            "artifacts/tls/x.json",
            ".github/workflows/v.yml",
        ]
    )
    validate_artifact(record, "small_batch_risk_record")
    # No block / gate / pass / fail fields exist on this artifact. The
    # only readiness-shaped vocabulary it can carry is the
    # split_recommendation enum, which is observation-only.
    forbidden_field_names = {
        "block",
        "gate_status",
        "pr_ready_status",
        "pr_update_ready_status",
        "ready",
        "not_ready",
    }
    assert not (forbidden_field_names & set(record.keys()))
    assert record["authority_scope"] == "observation_only"


def test_schema_authority_scope_is_const_observation_only():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    auth = schema["properties"]["authority_scope"]
    assert auth["const"] == "observation_only"


# ---------------------------------------------------------------------------
# APR integration — AEX phase emits the artifact ref
# ---------------------------------------------------------------------------


def test_apr_aex_includes_small_batch_risk_artifact_ref(tmp_path):
    changed_paths = ["docs/governance/pytest_pr_selection_integrity_policy.json"]
    output_dir = tmp_path / "apr"
    result = aex_required_surface_check(
        repo_root=REPO_ROOT,
        changed_paths=changed_paths,
        output_dir=output_dir,
        base_ref="origin/main",
        head_ref="HEAD",
    )
    refs = result.output_artifact_refs
    assert any(
        ref.endswith("small_batch_risk_record.json") for ref in refs
    ), f"small_batch_risk_record artifact ref missing from {refs}"


def test_apr_aex_emits_small_batch_risk_record_on_disk():
    aex_required_surface_check(
        repo_root=REPO_ROOT,
        changed_paths=[
            "docs/governance/pytest_pr_selection_integrity_policy.json"
        ],
        output_dir=REPO_ROOT / "outputs" / "agent_pr_precheck",
        base_ref="origin/main",
        head_ref="HEAD",
    )
    sbr_path = (
        REPO_ROOT
        / "outputs"
        / "small_batch_risk"
        / "small_batch_risk_record.json"
    )
    assert sbr_path.is_file(), "AEX should emit small_batch_risk_record"
    data = json.loads(sbr_path.read_text(encoding="utf-8"))
    validate_artifact(data, "small_batch_risk_record")
    assert data["authority_scope"] == "observation_only"


def test_apr_does_not_block_on_risk_level(tmp_path):
    # APR's AEX check status is determined by the required-surface
    # mapping result only. The small-batch risk artifact exists alongside
    # but never flips the AEX status to block.
    changed_paths = [
        "contracts/schemas/x.schema.json",
        "contracts/examples/x.example.json",
        "contracts/standards-manifest.json",
        "spectrum_systems/modules/runtime/y.py",
        "scripts/z.py",
        "tests/test_w.py",
        ".github/workflows/v.yml",
        "artifacts/tls/system_dependency_priority_report.json",
    ]
    output_dir = tmp_path / "apr"
    result = aex_required_surface_check(
        repo_root=REPO_ROOT,
        changed_paths=changed_paths,
        output_dir=output_dir,
        base_ref="origin/main",
        head_ref="HEAD",
    )
    # The result may pass or block based on required-surface mapping —
    # but its block reason cannot reference the risk_level artifact.
    for code in result.reason_codes:
        assert "very_high" not in code
        assert "risk_level" not in code


# ---------------------------------------------------------------------------
# Builder script CLI smoke
# ---------------------------------------------------------------------------


def test_builder_script_writes_validated_record(tmp_path):
    import subprocess

    out_rel = tmp_path / "small_batch_risk_record.json"
    rc = subprocess.run(
        [
            sys.executable,
            "scripts/build_small_batch_risk_record.py",
            "--base-ref",
            "origin/main",
            "--head-ref",
            "HEAD",
            "--output",
            str(out_rel),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rc.returncode == 0, rc.stderr
    data = json.loads(out_rel.read_text(encoding="utf-8"))
    validate_artifact(data, "small_batch_risk_record")
    assert data["artifact_type"] == "small_batch_risk_record"
    assert data["authority_scope"] == "observation_only"
