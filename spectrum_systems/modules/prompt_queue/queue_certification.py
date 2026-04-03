"""Deterministic fail-closed prompt queue certification gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_observability_snapshot,
    validate_queue_state,
    validate_replay_record,
    validate_resume_checkpoint,
)
from spectrum_systems.modules.prompt_queue.queue_manifest_validator import validate_queue_manifest


class QueueCertificationError(ValueError):
    """Raised when queue certification input refs are malformed or insufficient."""


_REQUIRED_INPUT_REFS = (
    "manifest_ref",
    "final_queue_state_ref",
    "observability_ref",
)


def _read_json_object(path_value: str, *, label: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def _validate_output_schema(instance: dict[str, Any]) -> None:
    schema = load_schema("prompt_queue_certification_record")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: str(e.path))
    if errors:
        raise QueueCertificationError("; ".join(error.message for error in errors))


def _parse_input_refs(input_refs: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(input_refs, dict):
        raise QueueCertificationError("input_refs must be an object")

    refs: dict[str, Any] = {}
    for key in _REQUIRED_INPUT_REFS:
        value = input_refs.get(key)
        if not isinstance(value, str) or not value.strip():
            raise QueueCertificationError(f"missing required input ref: {key}")
        refs[key] = value

    replay_refs = input_refs.get("replay_checkpoint_refs")
    if replay_refs is None:
        refs["replay_checkpoint_refs"] = []
    elif isinstance(replay_refs, list) and all(isinstance(item, str) and item.strip() for item in replay_refs):
        refs["replay_checkpoint_refs"] = replay_refs
    else:
        raise QueueCertificationError("replay_checkpoint_refs must be an array of non-empty strings")

    replay_record_ref = input_refs.get("replay_record_ref")
    if replay_record_ref is not None:
        if not isinstance(replay_record_ref, str) or not replay_record_ref.strip():
            raise QueueCertificationError("replay_record_ref must be a non-empty string when provided")
        refs["replay_record_ref"] = replay_record_ref

    return refs


def _push_reason(checks: dict[str, dict[str, Any]], check_name: str, reason: str, *, blocking_reasons: list[str]) -> None:
    checks[check_name]["passed"] = False
    checks[check_name]["details"].append(reason)
    if reason not in blocking_reasons:
        blocking_reasons.append(reason)


def _stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_queue_certification(input_refs: dict) -> dict:
    """Run deterministic fail-closed queue certification and return certification artifact."""
    refs = _parse_input_refs(input_refs)

    checks = {
        "queue_completion": {"passed": True, "details": []},
        "state_integrity": {"passed": True, "details": []},
        "replay_integrity": {"passed": True, "details": []},
        "observability_integrity": {"passed": True, "details": []},
        "artifact_completeness": {"passed": True, "details": []},
    }
    blocking_reasons: list[str] = []

    manifest: dict[str, Any] | None = None
    final_state: dict[str, Any] | None = None
    observability: dict[str, Any] | None = None
    replay_record: dict[str, Any] | None = None

    try:
        manifest = _read_json_object(refs["manifest_ref"], label="manifest")
        validate_queue_manifest(manifest)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        _push_reason(
            checks,
            "artifact_completeness",
            f"missing_or_invalid_manifest:{exc}",
            blocking_reasons=blocking_reasons,
        )

    try:
        final_state = _read_json_object(refs["final_queue_state_ref"], label="final_queue_state")
        validate_queue_state(final_state)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, ArtifactValidationError) as exc:
        _push_reason(
            checks,
            "artifact_completeness",
            f"missing_or_invalid_final_queue_state:{exc}",
            blocking_reasons=blocking_reasons,
        )

    try:
        observability = _read_json_object(refs["observability_ref"], label="observability")
        validate_observability_snapshot(observability)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, ArtifactValidationError) as exc:
        _push_reason(
            checks,
            "artifact_completeness",
            f"missing_or_invalid_observability:{exc}",
            blocking_reasons=blocking_reasons,
        )

    checkpoint_refs = refs.get("replay_checkpoint_refs", [])
    if not checkpoint_refs:
        _push_reason(
            checks,
            "artifact_completeness",
            "missing_required_replay_checkpoint_refs",
            blocking_reasons=blocking_reasons,
        )

    checkpoint_payloads: list[dict[str, Any]] = []
    for checkpoint_ref in checkpoint_refs:
        try:
            checkpoint_payload = _read_json_object(checkpoint_ref, label="replay_checkpoint")
            validate_resume_checkpoint(checkpoint_payload)
            checkpoint_payloads.append(checkpoint_payload)
        except (FileNotFoundError, json.JSONDecodeError, ValueError, ArtifactValidationError) as exc:
            _push_reason(
                checks,
                "artifact_completeness",
                f"missing_or_invalid_replay_checkpoint:{checkpoint_ref}:{exc}",
                blocking_reasons=blocking_reasons,
            )

    replay_record_ref = refs.get("replay_record_ref")
    if replay_record_ref:
        try:
            replay_record = _read_json_object(replay_record_ref, label="replay_record")
            validate_replay_record(replay_record)
        except (FileNotFoundError, json.JSONDecodeError, ValueError, ArtifactValidationError) as exc:
            _push_reason(
                checks,
                "artifact_completeness",
                f"missing_or_invalid_replay_record:{exc}",
                blocking_reasons=blocking_reasons,
            )
    else:
        _push_reason(
            checks,
            "artifact_completeness",
            "missing_required_replay_record_ref",
            blocking_reasons=blocking_reasons,
        )

    queue_id = "unknown"
    trace_id = "unknown-trace"
    timestamp = "1970-01-01T00:00:00Z"

    if manifest is not None:
        queue_id = str(manifest.get("queue_id") or queue_id)
        trace_candidate = (manifest.get("execution_policy") or {}).get("trace_id")
        if isinstance(trace_candidate, str) and trace_candidate:
            trace_id = trace_candidate

    if final_state is not None:
        queue_id = str(final_state.get("queue_id") or queue_id)
        timestamp = str(final_state.get("updated_at") or final_state.get("last_updated") or timestamp)

        if final_state.get("queue_status") != "completed":
            _push_reason(
                checks,
                "queue_completion",
                "queue_not_completed",
                blocking_reasons=blocking_reasons,
            )

        if int(final_state.get("current_step_index", -1)) != int(final_state.get("total_steps", -2)):
            _push_reason(
                checks,
                "queue_completion",
                "incomplete_step_progression",
                blocking_reasons=blocking_reasons,
            )

        if final_state.get("active_work_item_id") not in {None, ""}:
            _push_reason(
                checks,
                "queue_completion",
                "active_work_item_present_at_completion",
                blocking_reasons=blocking_reasons,
            )

        step_results = final_state.get("step_results")
        if not isinstance(step_results, list) or not step_results:
            _push_reason(
                checks,
                "state_integrity",
                "missing_step_results",
                blocking_reasons=blocking_reasons,
            )

    if manifest is not None and final_state is not None:
        if manifest.get("queue_id") != final_state.get("queue_id"):
            _push_reason(
                checks,
                "state_integrity",
                "manifest_queue_id_mismatch",
                blocking_reasons=blocking_reasons,
            )

    if observability is not None and final_state is not None:
        metrics = observability.get("health_metrics") or {}
        if metrics.get("queue_id") != final_state.get("queue_id"):
            _push_reason(
                checks,
                "observability_integrity",
                "observability_queue_id_mismatch",
                blocking_reasons=blocking_reasons,
            )
        if metrics.get("queue_status") != final_state.get("queue_status"):
            _push_reason(
                checks,
                "observability_integrity",
                "observability_queue_status_mismatch",
                blocking_reasons=blocking_reasons,
            )
        if final_state.get("queue_status") == "completed" and float(metrics.get("completion_progress", -1.0)) != 1.0:
            _push_reason(
                checks,
                "observability_integrity",
                "observability_completion_progress_mismatch",
                blocking_reasons=blocking_reasons,
            )

    if observability is not None:
        trace_linkage = observability.get("trace_linkage") or {}
        linkage_id = trace_linkage.get("linkage_id")
        if not isinstance(linkage_id, str) or not linkage_id:
            _push_reason(
                checks,
                "state_integrity",
                "missing_observability_trace_linkage",
                blocking_reasons=blocking_reasons,
            )

    if checkpoint_payloads:
        for checkpoint in checkpoint_payloads:
            if queue_id != "unknown" and checkpoint.get("queue_id") != queue_id:
                _push_reason(
                    checks,
                    "replay_integrity",
                    "checkpoint_queue_id_mismatch",
                    blocking_reasons=blocking_reasons,
                )
            if manifest is not None and checkpoint.get("manifest_ref") != refs["manifest_ref"]:
                _push_reason(
                    checks,
                    "replay_integrity",
                    "checkpoint_manifest_ref_mismatch",
                    blocking_reasons=blocking_reasons,
                )
            if final_state is not None and checkpoint.get("queue_state_ref") != refs["final_queue_state_ref"]:
                _push_reason(
                    checks,
                    "replay_integrity",
                    "checkpoint_queue_state_ref_mismatch",
                    blocking_reasons=blocking_reasons,
                )
            checkpoint_trace_id = checkpoint.get("trace_id")
            if not isinstance(checkpoint_trace_id, str) or not checkpoint_trace_id:
                _push_reason(
                    checks,
                    "state_integrity",
                    "missing_checkpoint_trace_id",
                    blocking_reasons=blocking_reasons,
                )
            elif trace_id != "unknown-trace" and checkpoint_trace_id != trace_id:
                _push_reason(
                    checks,
                    "state_integrity",
                    "trace_id_continuity_mismatch",
                    blocking_reasons=blocking_reasons,
                )

    if replay_record is not None:
        if replay_record.get("parity_status") != "match":
            _push_reason(
                checks,
                "replay_integrity",
                "replay_parity_mismatch",
                blocking_reasons=blocking_reasons,
            )
        if queue_id != "unknown" and replay_record.get("queue_id") != queue_id:
            _push_reason(
                checks,
                "replay_integrity",
                "replay_queue_id_mismatch",
                blocking_reasons=blocking_reasons,
            )
        replay_trace_id = replay_record.get("trace_id")
        if not isinstance(replay_trace_id, str) or not replay_trace_id:
            _push_reason(
                checks,
                "state_integrity",
                "missing_replay_trace_id",
                blocking_reasons=blocking_reasons,
            )
        elif trace_id != "unknown-trace" and replay_trace_id != trace_id:
            _push_reason(
                checks,
                "state_integrity",
                "replay_trace_id_continuity_mismatch",
                blocking_reasons=blocking_reasons,
            )
        replay_summary = replay_record.get("replay_result_summary")
        if not isinstance(replay_summary, dict):
            _push_reason(
                checks,
                "replay_integrity",
                "missing_replay_result_summary",
                blocking_reasons=blocking_reasons,
            )
        else:
            for field, reason in (
                ("termination_reason_match", "replay_termination_reason_mismatch"),
                ("decision_sequence_match", "replay_decision_sequence_mismatch"),
                ("final_outcome_match", "replay_final_outcome_mismatch"),
            ):
                value = replay_summary.get(field)
                if value is not True:
                    _push_reason(
                        checks,
                        "replay_integrity",
                        reason,
                        blocking_reasons=blocking_reasons,
                    )

    certification_status = "passed" if not blocking_reasons else "failed"
    system_response = "allow" if certification_status == "passed" else "block"

    deterministic_context = {
        "queue_id": queue_id,
        "manifest_ref": refs["manifest_ref"],
        "final_queue_state_ref": refs["final_queue_state_ref"],
        "observability_ref": refs["observability_ref"],
        "replay_checkpoint_refs": checkpoint_refs,
        "replay_record_ref": replay_record_ref,
        "certification_status": certification_status,
        "blocking_reasons": blocking_reasons,
    }

    artifact = {
        "certification_id": _stable_hash(deterministic_context),
        "queue_id": queue_id,
        "manifest_ref": refs["manifest_ref"],
        "final_queue_state_ref": refs["final_queue_state_ref"],
        "replay_checkpoint_refs": checkpoint_refs,
        "observability_ref": refs["observability_ref"],
        "certification_status": certification_status,
        "system_response": system_response,
        "check_results": checks,
        "blocking_reasons": blocking_reasons,
        "trace_id": trace_id,
        "timestamp": timestamp,
    }
    _validate_output_schema(artifact)
    return artifact
