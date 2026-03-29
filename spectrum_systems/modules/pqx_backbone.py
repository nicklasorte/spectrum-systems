"""Minimum governed execution backbone for PQX roadmap rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


REPO_ROOT = Path(__file__).resolve().parents[2]
ROADMAP_AUTHORITY_PATH = REPO_ROOT / "docs" / "roadmaps" / "roadmap_authority.md"
ACTIVE_ROADMAP_PATH = REPO_ROOT / "docs" / "roadmaps" / "system_roadmap.md"
LEGACY_EXECUTION_ROADMAP_PATH = REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"
STATE_PATH = REPO_ROOT / "data" / "pqx_state.json"
RUNS_ROOT = REPO_ROOT / "data" / "pqx_runs"


class PQXBackboneError(ValueError):
    """Raised when fail-closed PQX execution conditions are violated."""


@dataclass(frozen=True)
class RoadmapRow:
    row_index: int
    step_id: str
    step_name: str
    dependencies: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class RoadmapAuthorityResolution:
    active_authority_path: Path
    active_authority_ref: str
    execution_roadmap_path: Path
    execution_roadmap_ref: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now(clock=utc_now) -> str:
    return clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_dependencies(raw: str) -> tuple[str, ...]:
    normalized = raw.strip()
    if not normalized or normalized in {"—", "-"}:
        return ()
    return tuple(dep.strip() for dep in normalized.split(",") if dep.strip())


def resolve_roadmap_authority(
    *,
    authority_path: Path = ROADMAP_AUTHORITY_PATH,
    active_path: Path = ACTIVE_ROADMAP_PATH,
    legacy_execution_path: Path = LEGACY_EXECUTION_ROADMAP_PATH,
) -> RoadmapAuthorityResolution:
    expected_active = "docs/roadmaps/system_roadmap.md"
    expected_legacy = "docs/roadmap/system_roadmap.md"
    expected_contract = "docs/roadmap/roadmap_step_contract.md"

    for path in (authority_path, active_path, legacy_execution_path):
        if not path.is_file():
            raise PQXBackboneError(f"Roadmap authority bridge file is missing: {path}")

    authority_text = authority_path.read_text(encoding="utf-8")
    if f"**Active editorial authority:** `{expected_active}`" not in authority_text:
        raise PQXBackboneError("Authority doc missing active roadmap declaration.")
    if f"**Operational compatibility mirror (required until migration complete):** `{expected_legacy}`" not in authority_text:
        raise PQXBackboneError("Authority doc missing required legacy compatibility mirror declaration.")

    active_text = active_path.read_text(encoding="utf-8")
    if f"Compatibility transition rule: `{expected_legacy}` is a required parseable operational mirror" not in active_text:
        raise PQXBackboneError("Active roadmap missing compatibility transition rule for legacy execution mirror.")

    legacy_text = legacy_execution_path.read_text(encoding="utf-8")
    if f"Active editorial roadmap authority: `{expected_active}`" not in legacy_text:
        raise PQXBackboneError("Legacy execution roadmap missing active authority reference.")
    if expected_contract not in legacy_text:
        raise PQXBackboneError("Legacy execution roadmap missing step contract reference.")

    return RoadmapAuthorityResolution(
        active_authority_path=active_path,
        active_authority_ref=expected_active,
        execution_roadmap_path=legacy_execution_path,
        execution_roadmap_ref=expected_legacy,
    )


def parse_system_roadmap(path: Path | None = None) -> list[RoadmapRow]:
    resolved_path = path or resolve_roadmap_authority().execution_roadmap_path
    try:
        roadmap_ref = str(resolved_path.relative_to(REPO_ROOT))
    except ValueError:
        roadmap_ref = str(resolved_path)
    lines = resolved_path.read_text(encoding="utf-8").splitlines()
    header_idx = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("| Step ID "):
            header_idx = idx
            break

    if header_idx is None:
        raise PQXBackboneError(f"Roadmap table header not found in {roadmap_ref}.")

    rows: list[RoadmapRow] = []
    for line in lines[header_idx + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
        if len(cells) < 15:
            continue
        step_id = cells[0]
        if not step_id:
            continue
        rows.append(
            RoadmapRow(
                row_index=len(rows),
                step_id=step_id,
                step_name=cells[1],
                dependencies=_parse_dependencies(cells[11]),
                status=cells[14],
            )
        )

    if not rows:
        raise PQXBackboneError("Roadmap table parsed with zero execution rows.")

    return rows


def _validate_with_schema(payload: dict, schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: str(err.path))
    if errors:
        raise PQXBackboneError(f"Schema '{schema_name}' validation failed: {'; '.join(e.message for e in errors)}")


def load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {"schema_version": "1.0.0", "rows": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    _validate_with_schema(payload, "pqx_row_state")
    return payload


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    _validate_with_schema(state, "pqx_row_state")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _ensure_row_state(state: dict, step_id: str) -> dict:
    for row in state["rows"]:
        if row["step_id"] == step_id:
            return row

    row_state = {
        "step_id": step_id,
        "status": "not_started",
        "last_run": None,
        "dependencies_satisfied": False,
        "retries": 0,
    }
    state["rows"].append(row_state)
    return _ensure_row_state(state, step_id)


def resolve_executable_row(
    rows: list[RoadmapRow],
    state: dict,
    *,
    step_id: str | None = None,
) -> tuple[RoadmapRow | None, dict | None]:
    row_lookup = {row.step_id: row for row in rows}
    if step_id and step_id not in row_lookup:
        return None, {
            "block_type": "MISSING_ROW",
            "reason": f"Requested roadmap row '{step_id}' was not found.",
            "step_id": step_id,
            "blocking_dependencies": [],
        }

    candidate_rows = [row_lookup[step_id]] if step_id else sorted(rows, key=lambda row: row.row_index)
    blocked_candidates: list[dict] = []

    for row in candidate_rows:
        row_state = _ensure_row_state(state, row.step_id)
        if row_state["status"] == "complete":
            if step_id:
                return None, {
                    "block_type": "MISSING_ROW",
                    "reason": f"Requested roadmap row '{row.step_id}' is already complete.",
                    "step_id": row.step_id,
                    "blocking_dependencies": [],
                }
            continue

        missing_dependencies: list[str] = []
        incomplete_dependencies: list[str] = []
        for dependency_id in row.dependencies:
            if dependency_id not in row_lookup:
                missing_dependencies.append(dependency_id)
                continue
            dependency_state = _ensure_row_state(state, dependency_id)
            if dependency_state["status"] != "complete":
                incomplete_dependencies.append(dependency_id)

        if missing_dependencies:
            row_state["dependencies_satisfied"] = False
            blocked = {
                "block_type": "DEPENDENCY_UNSATISFIED",
                "reason": f"Dependency '{missing_dependencies[0]}' for row '{row.step_id}' is missing from roadmap.",
                "step_id": row.step_id,
                "blocking_dependencies": missing_dependencies,
            }
            if step_id:
                return None, blocked
            blocked_candidates.append(blocked)
            continue

        if incomplete_dependencies:
            row_state["dependencies_satisfied"] = False
            blocked = {
                "block_type": "DEPENDENCY_UNSATISFIED",
                "reason": f"Dependency '{incomplete_dependencies[0]}' for row '{row.step_id}' is not complete.",
                "step_id": row.step_id,
                "blocking_dependencies": incomplete_dependencies,
            }
            if step_id:
                return None, blocked
            blocked_candidates.append(blocked)
            continue

        row_state["dependencies_satisfied"] = True
        return row, None

    if blocked_candidates:
        return None, blocked_candidates[0]

    return None, {
        "block_type": "UNKNOWN",
        "reason": "No executable roadmap row found.",
        "step_id": step_id,
        "blocking_dependencies": [],
    }


def _write_artifact(payload: dict, schema_name: str, path: Path) -> Path:
    _validate_with_schema(payload, schema_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def run_pqx_backbone(
    *,
    selected_step_id: str | None,
    pqx_output_text: str | None,
    roadmap_path: Path | None = None,
    state_path: Path = STATE_PATH,
    runs_root: Path = RUNS_ROOT,
    clock=utc_now,
) -> dict:
    run_id = f"pqx-run-{iso_now(clock).replace(':', '').replace('-', '')}"
    try:
        authority = resolve_roadmap_authority()
        selected_roadmap_path = roadmap_path or authority.execution_roadmap_path
        state = load_state(state_path)
        rows = parse_system_roadmap(selected_roadmap_path)
    except PQXBackboneError as exc:
        block_payload = {
            "schema_version": "1.1.0",
            "run_id": run_id,
            "step_id": selected_step_id,
            "blocked_at": iso_now(clock),
            "block_type": "SCHEMA_INVALID",
            "reason": str(exc),
            "blocking_dependencies": [],
        }
        target_dir = runs_root / (selected_step_id or "_blocked")
        block_path = _write_artifact(block_payload, "pqx_block_record", target_dir / f"{run_id}.block_record.json")
        return {"status": "blocked", "block_record": str(block_path)}

    row, block = resolve_executable_row(rows, state, step_id=selected_step_id)
    if block:
        block_payload = {
            "schema_version": "1.1.0",
            "run_id": run_id,
            "step_id": block.get("step_id"),
            "blocked_at": iso_now(clock),
            "block_type": block["block_type"],
            "reason": block["reason"],
            "blocking_dependencies": block.get("blocking_dependencies", []),
        }
        target_dir = runs_root / (block.get("step_id") or "_blocked")
        block_path = _write_artifact(block_payload, "pqx_block_record", target_dir / f"{run_id}.block_record.json")
        save_state(state, state_path)
        return {"status": "blocked", "block_record": str(block_path)}

    assert row is not None
    if pqx_output_text is None:
        block_payload = {
            "schema_version": "1.1.0",
            "run_id": run_id,
            "step_id": row.step_id,
            "blocked_at": iso_now(clock),
            "block_type": "MISSING_INPUT",
            "reason": "PQX output payload is required; no fallback execution path is permitted.",
            "blocking_dependencies": [],
        }
        target_dir = runs_root / row.step_id
        block_path = _write_artifact(block_payload, "pqx_block_record", target_dir / f"{run_id}.block_record.json")

        row_state = _ensure_row_state(state, row.step_id)
        row_state["status"] = "blocked"
        row_state["last_run"] = iso_now(clock)
        row_state["retries"] += 1
        save_state(state, state_path)
        return {"status": "blocked", "block_record": str(block_path)}

    row_state = _ensure_row_state(state, row.step_id)
    row_state["status"] = "running"
    row_state["last_run"] = iso_now(clock)

    target_dir = runs_root / row.step_id
    request_payload = {
        "schema_version": "1.1.0",
        "run_id": run_id,
        "step_id": row.step_id,
        "step_name": row.step_name,
        "dependencies": list(row.dependencies),
        "requested_at": iso_now(clock),
        "prompt": f"Implement roadmap step {row.step_id}: {row.step_name}",
        "roadmap_version": authority.execution_roadmap_ref,
        "row_snapshot": {
            "row_index": row.row_index,
            "step_id": row.step_id,
            "step_name": row.step_name,
            "dependencies": list(row.dependencies),
            "status": row.status,
        },
    }
    request_path = _write_artifact(request_payload, "pqx_execution_request", target_dir / f"{run_id}.request.json")

    result_payload = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "step_id": row.step_id,
        "execution_status": "success",
        "started_at": row_state["last_run"],
        "completed_at": iso_now(clock),
        "output_text": pqx_output_text,
        "error": None,
    }
    result_path = _write_artifact(result_payload, "pqx_execution_result", target_dir / f"{run_id}.result.json")

    try:
        request_ref = str(request_path.relative_to(REPO_ROOT))
        result_ref = str(result_path.relative_to(REPO_ROOT))
    except ValueError:
        request_ref = str(request_path)
        result_ref = str(result_path)

    summary_payload = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "step_id": row.step_id,
        "final_status": "complete",
        "request_artifact_path": request_ref,
        "result_artifact_path": result_ref,
        "block_artifact_path": None,
        "generated_at": iso_now(clock),
    }
    summary_path = _write_artifact(summary_payload, "pqx_execution_summary", target_dir / f"{run_id}.summary.json")

    row_state["status"] = "complete"
    row_state["last_run"] = result_payload["completed_at"]
    row_state["dependencies_satisfied"] = True
    save_state(state, state_path)

    return {
        "status": "complete",
        "request": str(request_path),
        "result": str(result_path),
        "summary": str(summary_path),
    }
