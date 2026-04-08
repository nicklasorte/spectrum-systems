from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "run_harness_integrity_bundle",
        Path("scripts/run_harness_integrity_bundle.py"),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_only_fails_when_review_exists_and_outputs_missing(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    review = tmp_path / "harness_integrity_review.md"
    review.write_text("review exists", encoding="utf-8")
    monkeypatch.setattr(module, "REVIEW_DOC_PATH", review)

    rc = module.main(["--verify-only", "--output-dir", str(tmp_path / "missing")])
    assert rc == 2


def test_run_bundle_emits_real_outputs_and_metrics(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    review = tmp_path / "harness_integrity_review.md"
    review.write_text("review exists", encoding="utf-8")
    monkeypatch.setattr(module, "REVIEW_DOC_PATH", review)

    out_dir = tmp_path / "bundle"
    rc = module.main(["--output-dir", str(out_dir)])
    assert rc == 0

    for name in module.REQUIRED_OUTPUTS:
        target = out_dir / name
        assert target.exists(), f"missing output {name}"
        assert target.stat().st_size > 2, f"empty output {name}"
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), f"non-structured output {name}"
        assert payload, f"placeholder-like empty object in {name}"

    failure = json.loads((out_dir / "failure_injection_report.json").read_text(encoding="utf-8"))
    assert failure["case_count"] >= 3
    assert len(failure["scenarios"]) >= 3
    assert {"scenario", "expected_behavior", "observed_behavior", "pass"} <= set(failure["scenarios"][0].keys())

    transitions = json.loads((out_dir / "transition_consistency_report.json").read_text(encoding="utf-8"))
    assert transitions["cross_system_comparison_count"] >= 1
    assert len(transitions["comparisons"]) >= 3
    assert {"system", "raw_status", "status_bucket"} <= set(transitions["comparisons"][0].keys())

    trace = json.loads((out_dir / "trace_completeness_report.json").read_text(encoding="utf-8"))
    assert "coverage_ratio" in trace and "trace_links" in trace
    assert isinstance(trace["trace_links"], dict)

    replay = json.loads((out_dir / "replay_integrity_report.json").read_text(encoding="utf-8"))
    assert replay["deterministic_replay"] is True

    integrity = json.loads((out_dir / "harness_integrity_report.json").read_text(encoding="utf-8"))
    assert "checks" in integrity and len(integrity["checks"]) >= 3
    assert {"check_id", "passed", "details"} <= set(integrity["checks"][0].keys())

    index = json.loads((out_dir / "harness_bundle_index.json").read_text(encoding="utf-8"))
    assert "bundle_run_timestamp" in index
    assert "top_findings" in index
    assert "readiness_score" in index
    assert "blocking_findings_count" in index
    assert "warning_findings_count" in index

    verify_rc = module.main(["--verify-only", "--output-dir", str(out_dir)])
    assert verify_rc == 0
