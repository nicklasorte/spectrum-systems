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


def test_cli_execute_fixes_non_zero_on_blocked_fix(tmp_path: Path) -> None:
    plan = tmp_path / "execution_bundles.md"
    state = tmp_path / "state.json"
    out = tmp_path / "out"
    _plan(plan)

    state.write_text(
        json.dumps(
            {
                "schema_version": "1.3.0",
                "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
                "execution_plan_ref": str(plan),
                "run_id": "run-b7-cli-001",
                "sequence_run_id": "queue-run-b7-cli-001",
                "active_bundle_id": "BUNDLE-T1",
                "completed_bundle_ids": [],
                "completed_step_ids": [],
                "blocked_step_ids": [],
                "pending_fix_ids": [
                    {
                        "fix_id": "fix:REV-B7:F-001",
                        "source_review_id": "REV-B7",
                        "source_finding_id": "F-001",
                        "severity": "high",
                        "priority": "P1",
                        "affected_step_ids": ["AI-01"],
                        "status": "open",
                        "blocking": True,
                        "created_from_bundle_id": "BUNDLE-T1",
                        "created_from_run_id": "run-b7-cli-001",
                        "notes": "patch runtime",
                        "artifact_refs": [],
                    }
                ],
                "executed_fixes": [],
                "failed_fixes": [],
                "fix_artifacts": {},
                "reinsertion_points": {},
                "review_artifact_refs": [],
                "fix_gate_results": {},
                "resolved_fixes": ["fix:REV-B7:F-001"],
                "unresolved_fixes": [],
                "last_fix_gate_status": None,
                "review_requirements": [],
                "satisfied_review_checkpoint_ids": [],
                "artifact_index": {},
                "resume_position": {
                    "bundle_id": "BUNDLE-T1",
                    "next_step_id": "AI-01",
                    "resume_token": "resume:queue-run-b7-cli-001:BUNDLE-T1:0",
                },
                "created_at": "2026-03-29T12:00:00Z",
                "updated_at": "2026-03-29T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )

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
        "run-b7-cli-001",
        "--sequence-run-id",
        "queue-run-b7-cli-001",
        "--trace-id",
        "trace-b7-cli-001",
        "--bundle-plan-path",
        str(plan),
        "--execute-fixes",
    ]
    env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
    blocked = subprocess.run(run_cmd, capture_output=True, text=True, check=False, env=env)
    assert blocked.returncode == 2


def test_cli_emit_triage_plan_blocking_exit(tmp_path: Path) -> None:
    plan = tmp_path / "execution_bundles.md"
    out = tmp_path / "triage.json"
    _plan(plan)
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "review_id": "REV-CLI-B10",
                "checkpoint_id": "BUNDLE-T1:checkpoint:AI-01",
                "review_type": "checkpoint_review",
                "bundle_id": "BUNDLE-T1",
                "bundle_run_id": "queue-run-b10-cli-001",
                "roadmap_authority_ref": "docs/roadmaps/system_roadmap.md",
                "execution_plan_ref": str(plan),
                "scope": {"scope_type": "step", "step_id": "AI-01"},
                "findings": [
                    {
                        "finding_id": "F-001",
                        "severity": "critical",
                        "category": "runtime",
                        "title": "critical issue",
                        "description": "critical issue",
                        "affected_step_ids": ["AI-01"],
                        "recommended_action": "fix now",
                        "blocking": True,
                        "source_refs": ["docs/review-actions/REV-CLI-B10.md#f1"],
                    }
                ],
                "overall_disposition": "approved_with_findings",
                "created_at": "2026-03-29T12:00:00Z",
                "provenance_refs": ["trace:cli:b10"],
            }
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
    cmd = [
        sys.executable,
        "scripts/run_pqx_bundle.py",
        "emit-triage-plan",
        "--bundle-id",
        "BUNDLE-T1",
        "--bundle-plan-path",
        str(plan),
        "--run-id",
        "run-b10-cli-001",
        "--sequence-run-id",
        "queue-run-b10-cli-001",
        "--trace-id",
        "trace-b10-cli-001",
        "--created-at",
        "2026-03-29T12:02:00Z",
        "--output-path",
        str(out),
        "--review-artifact-ref",
        str(review),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    assert proc.returncode == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary_counts"]["blocking_total"] == 1
