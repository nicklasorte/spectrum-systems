from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class HOPValidationError(RuntimeError):
    """Raised when candidate validation fails closed."""


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _load_schema(schema_name: str, schema_root: Path | None = None) -> dict[str, Any]:
    root = schema_root or (Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "hop")
    path = root / f"{schema_name}.schema.json"
    if not path.exists():
        raise HOPValidationError(f"missing schema: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_artifact_shape(artifact: dict[str, Any], schema_name: str, schema_root: Path | None = None) -> None:
    schema = _load_schema(schema_name=schema_name, schema_root=schema_root)
    Draft202012Validator(schema).validate(artifact)


def _load_module_from_path(path: Path) -> Any:
    if not path.exists():
        raise HOPValidationError(f"candidate path not found: {path}")
    spec = importlib.util.spec_from_file_location("hop_candidate_module", str(path))
    if spec is None or spec.loader is None:
        raise HOPValidationError(f"unable to import candidate module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_candidate(candidate_artifact: dict[str, Any], schema_root: Path | None = None) -> dict[str, Any]:
    """Validate contract + import smoke + required methods. Returns failure artifact on rejection."""
    try:
        validate_artifact_shape(candidate_artifact, "harness_candidate", schema_root=schema_root)
        code_path = Path(candidate_artifact["code_ref"]).resolve()
        module = _load_module_from_path(code_path)
        harness_class = getattr(module, "HarnessCandidate", None)
        if harness_class is None:
            raise HOPValidationError("HarnessCandidate class missing")
        candidate = harness_class()
        for method_name in candidate_artifact["interface"]["required_methods"]:
            method = getattr(candidate, method_name, None)
            if method is None or not callable(method):
                raise HOPValidationError(f"required method missing: {method_name}")
        return {"status": "pass", "candidate_id": candidate_artifact["candidate_id"]}
    except Exception as exc:
        failure = {
            "artifact_type": "harness_failure_hypothesis",
            "artifact_id": f"hop-failure-{candidate_artifact.get('candidate_id', 'unknown')}",
            "schema_ref": "hop/harness_failure_hypothesis.schema.json@1.0.0",
            "trace": {
                "trace_id": candidate_artifact.get("trace", {}).get("trace_id", "trace-missing"),
                "timestamp": _now(),
                "steps": [{"name": "candidate_validation", "status": "fail", "detail": str(exc)}],
            },
            "content_hash": _sha({"error": str(exc), "candidate": candidate_artifact.get("candidate_id")}),
            "created_at": _now(),
            "candidate_id": candidate_artifact.get("candidate_id", "unknown"),
            "failure_code": "candidate_validation_failed",
            "hypothesis": str(exc),
            "severity": "high",
            "source_artifact_id": candidate_artifact.get("artifact_id", "unknown"),
        }
        validate_artifact_shape(failure, "harness_failure_hypothesis", schema_root=schema_root)
        return {"status": "fail", "failure_artifact": failure}
