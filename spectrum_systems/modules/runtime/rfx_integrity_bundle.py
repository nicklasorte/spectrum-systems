"""RFX provenance/replay evidence presence guard — LOOP-05 implementation.

This module is a non-owning presence check used during the RFX phase. It
does not issue lineage or replay decisions; canonical responsibilities for
those signals stay with the systems declared in the system registry. The
guard verifies that a lineage evidence record and a replay evidence record
are both present and valid before certification candidacy can be considered.

Without a matching replay evidence record there is no certification
candidate. Missing artifact = halt.
"""

from __future__ import annotations

from typing import Any


class RFXIntegrityBundleError(ValueError):
    """Raised when the RFX provenance/replay presence guard fails closed."""


def _is_nonempty_dict(obj: Any) -> bool:
    return isinstance(obj, dict) and bool(obj)


def assert_rfx_integrity_bundle(
    *,
    lineage_record: dict[str, Any] | None,
    replay_record: dict[str, Any] | None,
) -> None:
    """Verify a lineage evidence record and replay evidence record are both present and valid.

    This guard does not issue lineage or replay decisions. It only confirms
    presence and validity of the supplied records, then fails closed with
    deterministic, machine-readable reason codes when something is missing
    or invalid.

    Fail-closed reason codes:
      - ``rfx_missing_lineage``: lineage evidence record absent or empty.
      - ``rfx_lineage_not_authentic``: lineage authenticity is not ``pass``.
      - ``rfx_missing_replay``: replay evidence record absent or empty.
      - ``rfx_replay_mismatch``: replay match is not strictly ``True``.
    """
    if not _is_nonempty_dict(lineage_record):
        raise RFXIntegrityBundleError(
            "rfx_missing_lineage: lineage evidence record absent — "
            "certification candidate state blocked"
        )

    authenticity = lineage_record.get("authenticity")
    if authenticity != "pass":
        raise RFXIntegrityBundleError(
            f"rfx_lineage_not_authentic: lineage authenticity={authenticity!r} "
            "is not 'pass' — certification candidate state blocked"
        )

    if not _is_nonempty_dict(replay_record):
        raise RFXIntegrityBundleError(
            "rfx_missing_replay: replay evidence record absent — "
            "without a matching replay record there is no certification candidate"
        )

    replay_match = replay_record.get("match")
    if replay_match is not True:
        raise RFXIntegrityBundleError(
            f"rfx_replay_mismatch: replay match={replay_match!r} is not True — "
            "certification candidate state freeze/block"
        )


__all__ = [
    "RFXIntegrityBundleError",
    "assert_rfx_integrity_bundle",
]
