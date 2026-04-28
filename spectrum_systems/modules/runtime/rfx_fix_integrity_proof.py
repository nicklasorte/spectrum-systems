"""RFX fix-integrity proof — RFX-05.

Verifies that an RFX fix preserves protected guarantees before the fix may
proceed toward closure / evidence-package review. Canonical authority for
schema, test, eval, replay, lineage, observability, evidence-package
composition, and registry ownership remains with the systems recorded in
``docs/architecture/system_registry.md``. This module is a non-owning
phase-label support helper: it interprets the supplied evidence snapshots and
emits deterministic reason codes when any protected guarantee has weakened.

Required input shapes (each is a ``dict`` with ``before`` / ``after`` numeric
or boolean snapshots; values may be omitted when the dimension is irrelevant):

  * ``schema_coverage``                    — schema coverage score / count
  * ``test_coverage``                      — test counts or coverage fraction
  * ``eval_coverage``                      — required eval-case set or coverage fraction
  * ``replay_integrity``                   — replay-match flag or replay-pass count
  * ``lineage_continuity``                 — lineage authenticity flag / link count
  * ``obs_slo_evidence``                   — OBS+SLO evidence completeness / posture
  * ``certification_evidence_path``        — evidence-package gate composition snapshot
  * ``authority_boundaries``               — registry-ownership snapshot

Reason codes:

  * ``rfx_schema_weakened``
  * ``rfx_test_coverage_reduced``
  * ``rfx_eval_gap_introduced``
  * ``rfx_replay_regression``
  * ``rfx_lineage_break``
  * ``rfx_obs_slo_regression``
  * ``rfx_certification_evidence_path_weakened``
  * ``rfx_authority_boundary_regression``

All failures are aggregated and emitted before raising so callers receive a
complete picture rather than the first weakening only.
"""

from __future__ import annotations

from typing import Any


class RFXFixIntegrityProofError(ValueError):
    """Raised when an RFX fix integrity proof fails closed."""


def _is_present(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _compare_not_reduced(
    snapshot: dict[str, Any],
    *,
    keys: tuple[str, ...],
) -> tuple[float | None, float | None]:
    """Return (before, after) numeric pair from a snapshot.

    Picks the first present numeric key from ``keys`` for the ``before`` and
    ``after`` halves independently. Returns ``(None, None)`` when either half
    is absent or non-numeric — callers translate that into the appropriate
    "missing snapshot" reason.
    """
    before_dict = snapshot.get("before") if isinstance(snapshot.get("before"), dict) else None
    after_dict = snapshot.get("after") if isinstance(snapshot.get("after"), dict) else None
    before = None
    after = None
    if before_dict is not None:
        for k in keys:
            n = _coerce_number(before_dict.get(k))
            if n is not None:
                before = n
                break
    if after_dict is not None:
        for k in keys:
            n = _coerce_number(after_dict.get(k))
            if n is not None:
                after = n
                break
    return before, after


def _check_schema(snapshot: dict[str, Any] | None, reasons: list[str]) -> None:
    if not _is_present(snapshot):
        reasons.append(
            "rfx_schema_weakened: schema_coverage snapshot absent — fix integrity proof cannot verify schema preservation"
        )
        return
    before, after = _compare_not_reduced(
        snapshot, keys=("coverage", "score", "count", "covered_fields")
    )
    if before is None or after is None:
        reasons.append(
            "rfx_schema_weakened: schema_coverage snapshot missing before/after values"
        )
        return
    if after < before:
        reasons.append(
            f"rfx_schema_weakened: schema coverage reduced before={before!r} after={after!r}"
        )


def _check_tests(snapshot: dict[str, Any] | None, reasons: list[str]) -> None:
    if not _is_present(snapshot):
        reasons.append(
            "rfx_test_coverage_reduced: test_coverage snapshot absent — fix integrity proof cannot verify test preservation"
        )
        return
    before, after = _compare_not_reduced(
        snapshot, keys=("coverage", "count", "passing_count", "test_count")
    )
    if before is None or after is None:
        reasons.append(
            "rfx_test_coverage_reduced: test_coverage snapshot missing before/after values"
        )
        return
    if after < before:
        reasons.append(
            f"rfx_test_coverage_reduced: test coverage reduced before={before!r} after={after!r}"
        )


def _check_evals(snapshot: dict[str, Any] | None, reasons: list[str]) -> None:
    if not _is_present(snapshot):
        reasons.append(
            "rfx_eval_gap_introduced: eval_coverage snapshot absent — fix integrity proof cannot verify eval preservation"
        )
        return
    before_dict = snapshot.get("before") if isinstance(snapshot.get("before"), dict) else {}
    after_dict = snapshot.get("after") if isinstance(snapshot.get("after"), dict) else {}
    before_cases = before_dict.get("required_cases") if isinstance(before_dict.get("required_cases"), list) else None
    after_cases = after_dict.get("required_cases") if isinstance(after_dict.get("required_cases"), list) else None
    if before_cases is not None and after_cases is not None:
        before_set = {str(c) for c in before_cases if isinstance(c, str)}
        after_set = {str(c) for c in after_cases if isinstance(c, str)}
        removed = sorted(before_set - after_set)
        if removed:
            reasons.append(
                f"rfx_eval_gap_introduced: required eval cases removed: {removed}"
            )
            return
    before, after = _compare_not_reduced(
        snapshot, keys=("coverage", "case_count", "count")
    )
    if before is None or after is None:
        reasons.append(
            "rfx_eval_gap_introduced: eval_coverage snapshot missing before/after values"
        )
        return
    if after < before:
        reasons.append(
            f"rfx_eval_gap_introduced: eval coverage reduced before={before!r} after={after!r}"
        )


def _check_replay(snapshot: dict[str, Any] | None, reasons: list[str]) -> None:
    if not _is_present(snapshot):
        reasons.append(
            "rfx_replay_regression: replay_integrity snapshot absent — fix integrity proof cannot verify replay preservation"
        )
        return
    before_dict = snapshot.get("before") if isinstance(snapshot.get("before"), dict) else {}
    after_dict = snapshot.get("after") if isinstance(snapshot.get("after"), dict) else {}
    before_match = _coerce_bool(before_dict.get("match"))
    after_match = _coerce_bool(after_dict.get("match"))
    if before_match is True and after_match is not True:
        reasons.append(
            f"rfx_replay_regression: replay match regressed before=True after={after_match!r}"
        )
        return
    before, after = _compare_not_reduced(
        snapshot, keys=("pass_count", "matching_count", "count")
    )
    if before is not None and after is not None and after < before:
        reasons.append(
            f"rfx_replay_regression: replay pass-count reduced before={before!r} after={after!r}"
        )


def _check_lineage(snapshot: dict[str, Any] | None, reasons: list[str]) -> None:
    if not _is_present(snapshot):
        reasons.append(
            "rfx_lineage_break: lineage_continuity snapshot absent — fix integrity proof cannot verify lineage preservation"
        )
        return
    before_dict = snapshot.get("before") if isinstance(snapshot.get("before"), dict) else {}
    after_dict = snapshot.get("after") if isinstance(snapshot.get("after"), dict) else {}
    before_auth = before_dict.get("authenticity")
    after_auth = after_dict.get("authenticity")
    if before_auth == "pass" and after_auth != "pass":
        reasons.append(
            f"rfx_lineage_break: lineage authenticity regressed before='pass' after={after_auth!r}"
        )
        return
    before, after = _compare_not_reduced(
        snapshot, keys=("link_count", "node_count", "edge_count")
    )
    if before is not None and after is not None and after < before:
        reasons.append(
            f"rfx_lineage_break: lineage link count reduced before={before!r} after={after!r}"
        )


def _check_obs_slo(snapshot: dict[str, Any] | None, reasons: list[str]) -> None:
    if not _is_present(snapshot):
        reasons.append(
            "rfx_obs_slo_regression: obs_slo_evidence snapshot absent — fix integrity proof cannot verify telemetry preservation"
        )
        return
    before_dict = snapshot.get("before") if isinstance(snapshot.get("before"), dict) else {}
    after_dict = snapshot.get("after") if isinstance(snapshot.get("after"), dict) else {}
    _PASSING = {"pass", "complete", "ok", "within_budget", "acceptable"}
    before_obs = before_dict.get("obs_completeness")
    after_obs = after_dict.get("obs_completeness")
    if before_obs in _PASSING and after_obs not in _PASSING:
        reasons.append(
            f"rfx_obs_slo_regression: OBS completeness regressed before={before_obs!r} after={after_obs!r}"
        )
        return
    before_slo = before_dict.get("slo_status")
    after_slo = after_dict.get("slo_status")
    if before_slo in _PASSING and after_slo not in _PASSING:
        reasons.append(
            f"rfx_obs_slo_regression: SLO posture regressed before={before_slo!r} after={after_slo!r}"
        )


def _check_certification_evidence_path(snapshot: dict[str, Any] | None, reasons: list[str]) -> None:
    if not _is_present(snapshot):
        reasons.append(
            "rfx_certification_evidence_path_weakened: certification_evidence_path snapshot absent — "
            "fix integrity proof cannot verify evidence-package gates"
        )
        return
    before_dict = snapshot.get("before") if isinstance(snapshot.get("before"), dict) else {}
    after_dict = snapshot.get("after") if isinstance(snapshot.get("after"), dict) else {}
    before_gates = before_dict.get("required_gates")
    after_gates = after_dict.get("required_gates")
    if isinstance(before_gates, list) and isinstance(after_gates, list):
        removed = sorted({str(g) for g in before_gates if isinstance(g, str)} - {str(g) for g in after_gates if isinstance(g, str)})
        if removed:
            reasons.append(
                f"rfx_certification_evidence_path_weakened: evidence-package gates removed: {removed}"
            )


def _check_authority(snapshot: dict[str, Any] | None, reasons: list[str]) -> None:
    if not _is_present(snapshot):
        reasons.append(
            "rfx_authority_boundary_regression: authority_boundaries snapshot absent — fix integrity proof cannot verify ownership preservation"
        )
        return
    before_dict = snapshot.get("before") if isinstance(snapshot.get("before"), dict) else {}
    after_dict = snapshot.get("after") if isinstance(snapshot.get("after"), dict) else {}
    before_owners = before_dict.get("ownership")
    after_owners = after_dict.get("ownership")
    if isinstance(before_owners, dict) and isinstance(after_owners, dict):
        for system, owner in before_owners.items():
            if after_owners.get(system) != owner:
                reasons.append(
                    f"rfx_authority_boundary_regression: ownership for {system!r} changed "
                    f"before={owner!r} after={after_owners.get(system)!r}"
                )


def assert_rfx_fix_integrity_proof(
    *,
    schema_coverage: dict[str, Any] | None,
    test_coverage: dict[str, Any] | None,
    eval_coverage: dict[str, Any] | None,
    replay_integrity: dict[str, Any] | None,
    lineage_continuity: dict[str, Any] | None,
    obs_slo_evidence: dict[str, Any] | None,
    certification_evidence_path: dict[str, Any] | None,
    authority_boundaries: dict[str, Any] | None,
) -> dict[str, Any]:
    """Verify that a fix preserves all protected guarantees.

    Returns a non-owning ``rfx_fix_integrity_proof_record`` artifact when the
    fix is integrity-preserving. Raises :class:`RFXFixIntegrityProofError`
    with all aggregated reason codes when any guarantee has weakened.
    """
    reasons: list[str] = []

    _check_schema(schema_coverage, reasons)
    _check_tests(test_coverage, reasons)
    _check_evals(eval_coverage, reasons)
    _check_replay(replay_integrity, reasons)
    _check_lineage(lineage_continuity, reasons)
    _check_obs_slo(obs_slo_evidence, reasons)
    _check_certification_evidence_path(certification_evidence_path, reasons)
    _check_authority(authority_boundaries, reasons)

    if reasons:
        raise RFXFixIntegrityProofError("; ".join(reasons))

    return {
        "artifact_type": "rfx_fix_integrity_proof_record",
        "schema_version": "1.0.0",
        "checks": [
            "schema_coverage",
            "test_coverage",
            "eval_coverage",
            "replay_integrity",
            "lineage_continuity",
            "obs_slo_evidence",
            "certification_evidence_path",
            "authority_boundaries",
        ],
        "result": "preserved",
    }


__all__ = [
    "RFXFixIntegrityProofError",
    "assert_rfx_fix_integrity_proof",
]
