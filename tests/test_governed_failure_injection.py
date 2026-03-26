from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

from spectrum_systems.contracts import load_example, load_schema  # noqa: E402
from spectrum_systems.modules.runtime.governed_failure_injection import (  # noqa: E402
    list_case_ids,
    run_governed_failure_injection,
)
from spectrum_systems.modules.runtime.trace_engine import (  # noqa: E402
    clear_trace_store,
    create_trace_store,
    get_all_trace_ids,
    get_trace,
    start_trace,
)


def _validate_summary(summary: dict) -> None:
    schema = load_schema("governed_failure_injection_summary")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(summary)


def test_contract_example_validates() -> None:
    example = load_example("governed_failure_injection_summary")
    _validate_summary(example)


def test_runner_is_deterministic_for_ids_and_payload() -> None:
    first = run_governed_failure_injection()
    second = run_governed_failure_injection()
    assert first == second
    assert first["id"] == second["id"]
    first_ids = [item["artifact_id"] for item in first["results"]]
    second_ids = [item["artifact_id"] for item in second["results"]]
    assert first_ids == second_ids


def test_summary_schema_valid_and_counts_stable() -> None:
    summary = run_governed_failure_injection()
    _validate_summary(summary)
    assert summary["case_count"] == len(list_case_ids())
    assert summary["pass_count"] == summary["case_count"]
    assert summary["fail_count"] == 0


def test_required_failure_classes_fail_closed_or_allowed_by_policy() -> None:
    summary = run_governed_failure_injection()
    by_id = {item["injection_case_id"]: item for item in summary["results"]}

    blocked_cases = {
        "context_missing_upstream_refs",
        "monitor_contradictory_status",
        "monitor_malformed_digest",
        "replay_placeholder_ids",
        "replay_missing_trace_context",
        "evidence_required_grounded_empty_claims",
        "monitor_ingestion_malformed_regression",
        "replay_lineage_chain_mismatch",
        "trace_orphaned_parent_refs",
    }
    for case_id in blocked_cases:
        assert by_id[case_id]["observed_outcome"] == "block"
        assert by_id[case_id]["passed"] is True

    assert by_id["evidence_non_claim_applicable_allowed"]["observed_outcome"] == "allow"
    assert by_id["evidence_non_claim_applicable_allowed"]["passed"] is True


def test_global_trace_store_is_preserved_and_chaos_traces_are_isolated() -> None:
    clear_trace_store()
    preexisting = start_trace({"trace_id": "trace-preexisting", "run_id": "run-preexisting"})
    preexisting_snapshot = get_trace(preexisting)
    before = sorted(get_all_trace_ids())

    isolated_store = create_trace_store()
    summary = run_governed_failure_injection(trace_store=isolated_store)

    after = sorted(get_all_trace_ids())
    assert before == after
    assert preexisting in after
    assert get_trace(preexisting) == preexisting_snapshot
    assert all(item["run_linkage"]["trace_id"] != "trace-chaos-orphan" for item in summary["results"] if item["injection_case_id"] != "trace_orphaned_parent_refs")
    assert "trace-chaos-orphan" not in after
    clear_trace_store()


def test_mixed_global_and_injected_governed_runs_do_not_cross_contaminate() -> None:
    clear_trace_store()
    global_trace = start_trace({"trace_id": "trace-global-preexisting", "run_id": "run-global"})
    global_snapshot = get_trace(global_trace)
    before_global = sorted(get_all_trace_ids())

    isolated_store = create_trace_store()
    summary_isolated = run_governed_failure_injection(
        case_filter=["trace_orphaned_parent_refs"],
        trace_store=isolated_store,
    )
    final_global = sorted(get_all_trace_ids())
    assert final_global == before_global
    assert summary_isolated["results"][0]["passed"] is True
    assert global_trace in final_global
    assert get_trace(global_trace) == global_snapshot

    clear_trace_store()


def test_orphan_case_still_fails_closed_with_isolated_store() -> None:
    isolated_store = create_trace_store()
    summary = run_governed_failure_injection(case_filter=["trace_orphaned_parent_refs"], trace_store=isolated_store)
    result = summary["results"][0]
    assert result["injection_case_id"] == "trace_orphaned_parent_refs"
    assert result["observed_outcome"] == "block"
    assert result["passed"] is True


def test_cli_exit_zero_and_writes_artifact(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "run_governed_failure_injection.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--output-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    output = json.loads(proc.stdout)
    artifact_path = Path(output["output"])
    assert artifact_path.exists()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    _validate_summary(payload)


def test_cli_filter_and_unknown_case_handling(tmp_path: Path) -> None:
    case_filter = json.loads((REPO_ROOT / "tests" / "fixtures" / "governed_failure_injection_cases.json").read_text(encoding="utf-8"))
    script = REPO_ROOT / "scripts" / "run_governed_failure_injection.py"

    ok = subprocess.run(
        [sys.executable, str(script), "--output-dir", str(tmp_path), "--cases", *case_filter],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stderr
    payload = json.loads(Path(json.loads(ok.stdout)["output"]).read_text(encoding="utf-8"))
    assert payload["case_count"] == len(case_filter)

    bad = subprocess.run(
        [sys.executable, str(script), "--output-dir", str(tmp_path), "--cases", "does-not-exist"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode == 2
    assert "Unknown case id" in bad.stderr
