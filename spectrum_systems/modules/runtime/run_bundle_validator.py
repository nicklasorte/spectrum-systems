"""Run-bundle validation boundary with fail-closed artifact decisions."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker


REQUIRED_MANIFEST_FIELDS = [
    "run_id",
    "matlab_release",
    "runtime_version_required",
    "platform",
    "worker_entrypoint",
    "inputs",
    "expected_outputs",
]

REQUIRED_STRUCTURE_DIRS = ["inputs", "outputs", "logs"]
REQUIRED_EXPECTED_OUTPUTS = [
    "outputs/results_summary.json",
    "outputs/provenance.json",
]

_ALLOWED_MANIFEST_FIELDS = frozenset(REQUIRED_MANIFEST_FIELDS)
_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "artifact_validation_decision.schema.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision_id(run_id: str, timestamp: str) -> str:
    digest = hashlib.sha256(f"{run_id}:{timestamp}".encode("utf-8")).hexdigest()[:16]
    return f"avd_{digest}"


def _resolve_trace_id(run_id: str) -> str:
    try:
        from spectrum_systems.modules.runtime.trace_engine import start_trace

        return start_trace({"source": "run_bundle_validator", "run_id": run_id})
    except (ImportError, AttributeError):
        return str(uuid.uuid4())


def _load_manifest(bundle_path: Path) -> Dict[str, Any]:
    manifest_path = bundle_path / "run_bundle_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing required manifest: {manifest_path}")

    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("manifest must be a JSON object")
    return loaded


def _required_input_paths(manifest: Dict[str, Any]) -> List[str]:
    inputs = manifest.get("inputs")
    if not isinstance(inputs, list):
        return []

    required_paths: List[str] = []
    for entry in inputs:
        if not isinstance(entry, dict):
            continue
        if entry.get("required", True) is False:
            continue
        path = entry.get("path")
        if isinstance(path, str) and path:
            required_paths.append(path)
    return required_paths


def _expected_output_paths(manifest: Dict[str, Any]) -> List[str]:
    outputs = manifest.get("expected_outputs")
    if not isinstance(outputs, list):
        return []

    output_paths: List[str] = []
    for entry in outputs:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if isinstance(path, str) and path:
            output_paths.append(path)
    return output_paths


def validate_run_bundle(bundle_path: str | Path) -> Dict[str, Any]:
    """Validate run-bundle structure and manifest deterministically."""
    bundle_dir = Path(bundle_path)
    reasons: List[str] = []
    invalid_fields: List[str] = []
    missing_artifacts: List[str] = []

    try:
        manifest = _load_manifest(bundle_dir)
    except FileNotFoundError as exc:
        reasons.append(str(exc))
        return {
            "run_id": "unknown",
            "validation_results": {
                "manifest_valid": False,
                "inputs_present": False,
                "expected_outputs_declared": False,
                "output_paths_valid": False,
                "provenance_required": False,
            },
            "missing_artifacts": ["run_bundle_manifest.json"],
            "invalid_fields": ["run_bundle_manifest.json"],
            "reasons": reasons,
            "manifest": {},
        }
    except ValueError as exc:
        reasons.append(str(exc))
        return {
            "run_id": "unknown",
            "validation_results": {
                "manifest_valid": False,
                "inputs_present": False,
                "expected_outputs_declared": False,
                "output_paths_valid": False,
                "provenance_required": False,
            },
            "missing_artifacts": [],
            "invalid_fields": ["run_bundle_manifest.json"],
            "reasons": reasons,
            "manifest": {},
        }

    run_id = str(manifest.get("run_id") or "unknown")

    missing_fields = [f for f in REQUIRED_MANIFEST_FIELDS if f not in manifest]
    unexpected_fields = sorted(set(manifest.keys()) - _ALLOWED_MANIFEST_FIELDS)

    for field in missing_fields:
        invalid_fields.append(field)
        reasons.append(f"missing required manifest field: {field}")

    for field in unexpected_fields:
        invalid_fields.append(field)
        reasons.append(f"unexpected manifest field: {field}")

    for field in ("runtime_version_required", "platform", "expected_outputs"):
        value = manifest.get(field)
        if field == "expected_outputs":
            if not isinstance(value, list) or len(value) == 0:
                invalid_fields.append(field)
                reasons.append("expected_outputs must be a non-empty array")
        else:
            if not isinstance(value, str) or not value.strip():
                invalid_fields.append(field)
                reasons.append(f"{field} must be a non-empty string")

    for required_dir in REQUIRED_STRUCTURE_DIRS:
        path = bundle_dir / required_dir
        if not path.is_dir():
            missing_artifacts.append(required_dir + "/")
            reasons.append(f"missing required directory: {required_dir}/")

    required_input_paths = _required_input_paths(manifest)
    if not required_input_paths:
        invalid_fields.append("inputs")
        reasons.append("inputs must declare at least one required input path")

    for rel_path in required_input_paths:
        path = bundle_dir / rel_path
        if not path.is_file():
            missing_artifacts.append(rel_path)
            reasons.append(f"missing required input artifact: {rel_path}")

    declared_outputs = _expected_output_paths(manifest)
    declared_output_set = set(declared_outputs)
    missing_required_output_declarations = [
        path for path in REQUIRED_EXPECTED_OUTPUTS if path not in declared_output_set
    ]
    for path in missing_required_output_declarations:
        invalid_fields.append("expected_outputs")
        reasons.append(f"missing required expected output declaration: {path}")

    output_paths_valid = bool(declared_outputs) and all(
        output_path.startswith("outputs/") for output_path in declared_outputs
    )
    if not output_paths_valid:
        reasons.append("all expected output paths must be under outputs/")

    validation_results = {
        "manifest_valid": len(missing_fields) == 0 and len(unexpected_fields) == 0,
        "inputs_present": len(required_input_paths) > 0 and all(
            (bundle_dir / p).is_file() for p in required_input_paths
        ),
        "expected_outputs_declared": len(missing_required_output_declarations) == 0,
        "output_paths_valid": output_paths_valid,
        "provenance_required": "outputs/provenance.json" in declared_output_set,
    }

    return {
        "run_id": run_id,
        "validation_results": validation_results,
        "missing_artifacts": sorted(set(missing_artifacts)),
        "invalid_fields": sorted(set(invalid_fields)),
        "reasons": reasons,
        "manifest": manifest,
    }


def build_artifact_validation_decision(validation_report: Dict[str, Any]) -> Dict[str, Any]:
    """Build deterministic decision output from validator report."""
    run_id = str(validation_report.get("run_id") or "unknown")
    results = validation_report["validation_results"]
    missing_artifacts = validation_report["missing_artifacts"]
    invalid_fields = validation_report["invalid_fields"]
    reasons = validation_report["reasons"]

    has_blocker = bool(invalid_fields) or not results["manifest_valid"] or not results["expected_outputs_declared"]

    missing_outputs = [
        item
        for item in missing_artifacts
        if item.startswith("outputs/") or item == "outputs/"
    ]

    if has_blocker:
        status = "invalid"
        system_response = "block"
    elif missing_outputs:
        status = "invalid"
        system_response = "require_rebuild"
        reasons.append("bundle structure valid but required outputs are missing")
    elif all(results.values()):
        status = "valid"
        system_response = "allow"
    else:
        status = "invalid"
        system_response = "block"
        reasons.append("unknown validation state encountered; fail-closed block applied")

    timestamp = _now_iso()
    return {
        "decision_id": _decision_id(run_id, timestamp),
        "run_id": run_id,
        "trace_id": _resolve_trace_id(run_id),
        "status": status,
        "system_response": system_response,
        "validation_results": results,
        "missing_artifacts": missing_artifacts,
        "invalid_fields": invalid_fields,
        "reasons": reasons,
        "timestamp": timestamp,
    }


def validate_and_emit_decision(bundle_path: str | Path) -> Dict[str, Any]:
    """Validate a run bundle and return a schema-valid decision object."""
    report = validate_run_bundle(bundle_path)
    decision = build_artifact_validation_decision(report)

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(decision), key=lambda err: list(err.path))
    if errors:
        message = "; ".join(
            f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
            for err in errors
        )
        raise ValueError(f"artifact_validation_decision schema validation failed: {message}")

    return decision
