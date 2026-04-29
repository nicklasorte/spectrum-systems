"""OBS timeout trend record builder.

Records stream idle timeout events for observability and trend analysis.
Fail closed: required fields missing → raises rather than silently skipping.
"""

from __future__ import annotations

from spectrum_systems.contracts import validate_artifact


class OBSTimeoutTrendError(ValueError):
    """Raised when timeout trend record construction fails."""


def build_timeout_trend_record(
    *,
    provider: str,
    failure_type: str,
    stage: str,
    task_size_class: str,
    prompt_pattern: str,
    files_changed_before_timeout: int,
    checkpoint_present: bool,
) -> dict:
    """Build and schema-validate an obs_timeout_trend_record artifact."""
    record = {
        "artifact_type": "obs_timeout_trend_record",
        "schema_version": "1.0.0",
        "provider": provider,
        "failure_type": failure_type,
        "stage": stage,
        "task_size_class": task_size_class,
        "prompt_pattern": prompt_pattern,
        "files_changed_before_timeout": files_changed_before_timeout,
        "checkpoint_present": checkpoint_present,
    }

    try:
        validate_artifact(record, "obs_timeout_trend_record")
    except Exception as exc:
        raise OBSTimeoutTrendError(f"obs_timeout_trend_record invalid: {exc}") from exc

    return record
