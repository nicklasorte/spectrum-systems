"""RFX integrity-bundle guard — LOOP-05.

Lineage (LIN) and replay (REP) are mandatory integrity overlays for RFX work.
This guard enforces that both are present and valid before a candidate may be
considered for GOV certification review.

Behavior is fail-closed:
  - missing lineage record       -> rfx_missing_lineage
  - lineage authenticity != pass -> rfx_lineage_not_authentic
  - missing replay record        -> rfx_missing_replay
  - replay match != True         -> rfx_replay_mismatch

No replay = no certification candidate. LIN remains the lineage-issuing
authority and REP remains the replay-integrity authority; this guard does not
redefine ownership.
"""

from __future__ import annotations

from typing import Any


class RFXIntegrityBundleError(ValueError):
    """Raised when LIN/REP integrity invariants fail closed for RFX work."""


def _coerce_lineage_authenticity(lineage_record: dict[str, Any]) -> Any:
    for key in ("authenticity", "authenticity_status", "authenticity_result"):
        if key in lineage_record:
            return lineage_record[key]
    return None


def _coerce_replay_match(replay_record: dict[str, Any]) -> Any:
    for key in ("match", "replay_match", "matches"):
        if key in replay_record:
            return replay_record[key]
    return None


def assert_rfx_integrity_bundle(
    *,
    lineage_record: dict[str, Any] | None,
    replay_record: dict[str, Any] | None,
) -> None:
    """Assert lineage + replay integrity bundle is present and valid.

    Fails closed with deterministic, machine-readable reason codes when the
    lineage record is absent, lineage authenticity is not ``pass``, the replay
    record is absent, or the replay match flag is not exactly ``True``.
    """
    if not isinstance(lineage_record, dict) or not lineage_record:
        raise RFXIntegrityBundleError(
            "rfx_missing_lineage: LIN lineage record absent — "
            "GOV certification candidate state blocked"
        )

    authenticity = _coerce_lineage_authenticity(lineage_record)
    if authenticity != "pass":
        raise RFXIntegrityBundleError(
            f"rfx_lineage_not_authentic: lineage authenticity={authenticity!r} "
            f"is not 'pass' — provenance integrity broken, certification blocked"
        )

    if not isinstance(replay_record, dict) or not replay_record:
        raise RFXIntegrityBundleError(
            "rfx_missing_replay: REP replay record absent — "
            "no replay = no certification candidate"
        )

    replay_match = _coerce_replay_match(replay_record)
    if replay_match is not True:
        raise RFXIntegrityBundleError(
            f"rfx_replay_mismatch: replay match={replay_match!r} is not True — "
            f"reproducibility not proven; freeze/block certification path"
        )


__all__ = [
    "RFXIntegrityBundleError",
    "assert_rfx_integrity_bundle",
]
