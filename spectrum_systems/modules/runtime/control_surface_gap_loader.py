"""Fail-closed loader for governed control-surface gap packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact


class ControlSurfaceGapPacketLoaderError(ValueError):
    """Raised when control-surface gap packet loading fails closed."""


def load_control_surface_gap_packet(ref: str) -> dict[str, Any]:
    """Load and validate a control_surface_gap_packet artifact reference.

    The loader is pure and fail-closed:
    - missing references raise
    - unreadable JSON raises
    - schema-invalid payloads raise
    """

    if not isinstance(ref, str) or not ref.strip():
        raise ControlSurfaceGapPacketLoaderError("control_surface_gap_packet ref must be a non-empty string")

    packet_path = Path(ref.strip())
    if not packet_path.exists():
        raise ControlSurfaceGapPacketLoaderError(f"control_surface_gap_packet file not found: {packet_path}")

    try:
        payload = json.loads(packet_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ControlSurfaceGapPacketLoaderError(f"invalid JSON in control_surface_gap_packet: {exc}") from exc

    if not isinstance(payload, dict):
        raise ControlSurfaceGapPacketLoaderError("control_surface_gap_packet payload must be a JSON object")

    try:
        validate_artifact(payload, "control_surface_gap_packet")
    except ValueError as exc:
        raise ControlSurfaceGapPacketLoaderError(f"control_surface_gap_packet failed schema validation: {exc}") from exc

    return payload
