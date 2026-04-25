"""Optional repository/runtime bootstrap snapshot for harness context."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def build_bootstrap_snapshot(
    *,
    repo_root: str | Path,
    workflow_id: str,
    max_entries: int = 40,
    trace_id: str = "hop_bootstrap",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    files = sorted(
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if ".git" not in path.parts
    )[:max_entries]
    cli_commands = [
        "python -m spectrum_systems.cli.hop_cli --help",
        "python -m spectrum_systems.cli.hop_cli evaluate-baseline",
    ]
    test_commands = [
        "pytest tests/hop/test_evaluator.py",
        "pytest tests/hop/test_optimization_loop.py",
    ]
    schemas = sorted(str(p.name) for p in (root / "contracts" / "schemas" / "hop").glob("*.json"))[:max_entries]

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_bootstrap_snapshot",
        "schema_ref": "hop/harness_bootstrap_snapshot.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "snapshot_id": f"bootstrap_{workflow_id}",
        "workflow_id": workflow_id,
        "repo_structure": files,
        "schema_files": schemas,
        "cli_commands": cli_commands,
        "test_commands": test_commands,
        "context_budget_tokens": 4000,
    }
    finalize_artifact(payload, id_prefix="hop_bootstrap_")
    validate_hop_artifact(payload, "hop_harness_bootstrap_snapshot")
    return payload
