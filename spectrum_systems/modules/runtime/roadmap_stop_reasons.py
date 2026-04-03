"""Canonical stop-reason taxonomy for bounded roadmap execution surfaces (RDX-006A)."""

from __future__ import annotations

from typing import Final

STOP_REASON_MAX_BATCHES_REACHED: Final[str] = "max_batches_reached"
STOP_REASON_HARD_GATE_STOP: Final[str] = "hard_gate_stop"
STOP_REASON_AUTHORIZATION_BLOCK: Final[str] = "authorization_block"
STOP_REASON_AUTHORIZATION_FREEZE: Final[str] = "authorization_freeze"
STOP_REASON_MISSING_REQUIRED_SIGNAL: Final[str] = "missing_required_signal"
STOP_REASON_EXECUTION_BLOCKED: Final[str] = "execution_blocked"
STOP_REASON_EXECUTION_FAILED: Final[str] = "execution_failed"
STOP_REASON_LOOP_VALIDATION_FAILED: Final[str] = "loop_validation_failed"
STOP_REASON_REPLAY_NOT_READY: Final[str] = "replay_not_ready"
STOP_REASON_INVALID_ROADMAP_STATE: Final[str] = "invalid_roadmap_state"
STOP_REASON_INVALID_PROGRESS_STATE: Final[str] = "invalid_progress_state"
STOP_REASON_CONTRACT_PRECONDITION_FAILED: Final[str] = "contract_precondition_failed"
STOP_REASON_NO_ELIGIBLE_BATCH: Final[str] = "no_eligible_batch"

CANONICAL_STOP_REASONS: Final[tuple[str, ...]] = (
    STOP_REASON_MAX_BATCHES_REACHED,
    STOP_REASON_HARD_GATE_STOP,
    STOP_REASON_AUTHORIZATION_BLOCK,
    STOP_REASON_AUTHORIZATION_FREEZE,
    STOP_REASON_MISSING_REQUIRED_SIGNAL,
    STOP_REASON_EXECUTION_BLOCKED,
    STOP_REASON_EXECUTION_FAILED,
    STOP_REASON_LOOP_VALIDATION_FAILED,
    STOP_REASON_REPLAY_NOT_READY,
    STOP_REASON_INVALID_ROADMAP_STATE,
    STOP_REASON_INVALID_PROGRESS_STATE,
    STOP_REASON_CONTRACT_PRECONDITION_FAILED,
    STOP_REASON_NO_ELIGIBLE_BATCH,
)

