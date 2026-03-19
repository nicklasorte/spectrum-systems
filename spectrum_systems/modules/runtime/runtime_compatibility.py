"""Runtime compatibility enforcement for execution bundles (Prompt BC).

Validates a run-bundle manifest against the active runtime environment
BEFORE any job is allowed to execute.  Every validation call produces a
deterministic decision artifact.

Allowed system responses
------------------------
allow_execution
    Bundle is fully compatible; execution is permitted.
reject_execution
    Hard incompatibility detected; execution is blocked.
require_rebuild
    Bundle artifacts are incomplete; bundle must be rebuilt.
require_environment_update
    Runtime environment does not satisfy bundle requirements; the
    environment must be updated before re-submission.

Failure types
-------------
runtime_version_mismatch
    Installed MATLAB Runtime does not exactly match the version declared
    in the bundle manifest.
platform_mismatch
    Bundle requires a platform (linux/windows) different from the one
    that is active in the runtime environment.
missing_artifacts
    One or more required files declared in the manifest are absent.
invalid_entrypoint
    The declared entrypoint script is absent or not executable.
cache_unavailable
    The bundle requires a cache that is not available in the environment.
manifest_invalid
    The bundle manifest is missing one or more required fields.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_MATLAB_RUNTIME_VERSIONS: List[str] = [
    "R2022b",
    "R2023a",
    "R2023b",
    "R2024a",
    "R2024b",
]

REQUIRED_MANIFEST_FIELDS: List[str] = [
    "bundle_id",
    "matlab_runtime_version",
    "required_platform",
    "entrypoint_script",
    "required_files",
    "created_at",
]

SYSTEM_RESPONSE_VALUES = frozenset(
    {
        "allow_execution",
        "reject_execution",
        "require_rebuild",
        "require_environment_update",
    }
)

FAILURE_TYPE_VALUES = frozenset(
    {
        "runtime_version_mismatch",
        "platform_mismatch",
        "missing_artifacts",
        "invalid_entrypoint",
        "cache_unavailable",
        "manifest_invalid",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision_id(bundle_id: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{bundle_id}:{created_at}".encode("utf-8")).hexdigest()[:16]
    return f"rcd_{digest}"


# ---------------------------------------------------------------------------
# Runtime environment snapshot
# ---------------------------------------------------------------------------


def capture_runtime_env_snapshot(runtime_env: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Capture a snapshot of the current execution environment.

    When *runtime_env* is provided, its values override auto-detected
    values.  This allows tests and controlled environments to supply a
    deterministic snapshot without touching the OS.
    """
    snapshot: Dict[str, Any] = {
        "os": platform.system().lower(),
        "os_release": platform.release(),
        "python_version": sys.version,
        "hostname": socket.gethostname(),
        "matlab_runtime_version": None,
        "available_disk_bytes": None,
        "cache_available": False,
    }

    # Best-effort disk space detection
    try:
        usage = shutil.disk_usage(Path.home())
        snapshot["available_disk_bytes"] = usage.free
    except OSError:
        pass

    # Apply caller-supplied overrides (enables deterministic testing)
    if runtime_env:
        snapshot.update(runtime_env)

    return snapshot


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------


def validate_matlab_runtime_version(
    bundle_manifest: Dict[str, Any],
    runtime_env_snapshot: Dict[str, Any],
) -> List[str]:
    """Return a list of error strings; empty list means validation passed.

    Rules:
    - Required version must be in SUPPORTED_MATLAB_RUNTIME_VERSIONS.
    - The installed version (from runtime_env_snapshot) must EXACTLY match
      the required version.  No partial matching or fallback.
    """
    errors: List[str] = []
    required_version = bundle_manifest.get("matlab_runtime_version")
    if not required_version:
        errors.append("manifest_invalid: missing matlab_runtime_version in bundle manifest")
        return errors

    if required_version not in SUPPORTED_MATLAB_RUNTIME_VERSIONS:
        errors.append(
            f"runtime_version_mismatch: required version '{required_version}' is not in "
            f"the supported list {SUPPORTED_MATLAB_RUNTIME_VERSIONS}"
        )
        return errors

    installed_version = runtime_env_snapshot.get("matlab_runtime_version")
    if installed_version is None:
        errors.append(
            f"runtime_version_mismatch: no MATLAB Runtime is installed in the environment; "
            f"required '{required_version}'"
        )
        return errors

    if str(installed_version) != str(required_version):
        errors.append(
            f"runtime_version_mismatch: installed MATLAB Runtime '{installed_version}' "
            f"does not match required '{required_version}'"
        )

    return errors


def validate_platform_compatibility(
    bundle_manifest: Dict[str, Any],
    runtime_env_snapshot: Dict[str, Any],
) -> List[str]:
    """Return a list of error strings; empty list means validation passed.

    Rules:
    - If the bundle declares a required_platform, the running OS must match.
    - Matching is case-insensitive prefix: 'linux' in 'linux', 'windows' in
      'windows'.
    """
    errors: List[str] = []
    required_platform = bundle_manifest.get("required_platform", "")
    if not required_platform:
        return errors

    current_os = str(runtime_env_snapshot.get("os", "")).lower()
    required_platform_lower = required_platform.lower()

    if required_platform_lower not in current_os and current_os not in required_platform_lower:
        errors.append(
            f"platform_mismatch: bundle requires platform '{required_platform}' "
            f"but current environment is '{current_os}'"
        )

    return errors


def validate_required_artifacts(
    bundle_manifest: Dict[str, Any],
    base_path: Optional[Path] = None,
) -> List[str]:
    """Return a list of error strings; empty list means validation passed.

    Rules:
    - Every path in required_files must exist and be a file.
    - If base_path is provided, relative paths are resolved against it.
    """
    errors: List[str] = []
    required_files = bundle_manifest.get("required_files")
    if not isinstance(required_files, list):
        errors.append("manifest_invalid: required_files must be a list")
        return errors

    for f in required_files:
        path = Path(str(f))
        if base_path and not path.is_absolute():
            path = base_path / path
        if not path.exists() or not path.is_file():
            errors.append(f"missing_artifacts: required file not found: {f}")

    return errors


def validate_entrypoint(
    bundle_manifest: Dict[str, Any],
    base_path: Optional[Path] = None,
) -> List[str]:
    """Return a list of error strings; empty list means validation passed.

    Rules:
    - entrypoint_script must exist.
    - entrypoint_script must be executable (os.access check).
    """
    errors: List[str] = []
    entrypoint = bundle_manifest.get("entrypoint_script")
    if not entrypoint:
        errors.append("invalid_entrypoint: entrypoint_script is missing from bundle manifest")
        return errors

    path = Path(str(entrypoint))
    if base_path and not path.is_absolute():
        path = base_path / path

    if not path.exists() or not path.is_file():
        errors.append(f"invalid_entrypoint: entrypoint script does not exist: {entrypoint}")
        return errors

    if not os.access(path, os.X_OK):
        errors.append(f"invalid_entrypoint: entrypoint script is not executable: {entrypoint}")

    return errors


def validate_cache_policy(
    bundle_manifest: Dict[str, Any],
    runtime_env_snapshot: Dict[str, Any],
) -> List[str]:
    """Return a list of error strings; empty list means validation passed.

    Rules:
    - If optional_cache_policy is present and truthy, the environment must
      report cache_available=True.
    """
    errors: List[str] = []
    cache_policy = bundle_manifest.get("optional_cache_policy")
    if not cache_policy:
        return errors

    cache_available = bool(runtime_env_snapshot.get("cache_available"))
    if not cache_available:
        errors.append(
            f"cache_unavailable: bundle requires cache policy '{cache_policy}' "
            "but no cache is available in the runtime environment"
        )

    return errors


def validate_manifest_integrity(bundle_manifest: Dict[str, Any]) -> List[str]:
    """Return a list of error strings; empty list means validation passed.

    Rules:
    - All REQUIRED_MANIFEST_FIELDS must be present and non-None.
    """
    errors: List[str] = []
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in bundle_manifest or bundle_manifest[field] is None:
            errors.append(f"manifest_invalid: missing required field '{field}'")
    return errors


# ---------------------------------------------------------------------------
# Failure type classifier
# ---------------------------------------------------------------------------

_FAILURE_TYPE_PRIORITY = {
    "manifest_invalid": 0,
    "runtime_version_mismatch": 1,
    "platform_mismatch": 2,
    "missing_artifacts": 3,
    "invalid_entrypoint": 4,
    "cache_unavailable": 5,
}


def classify_runtime_failure(triggering_conditions: List[str]) -> Optional[str]:
    """Return the most severe failure type found in *triggering_conditions*.

    Returns ``None`` when there are no conditions (compatible bundle).
    """
    found: Optional[str] = None
    found_priority = 999
    for condition in triggering_conditions:
        for failure_type, priority in _FAILURE_TYPE_PRIORITY.items():
            if condition.startswith(failure_type):
                if priority < found_priority:
                    found = failure_type
                    found_priority = priority
    return found


# ---------------------------------------------------------------------------
# System response derivation
# ---------------------------------------------------------------------------

_FAILURE_TO_RESPONSE: Dict[str, str] = {
    "manifest_invalid": "reject_execution",
    "runtime_version_mismatch": "reject_execution",
    "platform_mismatch": "reject_execution",
    "invalid_entrypoint": "reject_execution",
    "missing_artifacts": "require_rebuild",
    "cache_unavailable": "require_environment_update",
}


def derive_runtime_decision(
    bundle_manifest: Dict[str, Any],
    triggering_conditions: List[str],
) -> Dict[str, Any]:
    """Derive a system response from the accumulated triggering conditions.

    Returns a dict with ``compatible``, ``system_response``, and
    ``failure_type`` fields.
    """
    if not triggering_conditions:
        return {
            "compatible": True,
            "system_response": "allow_execution",
            "failure_type": None,
        }

    failure_type = classify_runtime_failure(triggering_conditions)
    system_response = _FAILURE_TO_RESPONSE.get(failure_type or "", "reject_execution")

    return {
        "compatible": False,
        "system_response": system_response,
        "failure_type": failure_type,
    }


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def validate_runtime_environment(
    bundle_manifest: Dict[str, Any],
    runtime_env: Optional[Dict[str, Any]] = None,
    base_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validate *bundle_manifest* against *runtime_env* and return a full decision artifact.

    Parameters
    ----------
    bundle_manifest:
        Dict representation of the run-bundle manifest.
    runtime_env:
        Optional dict of runtime environment overrides.  Auto-detected when
        ``None``.
    base_path:
        Optional base directory used to resolve relative file paths in the
        manifest.

    Returns
    -------
    dict
        A complete runtime compatibility decision artifact ready for
        persistence and inspection.
    """
    created_at = _now_iso()
    bundle_id = bundle_manifest.get("bundle_id", "unknown")

    # Capture environment snapshot
    env_snapshot = capture_runtime_env_snapshot(runtime_env)

    triggering_conditions: List[str] = []

    # --- Manifest integrity first (fast-fail) ---
    integrity_errors = validate_manifest_integrity(bundle_manifest)
    triggering_conditions.extend(integrity_errors)

    # --- Remaining validators (only if manifest is minimally intact) ---
    if not integrity_errors:
        triggering_conditions.extend(
            validate_matlab_runtime_version(bundle_manifest, env_snapshot)
        )
        triggering_conditions.extend(
            validate_platform_compatibility(bundle_manifest, env_snapshot)
        )
        triggering_conditions.extend(
            validate_required_artifacts(bundle_manifest, base_path)
        )
        triggering_conditions.extend(validate_entrypoint(bundle_manifest, base_path))
        triggering_conditions.extend(validate_cache_policy(bundle_manifest, env_snapshot))

    decision_core = derive_runtime_decision(bundle_manifest, triggering_conditions)

    required_actions = _build_required_actions(decision_core["system_response"])

    decision: Dict[str, Any] = {
        "decision_id": _decision_id(bundle_id, created_at),
        "bundle_id": bundle_id,
        "created_at": created_at,
        "compatible": decision_core["compatible"],
        "system_response": decision_core["system_response"],
        "failure_type": decision_core["failure_type"],
        "triggering_conditions": triggering_conditions,
        "required_actions": required_actions,
        "runtime_env_snapshot": env_snapshot,
        "notes": _build_notes(decision_core),
    }

    return decision


def _build_required_actions(system_response: str) -> List[str]:
    mapping: Dict[str, List[str]] = {
        "allow_execution": [],
        "reject_execution": ["review_triggering_conditions", "fix_bundle_or_environment_before_resubmission"],
        "require_rebuild": ["rebuild_bundle_with_all_required_artifacts"],
        "require_environment_update": ["update_runtime_environment_to_satisfy_cache_policy"],
    }
    return mapping.get(system_response, ["review_triggering_conditions"])


def _build_notes(decision_core: Dict[str, Any]) -> str:
    if decision_core["compatible"]:
        return "Bundle is fully compatible with the runtime environment. Execution is permitted."
    return (
        f"Bundle rejected with failure type '{decision_core['failure_type']}'. "
        f"System response: '{decision_core['system_response']}'. "
        "Review triggering_conditions for details."
    )
