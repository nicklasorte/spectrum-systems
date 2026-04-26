"""RFX telemetry-enforced SLO gate — LOOP-08.

Part 4 of the RFX reliability/SLO enforcement layer. Observability is not
optional: an SLO posture marked ``ok`` while OBS evidence is incomplete or
absent must fail closed. SLO is required to be computed *from* OBS — never
independently — and the cross-check below catches the inconsistency.

Strict OBS invariants enforced:

  * trace_id present
  * execution path coverage present
  * artifact linkage present
  * failure logs present (an empty list is acceptable; a missing key is not)

Cross-check failure code:

  * ``rfx_slo_inconsistent_with_obs`` — SLO claims ``ok`` while OBS is
    incomplete (missing trace segments, artifact linkage, or failure logs)

This guard is a non-owning phase-label support helper. Canonical authority
for OBS and SLO is recorded in ``docs/architecture/system_registry.md``.
"""

from __future__ import annotations

from typing import Any


class RFXTelemetrySLOError(ValueError):
    """Raised when LOOP-08 telemetry/SLO invariants fail closed."""


_OBS_REQUIRED_FIELDS: tuple[str, ...] = (
    "trace_id",
    "execution_path_coverage",
    "artifact_linkage",
    "failure_logs",
)

_OBS_COMPLETENESS_PASS = frozenset({"pass", "complete"})

_SLO_OK = frozenset({"pass", "ok", "within_budget", "acceptable"})


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _coerce_completeness(obs: dict[str, Any]) -> Any:
    for key in ("completeness", "telemetry_completeness", "status"):
        v = obs.get(key)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


def _is_complete_value(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() in _OBS_COMPLETENESS_PASS:
        return True
    return False


def _coerce_slo_status(slo: dict[str, Any]) -> str | None:
    for key in ("status", "posture", "rollout_state"):
        s = _coerce_str(slo.get(key))
        if s is not None:
            return s
    return None


def _slo_derived_from_obs(slo: dict[str, Any], obs: dict[str, Any]) -> bool:
    """Return True iff the SLO record explicitly references its OBS source.

    Accepts the following OBS-source ID aliases (string value matching
    the OBS record's id):

      * ``obs_ref``
      * ``source_obs_id``
      * ``derived_from_obs_id``
      * ``derived_from_obs`` (string form)

    Also accepts a boolean ``derived_from_obs=True`` flag combined with a
    matching string id in any of the *_id aliases above. Anything else is
    treated as not-derived so an independent SLO calculation cannot
    pass-through.
    """
    obs_id = _coerce_str(obs.get("obs_id")) or _coerce_str(obs.get("id"))
    if obs_id is None:
        return False
    explicit_ref = (
        _coerce_str(slo.get("obs_ref"))
        or _coerce_str(slo.get("source_obs_id"))
        or _coerce_str(slo.get("derived_from_obs_id"))
        or _coerce_str(slo.get("derived_from_obs"))
    )
    if explicit_ref is not None and explicit_ref == obs_id:
        return True
    # Boolean ``derived_from_obs=True`` is a confirmation flag — it must be
    # paired with a matching id alias to count as derived.
    if slo.get("derived_from_obs") is True and explicit_ref is not None and explicit_ref == obs_id:
        return True
    return False


def assert_rfx_telemetry_slo_eligible(
    *,
    obs: dict[str, Any] | None,
    slo: dict[str, Any] | None,
) -> None:
    """LOOP-08 telemetry-enforced SLO eligibility gate.

    Fails closed when any required OBS field is missing, when OBS
    completeness is not ``pass``/``complete``/``True``, or when the SLO
    posture is reported as ``ok`` but OBS is incomplete.
    """
    reasons: list[str] = []

    obs_present = _is_dict(obs)
    slo_present = _is_dict(slo)

    if not obs_present:
        reasons.append(
            "rfx_missing_obs_telemetry: OBS telemetry record absent — "
            "SLO eligibility cannot be established"
        )
    if not slo_present:
        reasons.append(
            "rfx_missing_slo: SLO posture record absent — "
            "telemetry-enforced SLO gate blocked"
        )

    if not obs_present or not slo_present:
        raise RFXTelemetrySLOError("; ".join(reasons))

    # ---- OBS completeness invariants ----------------------------------
    missing_fields: list[str] = []
    for key in _OBS_REQUIRED_FIELDS:
        if key not in obs:
            missing_fields.append(key)
            continue
        v = obs[key]
        # Only ``None`` is invalid — empty list/string is structurally
        # acceptable for ``failure_logs`` (no failures observed) but the
        # field MUST be present.
        if v is None:
            missing_fields.append(key)
        elif key == "trace_id" and _coerce_str(v) is None:
            missing_fields.append(key)

    if missing_fields:
        reasons.append(
            "rfx_obs_incomplete: OBS missing required fields: "
            + ", ".join(sorted(missing_fields))
        )

    completeness = _coerce_completeness(obs)
    if not _is_complete_value(completeness):
        reasons.append(
            f"rfx_obs_incomplete: OBS completeness={completeness!r} "
            f"not 'pass'/'complete'/True"
        )

    # ---- SLO posture & derivation invariants --------------------------
    slo_status = _coerce_slo_status(slo)
    if slo_status is None:
        reasons.append("rfx_slo_block: SLO record missing status/posture")

    # If SLO claims ok, OBS must be complete and the SLO must be derived
    # from OBS — else the cross-check fires deterministically.
    if slo_status in _SLO_OK:
        obs_complete = (not missing_fields) and _is_complete_value(completeness)
        if not obs_complete:
            reasons.append(
                "rfx_slo_inconsistent_with_obs: SLO reports "
                f"status={slo_status!r} but OBS is incomplete — "
                "missing trace segments, artifact linkage, or failure logs"
            )
        if not _slo_derived_from_obs(slo, obs):
            reasons.append(
                "rfx_slo_inconsistent_with_obs: SLO does not declare an "
                "OBS source (obs_ref/source_obs_id) — SLO must be computed "
                "FROM OBS, not independently"
            )
    elif slo_status is not None:
        reasons.append(
            f"rfx_slo_block: SLO status={slo_status!r} not in {sorted(_SLO_OK)!r}"
        )

    if reasons:
        raise RFXTelemetrySLOError("; ".join(reasons))


__all__ = [
    "RFXTelemetrySLOError",
    "assert_rfx_telemetry_slo_eligible",
]
