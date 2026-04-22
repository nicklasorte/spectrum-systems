"""Fail-closed enforcer: every exception produces a mandatory failure artifact.

No exception may pass silently. Every failure gets a unique ID, reason code,
trace linkage, system attribution, and human-readable message — stored immediately.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

MANDATORY_FAILURE_FIELDS: List[str] = [
    "failure_id",
    "reason_code",
    "trace_id",
    "timestamp",
    "system_id",
    "human_readable",
]

_STORAGE_DIR = os.environ.get("FAILURE_ARTIFACT_DIR", "data/failure_artifacts")

_ERROR_REASON_MAP: Dict[type, str] = {
    ValueError: "VALIDATION_ERROR",
    TypeError: "TYPE_ERROR",
    KeyError: "MISSING_FIELD",
    AttributeError: "ATTRIBUTE_ERROR",
    FileNotFoundError: "RESOURCE_NOT_FOUND",
    PermissionError: "PERMISSION_DENIED",
    TimeoutError: "TIMEOUT",
    NotImplementedError: "NOT_IMPLEMENTED",
    RuntimeError: "RUNTIME_ERROR",
}


class FailClosedEnforcer:
    """Mandatory failure artifact enforcer.

    Every call to enforce_failure_artifact produces a validated, stored
    failure artifact. Storage uses 3-retry logic. Artifacts are immutable
    after creation.
    """

    def __init__(self, system_id: str = "UNKNOWN", storage_dir: str = _STORAGE_DIR) -> None:
        self.system_id = system_id
        self.storage_dir = storage_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enforce_failure_artifact(
        self,
        error: Exception,
        trace_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build, validate, store, and return a failure artifact. Never raises."""
        failure_id = f"FAIL-{uuid.uuid4().hex[:12].upper()}"
        timestamp = datetime.now(timezone.utc).isoformat()
        reason_code = self._classify_error(error)

        artifact: Dict[str, Any] = {
            "failure_id": failure_id,
            "reason_code": reason_code,
            "trace_id": trace_id,
            "timestamp": timestamp,
            "system_id": self.system_id,
            "human_readable": self._human_readable(error, reason_code),
            "error_type": type(error).__name__,
            "error_detail": str(error),
            "context": context or {},
        }

        missing = self._validate_mandatory_fields(artifact)
        if missing:
            artifact["_validation_warning"] = f"Missing fields: {missing}"

        self._store_with_retry(artifact, failure_id)
        return artifact

    def validate_failure_artifact(self, artifact: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Return (valid, list_of_violations). Validates mandatory fields and types."""
        violations: List[str] = []
        violations.extend(self._validate_mandatory_fields(artifact))
        violations.extend(self._validate_field_types(artifact))
        return (len(violations) == 0, violations)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_error(self, error: Exception) -> str:
        """Map exception type to canonical reason code."""
        for exc_type, code in _ERROR_REASON_MAP.items():
            if isinstance(error, exc_type):
                return code
        return "UNCLASSIFIED_ERROR"

    def _human_readable(self, error: Exception, reason_code: str) -> str:
        return f"[{reason_code}] {type(error).__name__}: {error}"

    def _validate_mandatory_fields(self, artifact: Dict[str, Any]) -> List[str]:
        return [f for f in MANDATORY_FAILURE_FIELDS if f not in artifact or artifact[f] is None]

    def _validate_field_types(self, artifact: Dict[str, Any]) -> List[str]:
        violations: List[str] = []
        str_fields = ["failure_id", "reason_code", "trace_id", "timestamp", "system_id", "human_readable"]
        for field in str_fields:
            if field in artifact and not isinstance(artifact[field], str):
                violations.append(f"{field} must be str, got {type(artifact[field]).__name__}")
        return violations

    def _store_with_retry(self, artifact: Dict[str, Any], failure_id: str) -> Optional[str]:
        """Store artifact with up to 3 retries. Returns path or None on total failure."""
        os.makedirs(self.storage_dir, exist_ok=True)
        path = os.path.join(self.storage_dir, f"{failure_id}.json")
        for attempt in range(3):
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(artifact, fh, indent=2, ensure_ascii=False)
                return path
            except OSError:
                if attempt < 2:
                    time.sleep(0.1 * (attempt + 1))
        return None
