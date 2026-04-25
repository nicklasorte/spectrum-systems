"""RFX integrity bundle guard — LOOP-05 implementation.

LIN remains the lineage authority and REP remains the replay authority. This
guard does NOT relocate either authority. It enforces the rule: certification
candidacy requires a present, authentic lineage record AND a present,
matching replay record.

No replay = no certification candidate. Missing artifact = halt.
"""

from __future__ import annotations

from typing import Any


class RFXIntegrityBundleError(ValueError):
    """Raised when RFX LIN+REP integrity invariants fail closed."""


def _is_nonempty_dict(obj: Any) -> bool:
    return isinstance(obj, dict) and bool(obj)


def assert_rfx_integrity_bundle(
    *,
    lineage_record: dict[str, Any] | None,
    replay_record: dict[str, Any] | None,
) -> None:
    """Assert lineage authenticity and replay match before certification.

    Fail-closed reason codes:
      - ``rfx_missing_lineage``: LIN lineage record absent or empty.
      - ``rfx_lineage_not_authentic``: lineage authenticity is not ``pass``.
      - ``rfx_missing_replay``: REP replay record absent or empty.
      - ``rfx_replay_mismatch``: replay match is not strictly ``True``.
    """
    if not _is_nonempty_dict(lineage_record):
        raise RFXIntegrityBundleError(
            "rfx_missing_lineage: LIN lineage record absent — "
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
            "rfx_missing_replay: REP replay record absent — "
            "no replay = no certification candidate"
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
