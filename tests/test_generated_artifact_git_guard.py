"""Tests for scripts/run_generated_artifact_git_guard.py.

The guard prevents recurrence of the merge-conflict failure mode where
generated run-specific artifacts (e.g.
``artifacts/certification_judgment_40_explicit/*.json``) are hand-merged
across branches with divergent timestamps and trace IDs.

These tests are deterministic and self-contained: they construct an isolated
repo root with a synthetic policy and exercise the guard's classification and
fail-closed behavior directly. They do not mutate the live repository.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_generated_artifact_git_guard as guard  # noqa: E402

LIVE_POLICY_PATH = REPO_ROOT / "config" / "generated_artifact_policy.json"


def _synthetic_policy() -> dict:
    return {
        "artifact_type": "generated_artifact_policy",
        "schema_version": "1.0.0",
        "policy_version": "test-1.0",
        "denylist": [
            {
                "path_glob": "artifacts/certification_judgment_40_explicit/*.json",
                "regenerator": "scripts/run_certification_judgment_40_explicit.py",
                "rationale": "test",
                "owner": "PRG",
                "kind": "certification_run_state",
            },
            {
                "path_glob": "artifacts/pqx_runs/**/*.json",
                "regenerator": "scripts/pqx_runner.py",
                "rationale": "test",
                "owner": "PQX",
                "kind": "execution_run_state",
            },
            {
                "path_glob": "artifacts/test_tmp/**/*.json",
                "regenerator": None,
                "rationale": "test",
                "owner": "test_harness",
                "kind": "test_run_state",
            },
        ],
        "allowlist": [
            {
                "path_glob": "artifacts/tls/*_redteam_report.json",
                "rationale": "review record",
                "kind": "review_record",
            },
            {
                "path_glob": "artifacts/roadmap/**",
                "rationale": "governance",
                "kind": "governance_record",
            },
        ],
        "schema_paths": [
            "contracts/schemas/**",
            "contracts/examples/**",
            "schemas/**",
        ],
        "documentation_paths": [
            "docs/**",
            "*.md",
        ],
        "test_fixture_paths": [
            "tests/**",
            "examples/**",
        ],
        "regeneration_exceptions": [],
    }


@pytest.fixture()
def policy() -> dict:
    return _synthetic_policy()


# ---------------------------------------------------------------------------
# Policy loader fail-closed behavior
# ---------------------------------------------------------------------------


def test_load_policy_fails_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(guard.GeneratedArtifactGuardError, match="missing"):
        guard.load_policy(tmp_path / "nope.json")


def test_load_policy_fails_on_malformed_json(tmp_path: Path) -> None:
    bad = tmp_path / "policy.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(guard.GeneratedArtifactGuardError, match="malformed"):
        guard.load_policy(bad)


def test_load_policy_fails_on_wrong_artifact_type(tmp_path: Path) -> None:
    bad = tmp_path / "policy.json"
    bad.write_text(json.dumps({"artifact_type": "other"}), encoding="utf-8")
    with pytest.raises(guard.GeneratedArtifactGuardError, match="artifact_type"):
        guard.load_policy(bad)


def test_load_policy_fails_when_required_key_missing(tmp_path: Path, policy: dict) -> None:
    del policy["denylist"]
    bad = tmp_path / "policy.json"
    bad.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(guard.GeneratedArtifactGuardError, match="denylist"):
        guard.load_policy(bad)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_certification_judgment_40_explicit_paths_are_denylisted(policy: dict) -> None:
    verdict = guard.classify_path(
        "artifacts/certification_judgment_40_explicit/checkpoint-1.json", policy
    )
    assert verdict["classification"] == "denylisted"
    assert verdict["matched_entry"]["regenerator"] == (
        "scripts/run_certification_judgment_40_explicit.py"
    )


def test_pqx_runs_recursive_glob_matches(policy: dict) -> None:
    verdict = guard.classify_path(
        "artifacts/pqx_runs/pqx_003/some_record.json", policy
    )
    assert verdict["classification"] == "denylisted"


def test_contracts_schemas_paths_are_not_blocked(policy: dict) -> None:
    verdict = guard.classify_path("contracts/schemas/foo.schema.json", policy)
    assert verdict["classification"] == "schema"


def test_contracts_examples_paths_are_not_blocked(policy: dict) -> None:
    verdict = guard.classify_path("contracts/examples/abstention_record.json", policy)
    assert verdict["classification"] == "schema"


def test_docs_review_paths_are_not_blocked(policy: dict) -> None:
    verdict = guard.classify_path("docs/reviews/some_review.md", policy)
    assert verdict["classification"] == "documentation"


def test_canonical_review_artifacts_are_allowlisted(policy: dict) -> None:
    verdict = guard.classify_path(
        "artifacts/tls/d3l_priority_freshness_redteam_report.json", policy
    )
    assert verdict["classification"] == "allowlisted"


def test_unknown_artifact_path_classifies_as_unknown(policy: dict) -> None:
    verdict = guard.classify_path(
        "artifacts/some_new_engine/output.json", policy
    )
    assert verdict["classification"] == "unknown"


def test_test_fixture_paths_are_not_blocked(policy: dict) -> None:
    verdict = guard.classify_path("tests/fixtures/sample.json", policy)
    assert verdict["classification"] == "test_fixture"


# ---------------------------------------------------------------------------
# Evaluation: full guard logic against synthetic changed-file lists
# ---------------------------------------------------------------------------


def test_changed_certification_artifact_without_regenerator_blocks(
    tmp_path: Path, policy: dict
) -> None:
    changed = ["artifacts/certification_judgment_40_explicit/checkpoint-1.json"]
    result = guard.evaluate_changed_files(
        changed_files=changed, policy=policy, repo_root=tmp_path
    )
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["reason_code"] == "GENERATED_ARTIFACT_HAND_MERGE_BLOCKED"
    assert "generated run-specific artifact" in finding["remediation"]


def test_changed_certification_artifact_with_regenerator_passes(
    tmp_path: Path, policy: dict
) -> None:
    changed = [
        "artifacts/certification_judgment_40_explicit/checkpoint-1.json",
        "scripts/run_certification_judgment_40_explicit.py",
    ]
    result = guard.evaluate_changed_files(
        changed_files=changed, policy=policy, repo_root=tmp_path
    )
    assert result["findings"] == []
    assert (
        "scripts/run_certification_judgment_40_explicit.py"
        in result["regenerator_scripts_in_pr"]
    )


def test_unknown_artifact_path_fails_closed(tmp_path: Path, policy: dict) -> None:
    changed = ["artifacts/brand_new_engine/output.json"]
    result = guard.evaluate_changed_files(
        changed_files=changed, policy=policy, repo_root=tmp_path
    )
    assert len(result["findings"]) == 1
    assert result["findings"][0]["reason_code"] == "GENERATED_ARTIFACT_UNCLASSIFIED"


def test_unknown_path_outside_artifacts_does_not_fail(
    tmp_path: Path, policy: dict
) -> None:
    changed = ["src/some/source.py"]
    result = guard.evaluate_changed_files(
        changed_files=changed, policy=policy, repo_root=tmp_path
    )
    assert result["findings"] == []


def test_canonical_review_artifact_change_passes(tmp_path: Path, policy: dict) -> None:
    changed = ["artifacts/tls/d3l_priority_freshness_redteam_report.json"]
    result = guard.evaluate_changed_files(
        changed_files=changed, policy=policy, repo_root=tmp_path
    )
    assert result["findings"] == []


def test_schema_change_passes(tmp_path: Path, policy: dict) -> None:
    changed = ["contracts/schemas/foo.schema.json"]
    result = guard.evaluate_changed_files(
        changed_files=changed, policy=policy, repo_root=tmp_path
    )
    assert result["findings"] == []


def test_leftover_conflict_marker_in_denylisted_artifact_blocks(
    tmp_path: Path, policy: dict
) -> None:
    rel = "artifacts/certification_judgment_40_explicit/checkpoint-1.json"
    artifact = tmp_path / rel
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{\n"a": 1\n<<<<<<< HEAD\n,"b": 2\n=======\n,"b": 3\n>>>>>>> branch\n}\n',
        encoding="utf-8",
    )
    # Include the regenerator change to isolate the conflict-marker failure path.
    changed = [
        rel,
        "scripts/run_certification_judgment_40_explicit.py",
    ]
    result = guard.evaluate_changed_files(
        changed_files=changed, policy=policy, repo_root=tmp_path
    )
    reason_codes = {f["reason_code"] for f in result["findings"]}
    assert "GENERATED_ARTIFACT_LEFTOVER_CONFLICT_MARKER" in reason_codes


def test_regeneration_exception_unblocks_specific_path(
    tmp_path: Path, policy: dict
) -> None:
    policy["regeneration_exceptions"].append(
        {
            "path_glob": "artifacts/certification_judgment_40_explicit/*.json",
            "rationale": "scheduled re-run after upstream input refresh",
            "approved_by": "PRG",
            "expires_after": "2099-01-01",
        }
    )
    changed = ["artifacts/certification_judgment_40_explicit/checkpoint-1.json"]
    result = guard.evaluate_changed_files(
        changed_files=changed, policy=policy, repo_root=tmp_path
    )
    assert result["findings"] == []


# ---------------------------------------------------------------------------
# Live-policy sanity checks (the in-repo policy file)
# ---------------------------------------------------------------------------


def test_live_policy_loads_cleanly() -> None:
    policy = guard.load_policy(LIVE_POLICY_PATH)
    assert policy["artifact_type"] == "generated_artifact_policy"
    # Spot-check that the conflict-prone path is on the denylist.
    matched = [
        e for e in policy["denylist"]
        if "certification_judgment_40_explicit" in e["path_glob"]
    ]
    assert matched, "certification_judgment_40_explicit must be denylisted"
    assert matched[0]["regenerator"].endswith(
        "run_certification_judgment_40_explicit.py"
    )


def test_live_policy_classifies_known_paths() -> None:
    policy = guard.load_policy(LIVE_POLICY_PATH)
    cases = {
        "artifacts/certification_judgment_40_explicit/checkpoint-1.json": "denylisted",
        "artifacts/review_fix_loop_36_explicit/delivery_report.json": "denylisted",
        "artifacts/pqx_runs/pqx_003/example.json": "denylisted",
        "artifacts/tls/d3l_priority_freshness_redteam_report.json": "allowlisted",
        "contracts/schemas/foo.schema.json": "schema",
        "contracts/examples/abstention_record.json": "schema",
        "docs/architecture/foo.md": "documentation",
        "tests/fixtures/x.json": "test_fixture",
    }
    for path, expected in cases.items():
        verdict = guard.classify_path(path, policy)
        assert verdict["classification"] == expected, (path, verdict)


def test_remediation_message_is_clear_and_actionable() -> None:
    assert "generated run-specific artifact" in guard.REMEDIATION_MESSAGE
    assert "Regenerate" in guard.REMEDIATION_MESSAGE
    assert "allowlist" in guard.REMEDIATION_MESSAGE


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_main_writes_result_artifact_and_returns_zero_for_clean_change(
    tmp_path: Path, policy: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    output_path = tmp_path / "out" / "result.json"

    # Inject explicit changed files via CLI to bypass git resolution.
    rc = guard.main(
        [
            "--changed-files",
            "src/foo.py",
            "--policy",
            "policy.json",
            "--output",
            "out/result.json",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "generated_artifact_git_guard_result"
    assert payload["status"] == "pass"


def test_main_returns_one_when_denylisted_artifact_changed_alone(
    tmp_path: Path, policy: dict
) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    output_path = tmp_path / "out" / "result.json"

    rc = guard.main(
        [
            "--changed-files",
            "artifacts/certification_judgment_40_explicit/checkpoint-1.json",
            "--policy",
            "policy.json",
            "--output",
            "out/result.json",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert payload["finding_count"] >= 1
