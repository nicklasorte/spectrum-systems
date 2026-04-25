from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .validator import validate_artifact_shape


class HOPSafetyError(RuntimeError):
    """Raised when tamper/leakage checks fail."""


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def run_safety_checks(
    *,
    candidate_artifact: dict[str, Any],
    eval_set_path: Path,
    schema_changed_paths: list[str] | None = None,
    bypass_flags: list[str] | None = None,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    """Block candidate if leakage/tampering/bypass indicators are present."""
    schema_changed_paths = schema_changed_paths or []
    bypass_flags = bypass_flags or []

    code_text = Path(candidate_artifact["code_ref"]).read_text(encoding="utf-8").lower()
    eval_blob = eval_set_path.read_text(encoding="utf-8").lower()

    reasons: list[str] = []
    if "hardcoded eval answer" in code_text:
        reasons.append("hardcoded_answers")
    if "golden-01" in code_text or "adversarial-01" in code_text:
        reasons.append("eval_dataset_leakage")
    if any("contracts/schemas/hop" in path for path in schema_changed_paths):
        reasons.append("schema_weakening")
    if any(flag in {"skip_eval", "disable_validation", "direct_promote"} for flag in bypass_flags):
        reasons.append("eval_bypass_attempt")
    if "golden-" not in eval_blob or "adversarial-" not in eval_blob:
        reasons.append("eval_dataset_tamper")

    if reasons:
        failure = {
            "artifact_type": "harness_failure_hypothesis",
            "artifact_id": f"hop-failure-safety-{candidate_artifact['candidate_id']}",
            "schema_ref": "hop/harness_failure_hypothesis.schema.json@1.0.0",
            "trace": {
                "trace_id": candidate_artifact["trace"]["trace_id"],
                "timestamp": _now(),
                "steps": [{"name": "safety_checks", "status": "block", "detail": ",".join(reasons)}],
            },
            "content_hash": _sha({"candidate_id": candidate_artifact["candidate_id"], "reasons": reasons}),
            "created_at": _now(),
            "candidate_id": candidate_artifact["candidate_id"],
            "failure_code": "safety_check_block",
            "hypothesis": " | ".join(reasons),
            "severity": "critical",
            "source_artifact_id": candidate_artifact["artifact_id"],
        }
        validate_artifact_shape(failure, "harness_failure_hypothesis", schema_root=schema_root)
        return {"status": "block", "failure_artifact": failure}

    return {"status": "pass", "candidate_id": candidate_artifact["candidate_id"]}
