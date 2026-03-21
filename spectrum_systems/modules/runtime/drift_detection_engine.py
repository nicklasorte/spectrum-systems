"""Drift Detection Engine (BAH).

Compares replay outputs against approved baselines and emits a governed
``drift_detection_result`` artifact.

Design principles
-----------------
- Fail closed: missing inputs, schema violations, and comparison failures raise
  hard errors or produce an explicit ``indeterminate`` result.
- Deterministic: same inputs always produce the same output artifact.
- Schema-governed: validates replay/baseline inputs and the emitted result.
- Validator/runtime separation: validation helpers are pure and side-effect free.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_REPLAY_SCHEMA_PATH = _SCHEMA_DIR / "replay_result.schema.json"
_DRIFT_SCHEMA_PATH = _SCHEMA_DIR / "drift_detection_result.schema.json"

logger = logging.getLogger(__name__)

STATUS_NO_DRIFT = "no_drift"
STATUS_DRIFT_DETECTED = "drift_detected"
STATUS_INDETERMINATE = "indeterminate"


class DriftDetectionError(Exception):
    """Raised when drift detection cannot execute safely (fail-closed)."""


@dataclass(frozen=True)
class DriftConfig:
    """Configuration for deterministic drift comparison."""

    abs_tolerance: float = 0.0
    rel_tolerance: float = 0.0
    required_fields: tuple[str, ...] = ()


def _load_schema(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise DriftDetectionError(f"Schema file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(instance: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


def validate_replay_artifact(artifact: Dict[str, Any]) -> List[str]:
    """Validate replay/baseline input artifacts against replay_result schema."""
    return _validate(artifact, _load_schema(_REPLAY_SCHEMA_PATH))


def validate_drift_detection_result(artifact: Dict[str, Any]) -> List[str]:
    """Validate drift output artifact against drift_detection_result schema."""
    return _validate(artifact, _load_schema(_DRIFT_SCHEMA_PATH))


def _extract_required_field(artifact: Dict[str, Any], field: str) -> Any:
    if field not in artifact:
        raise DriftDetectionError(f"Missing required field '{field}' in replay artifact")
    return artifact[field]


def _extract_run_id(replay_artifact: Dict[str, Any]) -> str:
    context = replay_artifact.get("context")
    if not isinstance(context, dict):
        raise DriftDetectionError("replay_artifact.context must be an object")
    run_id = context.get("run_id")
    if not run_id or not isinstance(run_id, str):
        raise DriftDetectionError("replay_artifact.context.run_id must be a non-empty string")
    return run_id


def _to_config(config: Optional[Dict[str, Any]]) -> DriftConfig:
    if config is None:
        return DriftConfig()
    if not isinstance(config, dict):
        raise DriftDetectionError("config must be an object when provided")

    abs_tol = config.get("abs_tolerance", 0.0)
    rel_tol = config.get("rel_tolerance", 0.0)
    required_fields = config.get("required_fields", [])
    if required_fields is None:
        required_fields = []

    if not isinstance(abs_tol, (int, float)) or abs_tol < 0:
        raise DriftDetectionError("config.abs_tolerance must be a non-negative number")
    if not isinstance(rel_tol, (int, float)) or rel_tol < 0:
        raise DriftDetectionError("config.rel_tolerance must be a non-negative number")
    if not isinstance(required_fields, list):
        raise DriftDetectionError("config.required_fields must be a list of field paths")
    if any((not isinstance(x, str) or not x) for x in required_fields):
        raise DriftDetectionError("config.required_fields entries must be non-empty strings")

    return DriftConfig(
        abs_tolerance=float(abs_tol),
        rel_tolerance=float(rel_tol),
        required_fields=tuple(required_fields),
    )


def _flatten_paths(value: Any, prefix: str = "") -> Dict[str, Any]:
    paths: Dict[str, Any] = {}
    if isinstance(value, dict):
        for key in sorted(value.keys()):
            child = f"{prefix}.{key}" if prefix else key
            paths.update(_flatten_paths(value[key], child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            child = f"{prefix}[{idx}]"
            paths.update(_flatten_paths(item, child))
    else:
        paths[prefix] = value
    return paths


def _compare_structures(
    replay_flat: Dict[str, Any],
    baseline_flat: Dict[str, Any],
) -> tuple[int, List[str], List[str], Set[str]]:
    mismatches = 0
    missing_fields: List[str] = []
    triggered: Set[str] = set()
    compared_numeric_paths: List[str] = []

    replay_paths = set(replay_flat.keys())
    baseline_paths = set(baseline_flat.keys())

    missing = sorted(baseline_paths - replay_paths)
    extra = sorted(replay_paths - baseline_paths)
    if missing:
        mismatches += len(missing)
        missing_fields.extend(missing)
        triggered.add("missing_fields")
    if extra:
        mismatches += len(extra)
        triggered.add("extra_fields")

    for path in sorted(replay_paths & baseline_paths):
        rv = replay_flat[path]
        bv = baseline_flat[path]
        if (isinstance(rv, bool) != isinstance(bv, bool)) or (
            type(rv) is not type(bv) and not (
                isinstance(rv, (int, float)) and isinstance(bv, (int, float))
            )
        ):
            mismatches += 1
            triggered.add("type_mismatch")
            continue
        if isinstance(rv, (int, float)) and isinstance(bv, (int, float)):
            compared_numeric_paths.append(path)

    return mismatches, missing_fields, compared_numeric_paths, triggered


def _compute_numeric_drift(
    replay_flat: Dict[str, Any],
    baseline_flat: Dict[str, Any],
    numeric_paths: List[str],
    *,
    abs_tolerance: float,
    rel_tolerance: float,
) -> tuple[float, int, Set[str]]:
    max_drift = 0.0
    numeric_exceeded = 0
    triggered: Set[str] = set()

    for path in numeric_paths:
        replay_value = float(replay_flat[path])
        baseline_value = float(baseline_flat[path])
        abs_diff = abs(replay_value - baseline_value)
        rel_denom = abs(baseline_value) if abs(baseline_value) > 1e-12 else 1.0
        rel_diff = abs_diff / rel_denom
        max_drift = max(max_drift, abs_diff)
        if abs_diff > abs_tolerance and rel_diff > rel_tolerance:
            numeric_exceeded += 1

    if numeric_exceeded:
        triggered.add("numeric_tolerance_exceeded")
    return max_drift, numeric_exceeded, triggered


def _build_drift_id(trace_id: str, baseline_id: str, replay_run_id: str) -> str:
    seed = f"{trace_id}|{baseline_id}|{replay_run_id}|drift-detection-v1"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _required_fields_missing(replay_flat: Dict[str, Any], required_fields: tuple[str, ...]) -> List[str]:
    return [field for field in required_fields if field not in replay_flat]


def run_drift_detection(
    replay_artifact: Dict[str, Any],
    baseline_artifact: Optional[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run deterministic drift detection and return a governed artifact."""
    if not isinstance(replay_artifact, dict):
        raise DriftDetectionError("replay_artifact must be an object")

    cfg = _to_config(config)
    replay_errors = validate_replay_artifact(replay_artifact)
    if replay_errors:
        raise DriftDetectionError(
            "replay_artifact failed schema validation: " + "; ".join(replay_errors)
        )

    trace_id = str(_extract_required_field(replay_artifact, "source_trace_id"))
    baseline_id = ""
    replay_run_id = _extract_run_id(replay_artifact)
    timestamp = str(_extract_required_field(replay_artifact, "replayed_at"))

    if baseline_artifact is None:
        baseline_id = "baseline_missing"
        drift = {
            "drift_id": _build_drift_id(trace_id, baseline_id, replay_run_id),
            "trace_id": trace_id,
            "baseline_id": baseline_id,
            "replay_run_id": replay_run_id,
            "drift_status": STATUS_INDETERMINATE,
            "drift_metrics": {
                "numeric_drift": 0.0,
                "field_mismatches": 0,
                "missing_fields": ["baseline_artifact"],
            },
            "thresholds_triggered": ["missing_baseline"],
            "comparison_summary": "Baseline artifact missing; drift comparison indeterminate.",
            "timestamp": timestamp,
        }
        output_errors = validate_drift_detection_result(drift)
        if output_errors:
            raise DriftDetectionError(
                "Generated indeterminate drift artifact failed schema validation: "
                + "; ".join(output_errors)
            )
        logger.warning(
            "drift_detection indeterminate trace_id=%s replay_run_id=%s reason=missing_baseline",
            trace_id,
            replay_run_id,
        )
        return drift

    if not isinstance(baseline_artifact, dict):
        raise DriftDetectionError("baseline_artifact must be an object when provided")

    baseline_errors = validate_replay_artifact(baseline_artifact)
    if baseline_errors:
        raise DriftDetectionError(
            "baseline_artifact failed schema validation: " + "; ".join(baseline_errors)
        )

    baseline_id = str(_extract_required_field(baseline_artifact, "replay_id"))

    replay_flat = _flatten_paths(replay_artifact)
    baseline_flat = _flatten_paths(baseline_artifact)

    required_missing = _required_fields_missing(replay_flat, cfg.required_fields)
    if required_missing:
        raise DriftDetectionError(
            "comparison incomplete: replay artifact missing required fields: "
            + ", ".join(required_missing)
        )

    struct_mismatches, missing_fields, numeric_paths, triggered = _compare_structures(
        replay_flat,
        baseline_flat,
    )
    numeric_drift, numeric_exceeded, numeric_triggered = _compute_numeric_drift(
        replay_flat,
        baseline_flat,
        numeric_paths,
        abs_tolerance=cfg.abs_tolerance,
        rel_tolerance=cfg.rel_tolerance,
    )

    triggered |= numeric_triggered
    field_mismatches = struct_mismatches + numeric_exceeded
    status = STATUS_DRIFT_DETECTED if field_mismatches > 0 else STATUS_NO_DRIFT

    summary = (
        f"Compared {len(replay_flat)} replay fields to {len(baseline_flat)} baseline fields; "
        f"mismatches={field_mismatches}, numeric_drift={numeric_drift:.12g}."
    )

    result = {
        "drift_id": _build_drift_id(trace_id, baseline_id, replay_run_id),
        "trace_id": trace_id,
        "baseline_id": baseline_id,
        "replay_run_id": replay_run_id,
        "drift_status": status,
        "drift_metrics": {
            "numeric_drift": numeric_drift,
            "field_mismatches": field_mismatches,
            "missing_fields": missing_fields,
        },
        "thresholds_triggered": sorted(triggered),
        "comparison_summary": summary,
        "timestamp": timestamp,
    }

    output_errors = validate_drift_detection_result(result)
    if output_errors:
        raise DriftDetectionError(
            "drift_detection_result failed schema validation: " + "; ".join(output_errors)
        )

    logger.info(
        "drift_detection completed trace_id=%s replay_run_id=%s status=%s mismatches=%s numeric_drift=%s",
        trace_id,
        replay_run_id,
        status,
        field_mismatches,
        f"{numeric_drift:.12g}",
    )
    return result
