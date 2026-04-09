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
    assert_valid_advancement,
    block_step,
    initialize_bundle_state,
    load_bundle_state,
    mark_bundle_complete,
    mark_step_complete,
    save_bundle_state,
)
from spectrum_systems.modules.runtime.pqx_fix_execution import (
    PQXFixExecutionError,
    determine_fix_insertion_point,
    execute_fix_step,
    load_pending_fixes,
    normalize_fix_into_step,
    record_fix_result,
    update_bundle_state_with_fix,
    validate_fix_step,
)
from spectrum_systems.modules.runtime.pqx_fix_gate import (
    PQXFixGateError,
    assert_fix_gate_allows_resume,
    evaluate_fix_completion,
)
from spectrum_systems.modules.runtime.pqx_triage_planner import (
    PQXTriagePlannerError,
    build_triage_plan_record,
)
from spectrum_systems.modules.runtime.pqx_sequence_runner import execute_sequence_run
from spectrum_systems.modules.runtime.pqx_slice_runner import (
    confirm_slice_completion_after_enforcement_allow,
    run_pqx_slice,
)
from spectrum_systems.modules.runtime.pqx_judgment import build_pqx_judgment_record
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now


BUNDLE_PLAN_PATH = REPO_ROOT / "docs" / "roadmaps" / "execution_bundles.md"


class PQXBundleOrchestratorError(ValueError):
    """Raised when bundle orchestration fails closed."""


@dataclass(frozen=True)
class BundleDefinition:
    bundle_id: str
    ordered_step_ids: tuple[str, ...]
    depends_on: tuple[str, ...]


@dataclass(frozen=True)
class ReviewRequirement:
    checkpoint_id: str
    bundle_id: str
    review_type: str
    scope: str
    step_id: str | None
    required: bool
    blocking_review_before_continue: bool


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


def _parse_optional_review_requirements(lines: list[str]) -> list[ReviewRequirement]:
    section_indexes = [i for i, line in enumerate(lines) if line.strip() == "## REVIEW CHECKPOINT TABLE"]
    if not section_indexes:
        return []
    if len(section_indexes) != 1:
        raise PQXBundleOrchestratorError("bundle plan must contain at most one '## REVIEW CHECKPOINT TABLE' section")

    table_start = section_indexes[0] + 1
    while table_start < len(lines) and not lines[table_start].strip():
        table_start += 1
    headers, rows = _parse_table(lines, table_start)
    expected = [
        "Checkpoint ID",
        "Bundle ID",
        "Review Type",
        "Scope",
        "Step ID",
        "Required",
        "Blocking Before Continue",
    ]
    if headers[:7] != expected:
        raise PQXBundleOrchestratorError("review checkpoint table headers are malformed or ambiguous")

    parsed: list[ReviewRequirement] = []
    seen: set[str] = set()
    for row in rows:
        checkpoint_id, bundle_id, review_type, scope, step_id, required, blocking = row[:7]
        if checkpoint_id in seen:
            raise PQXBundleOrchestratorError(f"duplicate checkpoint_id in review checkpoint table: {checkpoint_id}")
        seen.add(checkpoint_id)
        parsed.append(
            ReviewRequirement(
                checkpoint_id=checkpoint_id,
                bundle_id=bundle_id,
                review_type=review_type,
                scope=scope,
                step_id=None if step_id in {"-", "—", ""} else step_id,
                required=required.lower() == "true",
                blocking_review_before_continue=blocking.lower() == "true",
            )
        )
    return parsed


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


def load_review_requirements(
    bundle_plan_path: str | Path,
    *,
    bundle_id: str,
    ordered_step_ids: tuple[str, ...],
) -> list[dict]:
    lines = Path(bundle_plan_path).read_text(encoding="utf-8").splitlines()
    all_requirements = _parse_optional_review_requirements(lines)
    requirements = [r for r in all_requirements if r.bundle_id == bundle_id and r.required]
    step_ids = set(ordered_step_ids)
    normalized: list[dict] = []
    for req in requirements:
        if req.scope == "step" and req.step_id not in step_ids:
            raise PQXBundleOrchestratorError(
                f"review checkpoint '{req.checkpoint_id}' references step not in bundle: {req.step_id}"
            )
        normalized.append(
            {
                "checkpoint_id": req.checkpoint_id,
                "bundle_id": req.bundle_id,
                "review_type": req.review_type,
                "scope": req.scope,
                "step_id": req.step_id,
                "required": req.required,
                "blocking_review_before_continue": req.blocking_review_before_continue,
            }
        )
    return normalized


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


def select_next_runnable_bundle(
    *,
    bundle_plan: list[BundleDefinition],
    bundle_states: dict[str, dict],
    run_id: str,
    trace_id: str,
    now: str,
) -> dict:
    """Deterministically choose exactly one runnable bundle or fail closed with explicit block."""

    plan_ids = [definition.bundle_id for definition in bundle_plan]
    completed = {
        bundle_id
        for bundle_id, state in bundle_states.items()
        if isinstance(state, dict) and state.get("status") == "completed"
    }
    runnable: list[BundleDefinition] = []
    blocked_reasons: list[dict] = []

    for definition in bundle_plan:
        state = bundle_states.get(definition.bundle_id, {})
        status = state.get("status", "pending")
        unresolved_findings = bool(state.get("unresolved_findings", []))
        pending_fixes = bool(state.get("pending_fix_ids", []))
        readiness_approved = bool(state.get("readiness_approved", False))
        failed_or_blocked = status in {"failed", "blocked"}
        canary_status = state.get("canary_status", "not_applicable")

        unmet_deps = [dep for dep in definition.depends_on if dep not in completed and dep in plan_ids]
        if unmet_deps:
            blocked_reasons.append(
                {
                    "bundle_id": definition.bundle_id,
                    "block_type": "DEPENDENCY_UNSATISFIED",
                    "reason": f"bundle dependencies incomplete: {unmet_deps}",
                }
            )
            continue
        if status == "completed":
            continue
        if not readiness_approved:
            blocked_reasons.append(
                {
                    "bundle_id": definition.bundle_id,
                    "block_type": "READINESS_UNAPPROVED",
                    "reason": "bundle readiness gate is not approved",
                }
            )
            continue
        if unresolved_findings or pending_fixes:
            blocked_reasons.append(
                {
                    "bundle_id": definition.bundle_id,
                    "block_type": "GOVERNANCE_BLOCKED",
                    "reason": "bundle has unresolved findings or pending fixes",
                }
            )
            continue
        if canary_status == "frozen":
            blocked_reasons.append(
                {
                    "bundle_id": definition.bundle_id,
                    "block_type": "CANARY_FROZEN",
                    "reason": "canary evaluation froze this scheduling path",
                }
            )
            continue
        if failed_or_blocked and not state.get("resume_ready", False):
            blocked_reasons.append(
                {
                    "bundle_id": definition.bundle_id,
                    "block_type": "RESUME_NOT_ALLOWED",
                    "reason": "prior blocked/failed bundle is not resume-approved",
                }
            )
            continue
        runnable.append(definition)

    if not runnable:
        decision = {
            "schema_version": "1.0.0",
            "decision_id": f"schedule:{run_id}:{trace_id}:none",
            "outcome": "blocked",
            "selected_bundle_id": None,
            "block_type": "NO_RUNNABLE_BUNDLE",
            "reasons": ["no bundle satisfied dependency + readiness + governance prerequisites"],
            "candidate_bundle_ids": plan_ids,
            "blocked_candidates": blocked_reasons,
            "run_id": run_id,
            "trace_id": trace_id,
            "created_at": now,
        }
        validate_artifact(decision, "pqx_bundle_schedule_decision")
        return decision

    if len(runnable) > 1:
        top = sorted(runnable, key=lambda b: b.bundle_id)
        tied = [bundle.bundle_id for bundle in top]
        decision = {
            "schema_version": "1.0.0",
            "decision_id": f"schedule:{run_id}:{trace_id}:ambiguous",
            "outcome": "blocked",
            "selected_bundle_id": None,
            "block_type": "AMBIGUOUS_RUNNABLE_BUNDLE",
            "reasons": ["multiple runnable bundles exist and deterministic tie-break is undefined"],
            "candidate_bundle_ids": plan_ids,
            "blocked_candidates": blocked_reasons,
            "ambiguous_bundle_ids": tied,
            "run_id": run_id,
            "trace_id": trace_id,
            "created_at": now,
        }
        validate_artifact(decision, "pqx_bundle_schedule_decision")
        return decision

    selected = runnable[0]
    decision = {
        "schema_version": "1.0.0",
        "decision_id": f"schedule:{run_id}:{trace_id}:{selected.bundle_id}",
        "outcome": "selected",
        "selected_bundle_id": selected.bundle_id,
        "block_type": None,
        "reasons": ["dependency-valid", "readiness-approved", "governance-state-clear"],
        "candidate_bundle_ids": plan_ids,
        "blocked_candidates": blocked_reasons,
        "ambiguous_bundle_ids": [],
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": now,
    }
    validate_artifact(decision, "pqx_bundle_schedule_decision")
    return decision


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


def _execute_pending_fix_loop(
    *,
    bundle_state: dict,
    definition: BundleDefinition,
    step_state_dir: Path,
    run_id: str,
    sequence_run_id: str,
    trace_id: str,
    clock,
) -> tuple[dict, list[dict], list[dict]]:
    pending_fixes = load_pending_fixes(bundle_state)
    if not pending_fixes:
        return bundle_state, [], []

    roadmap = list(definition.ordered_step_ids)
    fix_records: list[dict] = []
    fix_gate_records: list[dict] = []

    for fix in pending_fixes:
        fix_step = normalize_fix_into_step(fix)
        validate_fix_step(fix_step, roadmap)
        insertion_point = determine_fix_insertion_point(fix_step, roadmap)

        fix_step_id = fix_step["fix_step_id"]
        step_state_path = step_state_dir / f"{fix_step_id}.json"

        def _run_fix(payload: dict) -> dict:
            result_state = execute_sequence_run(
                slice_requests=[{"slice_id": payload["fix_step_id"], "trace_id": f"{trace_id}:{payload['fix_step_id']}"}],
                state_path=step_state_path,
                queue_run_id=f"{sequence_run_id}:fix",
                run_id=run_id,
                trace_id=f"{trace_id}:{payload['fix_step_id']}",
                execute_slice=lambda _: {"execution_status": "success"},
                resume=step_state_path.exists(),
                max_slices=1,
                enforce_dependency_admission=False,
                clock=clock,
            )
            history = result_state["execution_history"][-1]
            return {
                "execution_status": "complete" if history.get("status") == "success" else "failed",
                "artifacts": [_relative(step_state_path)],
                "validation_result": "passed" if history.get("status") == "success" else "failed",
                "error": history.get("error"),
            }

        execution_result = execute_fix_step(fix_step, _run_fix)
        execution_result["fix_step"]["trace_id"] = f"{trace_id}:{fix_step_id}"
        execution_result["fix_step"]["run_id"] = run_id
        record = record_fix_result(bundle_state, execution_result["fix_step"], execution_result)
        record["insertion_point"] = insertion_point
        fix_execution_record_path = step_state_dir / f"{fix_step_id}.fix_execution_record.json"
        fix_execution_record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        bundle_state = update_bundle_state_with_fix(bundle_state, record)
        fix_records.append(record)

        fix_gate_path = step_state_dir / f"{fix_step_id}.fix_gate_record.json"
        bundle_state, gate_record = evaluate_fix_completion(
            bundle_state=bundle_state,
            fix_execution_record=record,
            fix_execution_record_ref=_relative(fix_execution_record_path),
            fix_gate_record_ref=_relative(fix_gate_path),
            now=iso_now(clock),
        )
        fix_gate_path.write_text(json.dumps(gate_record, indent=2) + "\n", encoding="utf-8")
        fix_gate_records.append(gate_record)

        if gate_record["gate_status"] != "passed":
            break
    return bundle_state, fix_records, fix_gate_records


def _load_json_artifact_refs(*, refs: list[str], repo_root: Path) -> list[dict]:
    artifacts: list[dict] = []
    for artifact_ref in refs:
        if not isinstance(artifact_ref, str) or not artifact_ref:
            raise PQXBundleOrchestratorError("triage planning requires non-empty artifact refs")
        path = Path(artifact_ref) if Path(artifact_ref).is_absolute() else (repo_root / artifact_ref)
        if not path.is_file():
            raise PQXBundleOrchestratorError(f"triage planning input artifact not found: {artifact_ref}")
        artifacts.append(json.loads(path.read_text(encoding="utf-8")))
    return artifacts


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
    execute_fixes: bool = False,
    emit_triage_plan: bool = False,
    triage_plan_on: tuple[str, ...] = ("review_findings", "fix_gate_blocked", "blocked_outstanding_findings"),
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
    review_requirements = load_review_requirements(
        bundle_plan_path,
        bundle_id=bundle_id,
        ordered_step_ids=definition.ordered_step_ids,
    )
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
                review_requirements=review_requirements,
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

    if execute_step is None:
        def _default_executor(payload: dict) -> dict:
            slice_id = str(payload.get("slice_id", ""))
            if slice_id.startswith("AI-"):
                canonical_step_id = slice_id
            elif slice_id == "PQX-QUEUE-01":
                canonical_step_id = "AI-01"
            elif slice_id == "PQX-QUEUE-02":
                canonical_step_id = "AI-02"
            else:
                canonical_step_id = "TRUST-01"
            slice_result = run_pqx_slice(
                step_id=canonical_step_id,
                roadmap_path=Path(roadmap_path),
                state_path=Path(bundle_state_path).parent / "pqx_state.json",
                runs_root=Path(output_dir) / "slice_runs",
                clock=clock,
                pqx_output_text=f"bundle deterministic output for {payload['slice_id']}",
                execution_intent="non_repo_write",
            )
            if slice_result.get("status") != "complete":
                return {"execution_status": "failed", "error": slice_result.get("reason") or slice_result.get("block_type", "blocked")}
            completion_confirmation = confirm_slice_completion_after_enforcement_allow(
                slice_result=slice_result,
                state_path=Path(bundle_state_path).parent / "pqx_state.json",
                step_id=canonical_step_id,
            )
            if completion_confirmation.get("status") != "complete":
                return {
                    "execution_status": "failed",
                    "error": completion_confirmation.get("reason")
                    or completion_confirmation.get("block_type", "post_enforcement_blocked"),
                }
            return {"execution_status": "success", **payload}
        executor = _default_executor
    else:
        executor = execute_step
    executed_steps: list[dict] = []
    executed_fix_records: list[dict] = []
    fix_gate_records: list[dict] = []
    persisted_fix_gate_refs: list[str] = []
    status = "completed"
    blocked_step_id: str | None = None
    failure_classification: str | None = None

    if execute_fixes and load_pending_fixes(bundle_state):
        try:
            bundle_state, executed_fix_records, fix_gate_records = _execute_pending_fix_loop(
                bundle_state=bundle_state,
                definition=definition,
                step_state_dir=step_state_dir,
                run_id=run_id,
                sequence_run_id=sequence_run_id,
                trace_id=trace_id,
                clock=clock,
            )
            if executed_fix_records:
                assert_fix_gate_allows_resume(bundle_state)
            bundle_state = save_bundle_state(bundle_state, state_path, bundle_plan=normalized_bundle_plan)
        except (PQXFixExecutionError, PQXFixGateError, PQXBundleStateError) as exc:
            raise PQXBundleOrchestratorError(str(exc)) from exc

        unresolved = [r["fix_id"] for r in fix_gate_records if r["gate_status"] != "passed"]
        if unresolved:
            status = "blocked"
            failure_classification = "FIX_GATE_BLOCKED"
            persisted_fix_gate_refs = [
                _relative(step_state_dir / f"fix-step:{record['fix_id']}.fix_gate_record.json") for record in fix_gate_records
            ]
        elif load_pending_fixes(bundle_state):
            status = "blocked"
            failure_classification = "BLOCKING_FIX_UNRESOLVED"

    if status != "blocked":
        for step_id in definition.ordered_step_ids:
            if step_id in bundle_state["completed_step_ids"]:
                continue

            try:
                assert_valid_advancement(bundle_state, normalized_bundle_plan, step_id=step_id)
            except PQXBundleStateError as exc:
                status = "blocked"
                blocked_step_id = step_id
                failure_classification = "REVIEW_REQUIRED" if "review checkpoint" in str(exc) else "BLOCKED"
                break

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
                enforce_dependency_admission=False,
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
            status = "blocked"
            failure_classification = "REVIEW_REQUIRED" if "review" in str(exc) else "BLOCKED"

    record = {
        "schema_version": "1.1.0",
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
        "review_artifact_refs": [entry["artifact_ref"] for entry in bundle_state["review_artifact_refs"]],
        "state_artifact_ref": _relative(state_path),
        "failure_classification": failure_classification,
        "block_reason": "required review unresolved" if failure_classification == "REVIEW_REQUIRED" else None,
        "resume_position": bundle_state["resume_position"],
    }
    try:
        validate_artifact(record, "pqx_bundle_execution_record")
    except Exception as exc:
        raise PQXBundleOrchestratorError(f"invalid pqx_bundle_execution_record artifact: {exc}") from exc

    record_path = output_root / f"{bundle_id}.bundle_execution_record.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    judgment_refs: list[str] = []
    if status == "blocked":
        judgment = build_pqx_judgment_record(
            record_id=f"judgment:{sequence_run_id}:{bundle_id}:blocked",
            decision_type="blocked_bundle_admission" if not executed_steps else "blocked_continuation",
            outcome="blocked",
            reasons=[record.get("failure_classification") or "bundle blocked", record.get("block_reason") or "governance gate blocked"],
            artifact_refs=[_relative(record_path), _relative(state_path)],
            bundle_id=bundle_id,
            slice_id=blocked_step_id,
            run_id=run_id,
            trace_id=trace_id,
            created_at=iso_now(clock),
            policy_refs=["docs/roadmaps/system_roadmap.md"],
        )
        judgment_path = output_root / f"{bundle_id}.judgment.blocked.json"
        judgment_path.write_text(json.dumps(judgment, indent=2) + "\n", encoding="utf-8")
        judgment_refs.append(_relative(judgment_path))
    elif status == "completed":
        judgment = build_pqx_judgment_record(
            record_id=f"judgment:{sequence_run_id}:{bundle_id}:resolved",
            decision_type="resolved_bundle_execution",
            outcome="resolved",
            reasons=["bundle completed with certification/audit evidence"],
            artifact_refs=[_relative(record_path), _relative(state_path)],
            bundle_id=bundle_id,
            slice_id=None,
            run_id=run_id,
            trace_id=trace_id,
            created_at=iso_now(clock),
            policy_refs=["docs/roadmaps/system_roadmap.md"],
        )
        judgment_path = output_root / f"{bundle_id}.judgment.resolved.json"
        judgment_path.write_text(json.dumps(judgment, indent=2) + "\n", encoding="utf-8")
        judgment_refs.append(_relative(judgment_path))

    triage_plan_record_ref: str | None = None
    if emit_triage_plan:
        should_emit = False
        pending_fixes = load_pending_fixes(bundle_state)
        has_review_findings = bool(bundle_state["review_artifact_refs"]) and bool(pending_fixes)
        has_fix_gate_block = failure_classification == "FIX_GATE_BLOCKED"
        has_blocked_outstanding = status == "blocked" and bool(bundle_state.get("unresolved_fixes"))

        if "review_findings" in triage_plan_on and has_review_findings:
            should_emit = True
        if "fix_gate_blocked" in triage_plan_on and has_fix_gate_block:
            should_emit = True
        if "blocked_outstanding_findings" in triage_plan_on and has_blocked_outstanding:
            should_emit = True

        if should_emit:
            try:
                review_refs = sorted({entry["artifact_ref"] for entry in bundle_state["review_artifact_refs"]})
                fix_refs = sorted(set(persisted_fix_gate_refs))
                reviews = _load_json_artifact_refs(refs=review_refs, repo_root=REPO_ROOT) if review_refs else []
                fixes = _load_json_artifact_refs(refs=fix_refs, repo_root=REPO_ROOT) if fix_refs else []
                triage_plan = build_triage_plan_record(
                    run_id=run_id,
                    trace_id=trace_id,
                    bundle_run_id=sequence_run_id,
                    bundle_id=bundle_id,
                    roadmap_authority_ref=roadmap_authority_ref,
                    review_artifacts=reviews,
                    review_artifact_refs=review_refs,
                    fix_gate_records=fixes,
                    fix_gate_record_refs=fix_refs,
                    step_ids=list(definition.ordered_step_ids),
                    created_at=iso_now(clock),
                )
            except (PQXTriagePlannerError, OSError, json.JSONDecodeError, KeyError) as exc:
                raise PQXBundleOrchestratorError(f"triage planning failed closed: {exc}") from exc

            triage_plan_path = output_root / f"{bundle_id}.triage_plan_record.json"
            triage_plan_path.write_text(json.dumps(triage_plan, indent=2) + "\n", encoding="utf-8")
            triage_plan_record_ref = _relative(triage_plan_path)

    return {
        "status": status,
        "failure_classification": failure_classification,
        "bundle_execution_record": _relative(record_path),
        "bundle_state": _relative(state_path),
        "triage_plan_record": triage_plan_record_ref,
        "judgment_record_refs": judgment_refs,
    }
