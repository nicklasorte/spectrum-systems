from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _plan(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Test",
                "## EXECUTABLE BUNDLE TABLE",
                "| Bundle ID | Ordered Step IDs | Depends On |",
                "| --- | --- | --- |",
                "| BUNDLE-T1 | AI-01, AI-02 | - |",
                "",
                "## REVIEW CHECKPOINT TABLE",
                "| Checkpoint ID | Bundle ID | Review Type | Scope | Step ID | Required | Blocking Before Continue |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                "| BUNDLE-T1:checkpoint:AI-01 | BUNDLE-T1 | checkpoint_review | step | AI-01 | true | true |",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_cli_blocked_exit_then_ingest_success(tmp_path: Path) -> None:
    plan = tmp_path / "execution_bundles.md"
    state = tmp_path / "state.json"
    out = tmp_path / "out"
    _plan(plan)

    run_cmd = [
        sys.executable,
        "scripts/run_pqx_bundle.py",
        "run",
        "--bundle-id",
        "BUNDLE-T1",
        "--bundle-state-path",
        str(state),
        "--output-dir",
        str(out),
        "--run-id",
        "run-b6-cli-001",
        "--sequence-run-id",
        "queue-run-b6-cli-001",
        "--trace-id",
        "trace-b6-cli-001",
        "--bundle-plan-path",
        str(plan),
    ]
    env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
    blocked = subprocess.run(run_cmd, capture_output=True, text=True, check=False, env=env)
    assert blocked.returncode == 1

    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "review_id": "REV-CLI-001",
                "checkpoint_id": "BUNDLE-T1:checkpoint:AI-01",
                "review_type": "checkpoint_review",
                "bundle_id": "BUNDLE-T1",
                "bundle_run_id": "queue-run-b6-cli-001",
                "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
                "execution_plan_ref": str(plan),
                "scope": {"scope_type": "step", "step_id": "AI-01"},
                "findings": [],
                "overall_disposition": "approved",
                "created_at": "2026-03-29T12:00:00Z",
                "provenance_refs": ["trace:cli:1"],
            }
        ),
        encoding="utf-8",
    )

    ingest_cmd = [
        sys.executable,
        "scripts/run_pqx_bundle.py",
        "ingest-findings",
        "--bundle-id",
        "BUNDLE-T1",
        "--bundle-state-path",
        str(state),
        "--bundle-plan-path",
        str(plan),
        "--review-artifact-path",
        str(review_path),
        "--now",
        "2026-03-29T12:01:00Z",
    ]
    ingested = subprocess.run(ingest_cmd, capture_output=True, text=True, check=False, env=env)
    assert ingested.returncode == 0
