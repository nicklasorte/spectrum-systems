"""PRL long-running task failure packet.

Produces a learning-facing failure packet for the stream_idle_timeout class.
Consumed by the governed eval/learning substrate for future pre-PR prevention.
Does not make policy decisions or execute enforcement.
"""

from __future__ import annotations

from spectrum_systems.contracts import validate_artifact

_DEFAULT_PREVENTION = (
    "split_task",
    "require_checkpoint",
    "cap_test_file_size",
    "stop_after_checkpoint",
    "run_targeted_tests_before_continuing",
)


class PRLLRTPacketError(ValueError):
    """Raised when failure packet construction fails validation."""


def build_lrt_failure_packet(
    *,
    trace_id: str,
    failure_type: str,
    provider: str,
    stage: str,
    prevention: list[str] | None = None,
) -> dict:
    """Build and schema-validate a prl_lrt_failure_packet artifact."""
    packet = {
        "artifact_type": "prl_lrt_failure_packet",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "failure_type": failure_type,
        "provider": provider,
        "stage": stage,
        "prevention": list(prevention) if prevention is not None else list(_DEFAULT_PREVENTION),
    }

    try:
        validate_artifact(packet, "prl_lrt_failure_packet")
    except Exception as exc:
        raise PRLLRTPacketError(f"prl_lrt_failure_packet invalid: {exc}") from exc

    return packet
