"""HOP query CLI tests."""

from __future__ import annotations

import json

import pytest

from spectrum_systems.cli import hop_cli
from spectrum_systems.modules.hop import baseline_harness
from spectrum_systems.modules.hop.evaluator import evaluate_candidate
from tests.hop.conftest import make_baseline_candidate


def _seed(store, eval_set, capsys=None):
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    evaluate_candidate(
        candidate_payload=candidate,
        runner=baseline_harness.run,
        eval_set=eval_set,
        store=store,
    )
    return candidate


def test_list_top_candidates(store, eval_set, capsys) -> None:
    _seed(store, eval_set)
    rc = hop_cli.main(["--root", str(store.root), "list-top-candidates", "--limit", "5"])
    assert rc == 0
    out = capsys.readouterr().out
    rows = json.loads(out)
    assert len(rows) == 1
    assert rows[0]["candidate_id"] == "baseline_v1"
    assert 0 <= rows[0]["score"] <= 1


def test_show_frontier(store, eval_set, capsys) -> None:
    _seed(store, eval_set)
    rc = hop_cli.main(["--root", str(store.root), "show-frontier"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["considered_count"] == 1
    assert payload["member_count"] == 1
    assert payload["invalid_count"] == 0
    assert payload["max_frontier_window"] >= 1


def test_show_frontier_respects_max_window(store, eval_set, capsys) -> None:
    _seed(store, eval_set)
    rc = hop_cli.main(
        [
            "--root",
            str(store.root),
            "show-frontier",
            "--max-frontier-window",
            "1",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["max_frontier_window"] == 1
    assert payload["member_count"] == 1


def test_show_frontier_rejects_zero_window(store, eval_set, capsys) -> None:
    _seed(store, eval_set)
    rc = hop_cli.main(
        [
            "--root",
            str(store.root),
            "show-frontier",
            "--max-frontier-window",
            "0",
        ]
    )
    assert rc == 2


def test_show_failures(store, eval_set, capsys) -> None:
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)

    def bad_runner(_):
        raise RuntimeError("boom")

    evaluate_candidate(
        candidate_payload=candidate,
        runner=bad_runner,
        eval_set=eval_set,
        store=store,
    )
    rc = hop_cli.main(
        ["--root", str(store.root), "show-failures", "--severity", "reject", "--limit", "5"]
    )
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows
    assert rows[0]["fields"]["failure_class"] == "runtime_error"


def test_inspect_trace(store, eval_set, capsys) -> None:
    _seed(store, eval_set)
    # Pick a trace from the index.
    trace_records = list(store.iter_index(artifact_type="hop_harness_trace"))
    assert trace_records
    trace_id = trace_records[0]["artifact_id"]
    rc = hop_cli.main(["--root", str(store.root), "inspect-trace", trace_id])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["artifact_type"] == "hop_harness_trace"


def test_diff_candidates(store, eval_set, capsys) -> None:
    candidate_a = make_baseline_candidate()
    store.write_artifact(candidate_a)
    candidate_b = make_baseline_candidate(code_source=candidate_a["code_source"] + "\n# variant\n")
    candidate_b["candidate_id"] = "baseline_v2"
    from spectrum_systems.modules.hop.artifacts import finalize_artifact

    candidate_b.pop("content_hash", None)
    candidate_b.pop("artifact_id", None)
    finalize_artifact(candidate_b, id_prefix="hop_candidate_")
    store.write_artifact(candidate_b)

    rc = hop_cli.main(
        [
            "--root",
            str(store.root),
            "diff-candidates",
            "--left",
            "baseline_v1",
            "--right",
            "baseline_v2",
        ]
    )
    assert rc == 0
    diff = json.loads(capsys.readouterr().out)
    assert "code_source" in diff["differences"]
    assert "candidate_id" in diff["differences"]


def test_cli_diff_missing_candidate_emits_error(store, capsys) -> None:
    rc = hop_cli.main(
        [
            "--root",
            str(store.root),
            "diff-candidates",
            "--left",
            "ghost_a",
            "--right",
            "ghost_b",
        ]
    )
    assert rc == 2


def test_cli_inspect_trace_missing_artifact_emits_error(store, capsys) -> None:
    rc = hop_cli.main(
        ["--root", str(store.root), "inspect-trace", "hop_trace_does_not_exist"]
    )
    assert rc == 2
