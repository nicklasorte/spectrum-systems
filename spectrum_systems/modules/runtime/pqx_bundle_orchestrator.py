"""Repo-native deterministic PQX bundle execution orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.pqx_backbone import (
    LEGACY_EXECUTION_ROADMAP_PATH,
    REPO_ROOT,
    RoadmapRow,
    parse_system_roadmap,
)
from spectrum_systems.modules.runtime.pqx_bundle_state import (
    PQXBundleStateError,
    block_step,
    initialize_bundle_state,
    load_bundle_state,
    mark_bundle_complete,
    mark_step_complete,
    save_bundle_state,
)
from spectrum_systems.modules.runtime.pqx_sequence_runner import execute_sequence_run
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now


BUNDLE_PLAN_PATH = REPO_ROOT / "docs" / "roadmaps" / "execution_bundles.md"


class PQXBundleOrchestratorError(ValueError):
    """Raised when bundle orchestration fails closed."""


@dataclass(frozen=True)
class BundleDefinition:
    bundle_id: str
    ordered_step_ids: tuple[str, ...]
    depends_on: tuple[str, ...]


def _parse_table(lines: list[str], start_index: int) -> tuple[list[str], list[list[str]]]:
    header_line = lines[start_index].strip()
    divider_line = lines[start_index + 1].strip() if start_index + 1 < len(lines) else ""
    if not header_line.startswith("|") or "---" not in divider_line:
        raise PQXBundleOrchestratorError("executable bundle table header is malformed")

    headers = [cell.strip() for cell in header_line.split("|")[1:-1]]
    rows: list[list[str]] = []
    for raw in lines[start_index + 2 :]:
        line = raw.strip()
        if not line:
            break
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.split("|")[1:-1]])
    if not rows:
        raise PQXBundleOrchestratorError("executable bundle table contains no rows")
    return headers, rows


def load_bundle_plan(bundle_plan_path: str | Path = BUNDLE_PLAN_PATH) -> list[BundleDefinition]:
    plan_path = Path(bundle_plan_path)
    if not plan_path.is_file():
        raise PQXBundleOrchestratorError(f"bundle plan file not found: {plan_path}")

    lines = plan_path.read_text(encoding="utf-8").splitlines()
    section_indexes = [i for i, line in enumerate(lines) if line.strip() == "## EXECUTABLE BUNDLE TABLE"]
    if len(section_indexes) != 1:
        raise PQXBundleOrchestratorError("bundle plan must contain exactly one '## EXECUTABLE BUNDLE TABLE' section")

    table_start = section_indexes[0] + 1
    while table_start < len(lines) and not lines[table_start].strip():
        table_start += 1
    headers, rows = _parse_table(lines, table_start)
    expected = ["Bundle ID", "Ordered Step IDs", "Depends On"]
    if headers[:3] != expected:
        raise PQXBundleOrchestratorError("executable bundle table headers are malformed or ambiguous")

    bundles: list[BundleDefinition] = []
    seen_ids: set[str] = set()
    for row in rows:
        if len(row) < 3:
            raise PQXBundleOrchestratorError("bundle table row is malformed")
        bundle_id = row[0].strip()
        ordered_step_ids = tuple(step.strip() for step in row[1].split(",") if step.strip())
        depends_on = tuple(dep.strip() for dep in row[2].split(",") if dep.strip() and dep.strip() not in {"-", "—"})
        if not bundle_id or not ordered_step_ids:
            raise PQXBundleOrchestratorError("bundle table row missing required bundle_id or ordered_step_ids")
        if bundle_id in seen_ids:
            raise PQXBundleOrchestratorError(f"duplicate bundle_id in executable bundle table: {bundle_id}")
        seen_ids.add(bundle_id)
        bundles.append(BundleDefinition(bundle_id=bundle_id, ordered_step_ids=ordered_step_ids, depends_on=depends_on))

    return bundles


def resolve_bundle_definition(bundle_plan: list[BundleDefinition], bundle_id: str) -> BundleDefinition:
    for definition in bundle_plan:
        if definition.bundle_id == bundle_id:
            return definition
    raise PQXBundleOrchestratorError(f"bundle_id not found in executable bundle table: {bundle_id}")


def validate_bundle_definition(bundle_definition: BundleDefinition, roadmap_rows: list[RoadmapRow]) -> None:
    if not bundle_definition.ordered_step_ids:
        raise PQXBundleOrchestratorError("bundle must declare a non-empty ordered_step_ids list")

    if len(set(bundle_definition.ordered_step_ids)) != len(bundle_definition.ordered_step_ids):
        raise PQXBundleOrchestratorError("bundle contains duplicate step IDs")

    row_by_id = {row.step_id: row for row in roadmap_rows}
    unknown = [step_id for step_id in bundle_definition.ordered_step_ids if step_id not in row_by_id]
    if unknown:
        raise PQXBundleOrchestratorError(f"bundle references unknown roadmap step IDs: {unknown}")

    position = {step_id: index for index, step_id in enumerate(bundle_definition.ordered_step_ids)}
    for step_id in bundle_definition.ordered_step_ids:
        row = row_by_id[step_id]
        for dependency in row.dependencies:
            if dependency not in position:
                raise PQXBundleOrchestratorError(
                    f"bundle dependency violation: step '{step_id}' requires roadmap dependency '{dependency}'"
                )
            if position[dependency] >= position[step_id]:
                raise PQXBundleOrchestratorError(
                    f"bundle dependency ordering violation: '{dependency}' must precede '{step_id}'"
                )


StepExecutor = Callable[[dict], dict]


def _to_bundle_plan(definition: BundleDefinition) -> list[dict]:
    return [
        {
            "bundle_id": definition.bundle_id,
            "step_ids": list(definition.ordered_step_ids),
            "depends_on": list(definition.depends_on),
        }
    ]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def execute_bundle_run(
    *,
    bundle_id: str,
    bundle_state_path: str | Path,
    output_dir: str | Path,
    run_id: str,
    sequence_run_id: str,
    trace_id: str,
    bundle_plan_path: str | Path = BUNDLE_PLAN_PATH,
    roadmap_authority_ref: str = "docs/roadmaps/system_roadmap.md",
    roadmap_path: str | Path = LEGACY_EXECUTION_ROADMAP_PATH,
    execute_step: StepExecutor | None = None,
    clock=utc_now,
) -> dict:
    bundle_plan = load_bundle_plan(bundle_plan_path)
    definition = resolve_bundle_definition(bundle_plan, bundle_id)
    roadmap_rows = parse_system_roadmap(Path(roadmap_path))
    validate_bundle_definition(definition, roadmap_rows)

    state_path = Path(bundle_state_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    step_state_dir = output_root / "sequence_step_states"
    step_state_dir.mkdir(parents=True, exist_ok=True)

    normalized_bundle_plan = _to_bundle_plan(definition)
    plan_ref = _relative(Path(bundle_plan_path))
    now = iso_now(clock)
    if state_path.exists():
        bundle_state = load_bundle_state(state_path, bundle_plan=normalized_bundle_plan)
        if bundle_state["roadmap_authority_ref"] != roadmap_authority_ref:
            raise PQXBundleOrchestratorError("resume blocked: roadmap_authority_ref mismatch")
        if bundle_state["execution_plan_ref"] != plan_ref:
            raise PQXBundleOrchestratorError("resume blocked: execution_plan_ref mismatch")
        if bundle_state["run_id"] != run_id or bundle_state["sequence_run_id"] != sequence_run_id:
            raise PQXBundleOrchestratorError("resume blocked: run_id/sequence_run_id mismatch")
    else:
        try:
            bundle_state = initialize_bundle_state(
                bundle_plan=normalized_bundle_plan,
                run_id=run_id,
                sequence_run_id=sequence_run_id,
                roadmap_authority_ref=roadmap_authority_ref,
                execution_plan_ref=plan_ref,
                now=now,
            )
            bundle_state = save_bundle_state(bundle_state, state_path, bundle_plan=normalized_bundle_plan)
        except PQXBundleStateError as exc:
            raise PQXBundleOrchestratorError(str(exc)) from exc

    if bundle_id in bundle_state.get("completed_bundle_ids", []):
        raise PQXBundleOrchestratorError(f"bundle already completed: {bundle_id}")

    completed = bundle_state["completed_step_ids"]
    expected_prefix = list(definition.ordered_step_ids[: len(completed)])
    if completed != expected_prefix:
        raise PQXBundleOrchestratorError("resume blocked: completed_step_ids are inconsistent with bundle step order")

    executor = execute_step or (lambda payload: {"execution_status": "success", **payload})
    executed_steps: list[dict] = []
    status = "completed"
    blocked_step_id: str | None = None
    failure_classification: str | None = None

    for step_id in definition.ordered_step_ids:
        if step_id in bundle_state["completed_step_ids"]:
            continue

        step_state_path = step_state_dir / f"{step_id}.json"
        result_state = execute_sequence_run(
            slice_requests=[{"slice_id": step_id, "trace_id": f"{trace_id}:{step_id}"}],
            state_path=step_state_path,
            queue_run_id=sequence_run_id,
            run_id=run_id,
            trace_id=f"{trace_id}:{step_id}",
            execute_slice=executor,
            resume=step_state_path.exists(),
            max_slices=1,
            clock=clock,
        )

        history_record = result_state["execution_history"][-1]
        artifact_ref = _relative(step_state_path)
        if result_state["status"] == "failed":
            status = "blocked"
            blocked_step_id = step_id
            failure_classification = "STEP_EXECUTION_FAILED"
            try:
                bundle_state = block_step(bundle_state, normalized_bundle_plan, step_id=step_id, now=iso_now(clock))
                bundle_state = save_bundle_state(bundle_state, state_path, bundle_plan=normalized_bundle_plan)
            except PQXBundleStateError as exc:
                raise PQXBundleOrchestratorError(str(exc)) from exc
            executed_steps.append(
                {
                    "step_id": step_id,
                    "status": "failed",
                    "artifact_refs": [artifact_ref],
                    "error": history_record.get("error"),
                }
            )
            break

        try:
            bundle_state = mark_step_complete(
                bundle_state,
                normalized_bundle_plan,
                step_id=step_id,
                artifact_refs=[artifact_ref],
                now=iso_now(clock),
            )
            bundle_state = save_bundle_state(bundle_state, state_path, bundle_plan=normalized_bundle_plan)
        except PQXBundleStateError as exc:
            raise PQXBundleOrchestratorError(str(exc)) from exc

        executed_steps.append({"step_id": step_id, "status": "success", "artifact_refs": [artifact_ref], "error": None})

    if status == "completed":
        try:
            bundle_state = mark_bundle_complete(
                bundle_state,
                normalized_bundle_plan,
                bundle_id=bundle_id,
                now=iso_now(clock),
            )
            bundle_state = save_bundle_state(bundle_state, state_path, bundle_plan=normalized_bundle_plan)
        except PQXBundleStateError as exc:
            raise PQXBundleOrchestratorError(str(exc)) from exc

    record = {
        "schema_version": "1.0.0",
        "bundle_execution_id": f"bundle-exec:{sequence_run_id}:{bundle_id}:{len(bundle_state['completed_step_ids'])}",
        "bundle_id": bundle_id,
        "roadmap_authority_ref": roadmap_authority_ref,
        "bundle_plan_ref": plan_ref,
        "run_id": run_id,
        "trace_id": trace_id,
        "started_at": now,
        "completed_at": iso_now(clock) if status == "completed" else None,
        "blocked_at": iso_now(clock) if status == "blocked" else None,
        "status": status,
        "executed_steps": executed_steps,
        "blocked_step_id": blocked_step_id,
        "output_artifact_refs": [ref for step in executed_steps for ref in step["artifact_refs"]],
        "review_artifact_refs": [],
        "state_artifact_ref": _relative(state_path),
        "failure_classification": failure_classification,
        "resume_position": bundle_state["resume_position"],
    }
    try:
        validate_artifact(record, "pqx_bundle_execution_record")
    except Exception as exc:
        raise PQXBundleOrchestratorError(f"invalid pqx_bundle_execution_record artifact: {exc}") from exc

    record_path = output_root / f"{bundle_id}.bundle_execution_record.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    return {
        "status": status,
        "bundle_execution_record": _relative(record_path),
        "bundle_state": _relative(state_path),
    }
