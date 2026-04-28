"""RFX chaos campaign engine — RFX-09.

Continuously proves fail-closed behavior across the RFX path. Each chaos
case represents a known-bad input mutation that **must** cause a
deterministic block / freeze with a recognized reason code. If a case
fails open (no exception raised, or exception lacks a reason code), the
entire campaign fails closed with ``rfx_chaos_case_failed_open``.

This module is a non-owning phase-label support helper. Canonical
fail-closed authority for AEX/TLC/EVL/TPA/CDE/SEL/LIN/REP/OBS/SLO/PRA/POL
remains with the systems recorded in
``docs/architecture/system_registry.md``.

Outputs:

  * ``rfx_chaos_campaign_record``
  * ``rfx_chaos_case_result``

Reason codes:

  * ``rfx_chaos_case_failed_open``
  * ``rfx_chaos_expected_block_missing``
  * ``rfx_chaos_reason_code_missing``
  * ``rfx_chaos_campaign_incomplete``
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable


class RFXChaosCampaignError(ValueError):
    """Raised when a chaos campaign fails closed."""


# Canonical chaos scenario set the campaign must cover.
REQUIRED_CHAOS_SCENARIOS: tuple[str, ...] = (
    "missing_aex_admission",
    "missing_tlc_lineage",
    "missing_evl_evidence",
    "missing_tpa_evidence",
    "missing_cde_decision",
    "missing_sel_linkage",
    "broken_lin_lineage",
    "rep_replay_mismatch",
    "missing_obs_telemetry",
    "slo_freeze_burn_block",
    "missing_pra",
    "missing_pol",
    "schema_weakening",
    "eval_removal",
    "authority_drift_phrase",
)


@dataclass(frozen=True)
class RFXChaosCase:
    """A single chaos scenario.

    ``invoke`` is a no-arg callable that performs the bad-state invocation
    against a guard. The case passes only when ``invoke`` raises an
    exception whose stringified message contains at least one of the
    declared ``expected_reason_codes``.
    """

    name: str
    expected_reason_codes: tuple[str, ...]
    invoke: Callable[[], Any]
    notes: str | None = None


@dataclass
class RFXChaosCaseResult:
    """Per-case execution result captured in the campaign record."""

    name: str
    expected_reason_codes: tuple[str, ...]
    raised: bool
    reason_code_matched: bool
    matched_reason_code: str | None
    error_class: str | None
    error_message: str | None

    def to_artifact(self) -> dict[str, Any]:
        return {
            "artifact_type": "rfx_chaos_case_result",
            "schema_version": "1.0.0",
            "case_name": self.name,
            "expected_reason_codes": list(self.expected_reason_codes),
            "raised": self.raised,
            "reason_code_matched": self.reason_code_matched,
            "matched_reason_code": self.matched_reason_code,
            "error_class": self.error_class,
            "error_message": self.error_message,
            "result": "blocked" if (self.raised and self.reason_code_matched) else "fail_open",
        }


def _stable_id(payload: Any, *, prefix: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _run_case(case: RFXChaosCase) -> RFXChaosCaseResult:
    try:
        case.invoke()
    except BaseException as exc:  # noqa: BLE001 - chaos case asserts any block path
        message = str(exc)
        matched = next(
            (code for code in case.expected_reason_codes if code and code in message),
            None,
        )
        return RFXChaosCaseResult(
            name=case.name,
            expected_reason_codes=case.expected_reason_codes,
            raised=True,
            reason_code_matched=matched is not None,
            matched_reason_code=matched,
            error_class=type(exc).__name__,
            error_message=message,
        )
    return RFXChaosCaseResult(
        name=case.name,
        expected_reason_codes=case.expected_reason_codes,
        raised=False,
        reason_code_matched=False,
        matched_reason_code=None,
        error_class=None,
        error_message=None,
    )


def run_rfx_chaos_campaign(
    *,
    cases: list[RFXChaosCase],
    required_scenarios: tuple[str, ...] = REQUIRED_CHAOS_SCENARIOS,
) -> dict[str, Any]:
    """Run the supplied chaos cases and return a campaign record.

    Fails closed with:

    * ``rfx_chaos_campaign_incomplete`` when ``cases`` does not cover every
      scenario in ``required_scenarios``.
    * ``rfx_chaos_case_failed_open`` when any case did not raise.
    * ``rfx_chaos_reason_code_missing`` when a case raised but the
      exception did not carry a recognized reason code.
    * ``rfx_chaos_expected_block_missing`` when a case declares no
      expected reason codes.
    """
    if not isinstance(cases, list) or not cases:
        raise RFXChaosCampaignError(
            "rfx_chaos_campaign_incomplete: cases list absent or empty"
        )

    declared_names = {c.name for c in cases if isinstance(c, RFXChaosCase)}
    missing = sorted(set(required_scenarios) - declared_names)
    if missing:
        raise RFXChaosCampaignError(
            f"rfx_chaos_campaign_incomplete: required scenarios missing from campaign: {missing}"
        )

    results: list[RFXChaosCaseResult] = []
    failures: list[str] = []
    for case in cases:
        if not isinstance(case, RFXChaosCase):
            raise RFXChaosCampaignError(
                "rfx_chaos_campaign_incomplete: non-RFXChaosCase entry in cases list"
            )
        if not case.expected_reason_codes:
            failures.append(
                f"rfx_chaos_expected_block_missing: case {case.name!r} declares no expected reason codes"
            )
            continue
        result = _run_case(case)
        results.append(result)
        if not result.raised:
            failures.append(
                f"rfx_chaos_case_failed_open: case {case.name!r} did not block — "
                f"chaos input passed through guard"
            )
            continue
        if not result.reason_code_matched:
            failures.append(
                f"rfx_chaos_reason_code_missing: case {case.name!r} raised "
                f"{result.error_class} but message did not contain any of "
                f"{list(case.expected_reason_codes)}"
            )

    if failures:
        raise RFXChaosCampaignError("; ".join(failures))

    record = {
        "artifact_type": "rfx_chaos_campaign_record",
        "schema_version": "1.0.0",
        "case_count": len(results),
        "blocked_count": sum(1 for r in results if r.raised and r.reason_code_matched),
        "results": [r.to_artifact() for r in results],
        "covered_scenarios": sorted(declared_names),
    }
    record["campaign_id"] = _stable_id(
        {"covered": record["covered_scenarios"], "case_count": record["case_count"]},
        prefix="rfx-chaos",
    )
    return record


__all__ = [
    "REQUIRED_CHAOS_SCENARIOS",
    "RFXChaosCampaignError",
    "RFXChaosCase",
    "RFXChaosCaseResult",
    "run_rfx_chaos_campaign",
]
