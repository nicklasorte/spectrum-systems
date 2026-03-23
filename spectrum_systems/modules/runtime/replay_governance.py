"""Replay Governance Gate (BY) — BAA Control Loop Integration.

Promotes replay from an advisory monitoring signal into an enforceable
governance gate.  A replay governance decision can stop, quarantine, or
force review of downstream execution.

BAA additions
-------------
- Control chain integration: consistency_sli thresholds drive system_response.
- Trace + provenance linkage: trace_id, original_run_id, replay_run_id,
  replay_artifact_ids required when replay was consumed.
- Replay independence enforcement: replay_validation_mode field.
- Environment reproducibility contract: environment_context (matlab_release,
  runtime_version, platform, seed_rng_state).
- SLO + error budget hook: replay_drift_event, replay_failure_rate logging.
- Decision artifact hardening: replay_decision_status (pass | drift |
  indeterminate) on every governed artifact.
- Observability events: REPLAY_START, REPLAY_COMPLETE, REPLAY_DRIFT_DETECTED.

Design principles
-----------------
- Fail closed:  unknown, malformed, or semantically invalid replay inputs
  never degrade to allow.
- Deterministic enforcement:  decisions depend only on structured fields,
  never on free-form text or heuristics.
- Structured artifacts first:  all outputs are schema-validated governed
  artifacts.
- Governance before convenience:  if replay says trust is compromised the
  system acts on that signal.
- No hidden fallbacks:  every code path emits an explicit, traceable
  decision.

Public API
----------
build_replay_governance_decision(...)         → replay_governance_decision dict
summarize_replay_governance_decision(...)     → concise machine-readable summary
should_block_from_replay_governance(...)      → bool
should_require_review_from_replay_governance(...) → bool
should_quarantine_from_replay_governance(...) → bool
merge_system_responses(responses)             → str  (strictest wins)

Internal helpers (exported for testing)
----------------------------------------
_validate_replay_analysis(replay_decision_analysis)  → dict
_validate_governance_policy(policy)                  → dict
_derive_replay_governance_decision(...)              → dict
_replay_status_to_decision_status(replay_status)     → str
_apply_sli_thresholds(...)                           → dict
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION: str = "1.0.0"
ARTIFACT_TYPE: str = "replay_governance_decision"

# Replay status values (mirrors BQ consistency statuses)
REPLAY_STATUS_CONSISTENT: str = "consistent"
REPLAY_STATUS_DRIFTED: str = "drifted"
REPLAY_STATUS_INDETERMINATE: str = "indeterminate"

_KNOWN_REPLAY_STATUSES: frozenset = frozenset({
    REPLAY_STATUS_CONSISTENT,
    REPLAY_STATUS_DRIFTED,
    REPLAY_STATUS_INDETERMINATE,
})

# System response values — ordered from least to most severe
SYSTEM_RESPONSE_ALLOW: str = "allow"
SYSTEM_RESPONSE_REQUIRE_REVIEW: str = "require_review"
SYSTEM_RESPONSE_QUARANTINE: str = "quarantine"
SYSTEM_RESPONSE_BLOCK: str = "block"

_SYSTEM_RESPONSE_PRECEDENCE: Dict[str, int] = {
    SYSTEM_RESPONSE_ALLOW: 0,
    SYSTEM_RESPONSE_REQUIRE_REVIEW: 1,
    SYSTEM_RESPONSE_QUARANTINE: 2,
    SYSTEM_RESPONSE_BLOCK: 3,
}

_KNOWN_SYSTEM_RESPONSES: frozenset = frozenset(_SYSTEM_RESPONSE_PRECEDENCE.keys())

# Governance status values
GOVERNANCE_STATUS_OK: str = "ok"
GOVERNANCE_STATUS_INVALID_INPUT: str = "invalid_input"
GOVERNANCE_STATUS_POLICY_BLOCKED: str = "policy_blocked"

# Rationale codes
_RATIONALE_CONSISTENT: str = "replay_consistent"
_RATIONALE_DRIFTED: str = "replay_drifted"
_RATIONALE_INDETERMINATE: str = "replay_indeterminate"
_RATIONALE_MISSING_REQUIRED: str = "replay_missing_required"
_RATIONALE_INVALID_ARTIFACT: str = "replay_invalid_artifact"
_RATIONALE_UNKNOWN_STATUS: str = "replay_unknown_status"
_RATIONALE_NOT_REQUIRED: str = "replay_not_required"

# BAA: Replay decision status values (high-level outcome of replay governance)
REPLAY_DECISION_STATUS_PASS: str = "pass"
REPLAY_DECISION_STATUS_DRIFT: str = "drift"
REPLAY_DECISION_STATUS_INDETERMINATE: str = "indeterminate"

# BAA: Observability event types
EVENT_REPLAY_START: str = "REPLAY_START"
EVENT_REPLAY_COMPLETE: str = "REPLAY_COMPLETE"
EVENT_REPLAY_DRIFT_DETECTED: str = "REPLAY_DRIFT_DETECTED"

# BAA: Replay validation modes
REPLAY_VALIDATION_MODE_INDEPENDENT: str = "independent"
REPLAY_VALIDATION_MODE_SHARED: str = "shared"

# BAA: SLI threshold defaults for control chain policy
#   consistency_sli < REBUILD_THRESHOLD  → require_rebuild (block-equivalent)
#   consistency_sli < REVIEW_THRESHOLD   → require_review
_DEFAULT_SLI_REBUILD_THRESHOLD: float = 0.5
_DEFAULT_SLI_REVIEW_THRESHOLD: float = 0.8

# Schema path
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_GOVERNANCE_SCHEMA_PATH = _SCHEMA_DIR / "replay_governance_decision.schema.json"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------

class InvalidReplayGovernanceInputError(ValueError):
    """Raised when the replay_decision_analysis artifact is malformed, missing
    required fields, contains unknown status values, or has an SLI outside
    [0, 1].  This error always triggers fail-closed behavior (block)."""


class ReplayGovernancePolicyError(ValueError):
    """Raised when the governance_policy dict is invalid, missing required
    fields, or contains unsupported action values."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _load_governance_schema() -> Dict[str, Any]:
    return json.loads(_GOVERNANCE_SCHEMA_PATH.read_text(encoding="utf-8"))


def _severity_for_response(response: str) -> str:
    """Map system_response to severity level."""
    mapping = {
        SYSTEM_RESPONSE_ALLOW: "info",
        SYSTEM_RESPONSE_REQUIRE_REVIEW: "warning",
        SYSTEM_RESPONSE_QUARANTINE: "elevated",
        SYSTEM_RESPONSE_BLOCK: "critical",
    }
    return mapping.get(response, "critical")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_replay_analysis(replay_decision_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the replay_decision_analysis artifact from BQ.

    Checks that all required governance-critical fields are present, that the
    decision_consistency.status is a known value, and that reproducibility_score
    is in [0, 1].

    Returns the validated artifact dict unchanged.

    Raises
    ------
    InvalidReplayGovernanceInputError
        If any required field is missing, contains an unknown value, or the
        score is out of range.  Fail-closed — never silently passes.
    """
    if not isinstance(replay_decision_analysis, dict):
        raise InvalidReplayGovernanceInputError(
            "replay_decision_analysis must be a dict; "
            f"got {type(replay_decision_analysis).__name__}"
        )

    # Required top-level fields
    required_fields = ["analysis_id", "decision_consistency", "reproducibility_score"]
    missing = [f for f in required_fields if f not in replay_decision_analysis]
    if missing:
        raise InvalidReplayGovernanceInputError(
            f"replay_decision_analysis missing required fields: {missing}"
        )

    # decision_consistency must be a dict with a 'status' field
    dc = replay_decision_analysis.get("decision_consistency")
    if not isinstance(dc, dict):
        raise InvalidReplayGovernanceInputError(
            "replay_decision_analysis.decision_consistency must be a dict"
        )

    status = dc.get("status")
    if status not in _KNOWN_REPLAY_STATUSES:
        raise InvalidReplayGovernanceInputError(
            f"replay_decision_analysis.decision_consistency.status is unknown or missing: "
            f"'{status}'. Known values: {sorted(_KNOWN_REPLAY_STATUSES)}"
        )

    # reproducibility_score must be a number in [0, 1]
    score = replay_decision_analysis.get("reproducibility_score")
    if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 1.0):
        raise InvalidReplayGovernanceInputError(
            f"replay_decision_analysis.reproducibility_score must be a number in [0, 1]; "
            f"got {score!r}"
        )

    return replay_decision_analysis


def _validate_governance_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a governance policy dict.

    Checks required fields and that all action values belong to their allowed
    enum sets.

    Returns the validated policy dict unchanged.

    Raises
    ------
    ReplayGovernancePolicyError
        If any required field is missing or contains an unsupported value.
    """
    if not isinstance(policy, dict):
        raise ReplayGovernancePolicyError(
            f"governance_policy must be a dict; got {type(policy).__name__}"
        )

    required = [
        "policy_name",
        "policy_version",
        "drift_action",
        "indeterminate_action",
        "missing_replay_action",
        "require_replay",
    ]
    missing = [f for f in required if f not in policy]
    if missing:
        raise ReplayGovernancePolicyError(
            f"governance_policy missing required fields: {missing}"
        )

    drift_action = policy["drift_action"]
    if drift_action not in {SYSTEM_RESPONSE_QUARANTINE, SYSTEM_RESPONSE_BLOCK}:
        raise ReplayGovernancePolicyError(
            f"governance_policy.drift_action must be one of "
            f"[quarantine, block]; got '{drift_action}'"
        )

    indeterminate_action = policy["indeterminate_action"]
    if indeterminate_action not in {SYSTEM_RESPONSE_REQUIRE_REVIEW, SYSTEM_RESPONSE_BLOCK}:
        raise ReplayGovernancePolicyError(
            f"governance_policy.indeterminate_action must be one of "
            f"[require_review, block]; got '{indeterminate_action}'"
        )

    missing_replay_action = policy["missing_replay_action"]
    if missing_replay_action not in {
        SYSTEM_RESPONSE_ALLOW,
        SYSTEM_RESPONSE_REQUIRE_REVIEW,
        SYSTEM_RESPONSE_BLOCK,
    }:
        raise ReplayGovernancePolicyError(
            f"governance_policy.missing_replay_action must be one of "
            f"[allow, require_review, block]; got '{missing_replay_action}'"
        )

    if not isinstance(policy["require_replay"], bool):
        raise ReplayGovernancePolicyError(
            f"governance_policy.require_replay must be a bool; "
            f"got {type(policy['require_replay']).__name__}"
        )

    # BAA: Validate optional SLI threshold fields when present
    rebuild_threshold = policy.get("consistency_sli_rebuild_threshold")
    if rebuild_threshold is not None:
        if not isinstance(rebuild_threshold, (int, float)) or not (0.0 <= float(rebuild_threshold) <= 1.0):
            raise ReplayGovernancePolicyError(
                f"governance_policy.consistency_sli_rebuild_threshold must be a number in [0, 1]; "
                f"got {rebuild_threshold!r}"
            )

    review_threshold = policy.get("consistency_sli_review_threshold")
    if review_threshold is not None:
        if not isinstance(review_threshold, (int, float)) or not (0.0 <= float(review_threshold) <= 1.0):
            raise ReplayGovernancePolicyError(
                f"governance_policy.consistency_sli_review_threshold must be a number in [0, 1]; "
                f"got {review_threshold!r}"
            )

    return policy


def _replay_status_to_decision_status(replay_status: Optional[str]) -> str:
    """BAA: Map BQ replay_status to the high-level replay_decision_status.

    Parameters
    ----------
    replay_status:
        One of 'consistent', 'drifted', 'indeterminate', or None.

    Returns
    -------
    str
        One of REPLAY_DECISION_STATUS_PASS, REPLAY_DECISION_STATUS_DRIFT,
        REPLAY_DECISION_STATUS_INDETERMINATE.  Defaults to 'indeterminate'
        for None or unknown values (fail-closed).
    """
    mapping: Dict[Optional[str], str] = {
        REPLAY_STATUS_CONSISTENT: REPLAY_DECISION_STATUS_PASS,
        REPLAY_STATUS_DRIFTED: REPLAY_DECISION_STATUS_DRIFT,
        REPLAY_STATUS_INDETERMINATE: REPLAY_DECISION_STATUS_INDETERMINATE,
    }
    return mapping.get(replay_status, REPLAY_DECISION_STATUS_INDETERMINATE)


def _apply_sli_thresholds(
    replay_status: str,
    replay_consistency_sli: float,
    policy: Dict[str, Any],
    base_decision: Dict[str, Any],
) -> Dict[str, Any]:
    """BAA: Apply SLI threshold escalation on top of the base governance decision.

    When replay_status is consistent but the SLI is below configured thresholds,
    the system_response is escalated:
      - sli < rebuild_threshold → block (require_rebuild equivalent)
      - sli < review_threshold  → require_review

    Parameters
    ----------
    replay_status:
        Replay consistency status string.
    replay_consistency_sli:
        SLI score in [0, 1].
    policy:
        Validated governance policy dict.
    base_decision:
        The decision dict produced by :func:`_derive_replay_governance_decision`.

    Returns
    -------
    Updated decision dict (may escalate system_response and severity).
    """
    # SLI thresholds only apply when we have a concrete SLI score
    if not isinstance(replay_consistency_sli, (int, float)):
        return base_decision

    rebuild_threshold = float(
        policy.get("consistency_sli_rebuild_threshold", _DEFAULT_SLI_REBUILD_THRESHOLD)
    )
    review_threshold = float(
        policy.get("consistency_sli_review_threshold", _DEFAULT_SLI_REVIEW_THRESHOLD)
    )

    sli = float(replay_consistency_sli)

    # Only escalate if the base decision is 'allow' (threshold escalation
    # applies to consistent replays whose SLI score is below acceptable levels)
    current_response = base_decision.get("system_response", SYSTEM_RESPONSE_ALLOW)
    if current_response != SYSTEM_RESPONSE_ALLOW:
        return base_decision

    if sli < rebuild_threshold:
        escalated = dict(base_decision)
        escalated["system_response"] = SYSTEM_RESPONSE_BLOCK
        escalated["severity"] = "critical"
        escalated["rationale"] = (
            f"{base_decision.get('rationale', '')} "
            f"SLI {sli:.3f} is below rebuild threshold {rebuild_threshold:.3f}: "
            "blocking (require_rebuild)."
        ).strip()
        return escalated
    elif sli < review_threshold:
        escalated = dict(base_decision)
        escalated["system_response"] = SYSTEM_RESPONSE_REQUIRE_REVIEW
        escalated["severity"] = "warning"
        escalated["rationale"] = (
            f"{base_decision.get('rationale', '')} "
            f"SLI {sli:.3f} is below review threshold {review_threshold:.3f}: "
            "human review required."
        ).strip()
        return escalated

    return base_decision


# ---------------------------------------------------------------------------
# Decision derivation
# ---------------------------------------------------------------------------

def _derive_replay_governance_decision(
    replay_status: str,
    replay_consistency_sli: float,
    policy: Dict[str, Any],
    replay_required: bool,
) -> Dict[str, Any]:
    """Deterministically map replay result + policy to a governance decision dict.

    BAA: Applies SLI threshold escalation (consistency_sli_rebuild_threshold,
    consistency_sli_review_threshold) after the base status-driven decision.

    Parameters
    ----------
    replay_status:
        One of REPLAY_STATUS_CONSISTENT, REPLAY_STATUS_DRIFTED,
        REPLAY_STATUS_INDETERMINATE.
    replay_consistency_sli:
        Reproducibility score in [0, 1].
    policy:
        Validated governance policy dict.
    replay_required:
        Whether replay was explicitly required (from caller or policy).

    Returns
    -------
    dict with keys: system_response, severity, replay_governed,
    rationale_code, rationale.
    """
    if replay_status == REPLAY_STATUS_CONSISTENT:
        base = {
            "system_response": SYSTEM_RESPONSE_ALLOW,
            "severity": "info",
            "replay_governed": True,
            "rationale_code": _RATIONALE_CONSISTENT,
            "rationale": (
                "Replay is consistent with the original execution. "
                "Governed outputs may proceed."
            ),
        }
        # BAA: Apply SLI threshold escalation only for consistent (allow) base decisions
        return _apply_sli_thresholds(replay_status, replay_consistency_sli, policy, base)

    if replay_status == REPLAY_STATUS_DRIFTED:
        response = policy["drift_action"]
        severity = "critical" if response == SYSTEM_RESPONSE_BLOCK else "elevated"
        return {
            "system_response": response,
            "severity": severity,
            "replay_governed": True,
            "rationale_code": _RATIONALE_DRIFTED,
            "rationale": (
                "Replay drift was detected. "
                "Governed outputs cannot be promoted automatically."
            ),
        }

    if replay_status == REPLAY_STATUS_INDETERMINATE:
        response = policy["indeterminate_action"]
        return {
            "system_response": response,
            "severity": "warning",
            "replay_governed": True,
            "rationale_code": _RATIONALE_INDETERMINATE,
            "rationale": (
                "Replay result was indeterminate. "
                "Decision reproducibility could not be confirmed."
            ),
        }

    # Should not reach here if _validate_replay_analysis ran first, but
    # kept as an explicit fail-closed path for any novel unknown status.
    return {
        "system_response": SYSTEM_RESPONSE_BLOCK,
        "severity": "critical",
        "replay_governed": True,
        "rationale_code": _RATIONALE_UNKNOWN_STATUS,
        "rationale": (
            f"Replay status '{replay_status}' is not a recognised governance value. "
            "Blocking per fail-closed policy."
        ),
    }


# ---------------------------------------------------------------------------
# Artifact builder
# ---------------------------------------------------------------------------

def build_replay_governance_decision(
    replay_decision_analysis: Optional[Dict[str, Any]],
    *,
    run_id: str,
    replay_analysis_artifact_id: Optional[str] = None,
    governance_policy: Optional[Dict[str, Any]] = None,
    require_replay: bool = False,
    trace_id: Optional[str] = None,
    original_run_id: Optional[str] = None,
    replay_run_id: Optional[str] = None,
    replay_artifact_ids: Optional[List[str]] = None,
    replay_validation_mode: Optional[str] = None,
    environment_context: Optional[Dict[str, Any]] = None,
    evaluated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a governed ``replay_governance_decision`` artifact.

    This is the primary entry point for the BY Replay Governance Gate (BAA).

    Parameters
    ----------
    replay_decision_analysis:
        The BQ ``replay_decision_analysis`` artifact.  May be ``None`` if no
        replay was run.
    run_id:
        Pipeline run identifier (required).
    replay_analysis_artifact_id:
        Override the artifact ID extracted from the analysis artifact.  Useful
        when the caller already holds the ID.
    governance_policy:
        Custom governance policy.  If ``None`` the strict default is used.
    require_replay:
        When ``True`` the absence of a replay artifact is treated as a policy
        violation, regardless of ``policy.require_replay``.
    trace_id:
        Trace identifier for correlation (BAA).  Auto-extracted from the
        analysis artifact when not provided.  Required in schema when replay
        was consumed.
    original_run_id:
        BAA: Identifier of the original pipeline run that was replayed.
        Optional; included in artifact when provided.
    replay_run_id:
        BAA: Identifier of the replay pipeline run.  Auto-extracted from
        ``replay_decision_analysis["replay_result_id"]`` when not provided.
    replay_artifact_ids:
        BAA: List of artifact IDs produced during the replay run.  Optional.
    replay_validation_mode:
        BAA: ``'independent'`` or ``'shared'``.  Enforced for high-severity
        decisions — if a critical decision is made and mode is ``'shared'``
        the response escalates to block.
    environment_context:
        BAA: Environment reproducibility contract dict (matlab_release,
        runtime_version, platform, seed_rng_state).
    evaluated_at:
        Override evaluation timestamp.  Defaults to now.

    Returns
    -------
    dict
        A schema-validated ``replay_governance_decision`` artifact.

    Raises
    ------
    InvalidReplayGovernanceInputError
        If the replay artifact is present but malformed.
    ReplayGovernancePolicyError
        If the governance_policy is invalid.
    ValueError
        If schema validation of the produced artifact fails (internal error).
    """
    ts = evaluated_at or _now_iso()

    # BAA: Emit REPLAY_START observability event
    _emit_observability_event(EVENT_REPLAY_START, run_id=run_id, trace_id=trace_id)

    # Resolve and validate policy
    effective_policy: Dict[str, Any]
    if governance_policy is None:
        raise ReplayGovernancePolicyError(
            "governance_policy is required; implicit default policy is disallowed."
        )
    effective_policy = _validate_governance_policy(governance_policy)

    # Determine whether replay is required from any source
    replay_is_required: bool = require_replay or bool(effective_policy.get("require_replay", False))

    # ------------------------------------------------------------------ #
    # Case A: No replay artifact provided
    # ------------------------------------------------------------------ #
    if replay_decision_analysis is None:
        artifact_id = None
        replay_status_val: Optional[str] = None
        sli_val: Optional[float] = None

        if replay_is_required:
            missing_action = effective_policy["missing_replay_action"]
            decision_dict = {
                "system_response": missing_action,
                "severity": _severity_for_response(missing_action),
                "replay_governed": True,
                "rationale_code": _RATIONALE_MISSING_REQUIRED,
                "rationale": (
                    "Replay artifact is required by policy but was not provided. "
                    f"Applying missing_replay_action='{missing_action}'."
                ),
            }
            gov_status = (
                GOVERNANCE_STATUS_POLICY_BLOCKED
                if missing_action != SYSTEM_RESPONSE_ALLOW
                else GOVERNANCE_STATUS_OK
            )
            enforcement_reason = {
                "summary": (
                    f"Replay governance applied missing_replay_action='{missing_action}' "
                    "because replay is required but absent."
                ),
                "details": [
                    "replay_artifact=absent",
                    "require_replay=true",
                    f"policy.missing_replay_action={missing_action}",
                ],
            }
        else:
            decision_dict = {
                "system_response": SYSTEM_RESPONSE_ALLOW,
                "severity": "info",
                "replay_governed": False,
                "rationale_code": _RATIONALE_NOT_REQUIRED,
                "rationale": (
                    "Replay artifact was not provided and replay is not required. "
                    "Governance gate is bypassed."
                ),
            }
            gov_status = GOVERNANCE_STATUS_OK
            enforcement_reason = {
                "summary": "Replay governance bypassed: replay not provided and not required.",
                "details": [
                    "replay_artifact=absent",
                    "require_replay=false",
                ],
            }

        artifact = _build_artifact_dict(
            replay_analysis_artifact_id=artifact_id,
            run_id=run_id,
            evaluated_at=ts,
            replay_status=replay_status_val,
            replay_consistency_sli=sli_val,
            effective_policy=effective_policy,
            decision_dict=decision_dict,
            enforcement_reason=enforcement_reason,
            gov_status=gov_status,
            trace_id=trace_id,
            original_run_id=original_run_id,
            replay_run_id=replay_run_id,
            replay_artifact_ids=replay_artifact_ids,
            replay_decision_status=None,
            replay_validation_mode=replay_validation_mode,
            environment_context=environment_context,
        )
        _validate_or_raise(artifact)

        _emit_observability_event(
            EVENT_REPLAY_COMPLETE,
            run_id=run_id,
            trace_id=trace_id,
            replay_decision_status=None,
            system_response=decision_dict.get("system_response"),
        )
        _log_governance_event(artifact, run_id, trace_id)
        return artifact

    # ------------------------------------------------------------------ #
    # Case B: Replay artifact provided — validate it (fail closed)
    # ------------------------------------------------------------------ #
    try:
        _validate_replay_analysis(replay_decision_analysis)
    except InvalidReplayGovernanceInputError as exc:
        decision_dict = {
            "system_response": SYSTEM_RESPONSE_BLOCK,
            "severity": "critical",
            "replay_governed": True,
            "rationale_code": _RATIONALE_INVALID_ARTIFACT,
            "rationale": (
                f"Replay artifact failed validation and cannot be trusted: {exc}. "
                "Blocking per fail-closed policy."
            ),
        }
        enforcement_reason = {
            "summary": "Replay governance blocked: replay artifact is malformed.",
            "details": [
                f"validation_error={exc}",
                "fail_closed_policy=block_on_invalid_artifact",
            ],
        }
        artifact_id = (
            replay_analysis_artifact_id
            or (replay_decision_analysis.get("analysis_id") if isinstance(replay_decision_analysis, dict) else None)
        )
        # BAA: Auto-extract correlation fields from the (potentially invalid) analysis dict
        invalid_trace_id = trace_id or (
            replay_decision_analysis.get("trace_id") if isinstance(replay_decision_analysis, dict) else None
        )
        invalid_replay_run_id = replay_run_id or (
            replay_decision_analysis.get("replay_result_id") if isinstance(replay_decision_analysis, dict) else None
        )
        artifact = _build_artifact_dict(
            replay_analysis_artifact_id=artifact_id,
            run_id=run_id,
            evaluated_at=ts,
            replay_status=None,
            replay_consistency_sli=None,
            effective_policy=effective_policy,
            decision_dict=decision_dict,
            enforcement_reason=enforcement_reason,
            gov_status=GOVERNANCE_STATUS_INVALID_INPUT,
            trace_id=invalid_trace_id,
            original_run_id=original_run_id,
            replay_run_id=invalid_replay_run_id,
            replay_artifact_ids=replay_artifact_ids,
            replay_decision_status=REPLAY_DECISION_STATUS_INDETERMINATE if artifact_id else None,
            replay_validation_mode=replay_validation_mode,
            environment_context=environment_context,
        )
        _validate_or_raise(artifact)
        _emit_observability_event(
            EVENT_REPLAY_COMPLETE,
            run_id=run_id,
            trace_id=invalid_trace_id,
            replay_decision_status=REPLAY_DECISION_STATUS_INDETERMINATE if artifact_id else None,
            system_response=SYSTEM_RESPONSE_BLOCK,
        )
        _log_governance_event(artifact, run_id, invalid_trace_id)
        return artifact

    # Extract governance-critical values from the validated artifact
    dc = replay_decision_analysis["decision_consistency"]
    replay_status: str = dc["status"]
    score: float = float(replay_decision_analysis["reproducibility_score"])
    artifact_id = (
        replay_analysis_artifact_id
        or replay_decision_analysis.get("analysis_id")
    )

    # BAA: Auto-extract trace_id and replay_run_id from analysis when not provided
    effective_trace_id = trace_id or replay_decision_analysis.get("trace_id")
    effective_replay_run_id = replay_run_id or replay_decision_analysis.get("replay_result_id")

    # ------------------------------------------------------------------ #
    # Case C: Derive decision from replay status + policy
    # ------------------------------------------------------------------ #
    decision_dict = _derive_replay_governance_decision(
        replay_status=replay_status,
        replay_consistency_sli=score,
        policy=effective_policy,
        replay_required=replay_is_required,
    )

    # BAA: Enforce replay_validation_mode for high-severity decisions.
    # If system_response would be critical and replay_validation_mode is 'shared',
    # escalate to block to enforce independence requirement.
    response = decision_dict["system_response"]
    severity = decision_dict.get("severity", "info")
    if (
        replay_validation_mode == REPLAY_VALIDATION_MODE_SHARED
        and severity in {"critical", "elevated"}
        and _SYSTEM_RESPONSE_PRECEDENCE.get(response, 0) >= _SYSTEM_RESPONSE_PRECEDENCE[SYSTEM_RESPONSE_QUARANTINE]
    ):
        decision_dict = dict(decision_dict)
        decision_dict["system_response"] = SYSTEM_RESPONSE_BLOCK
        decision_dict["severity"] = "critical"
        decision_dict["rationale"] = (
            decision_dict.get("rationale", "")
            + " Replay independence not satisfied (shared mode): blocking per BAA policy."
        ).strip()
        response = SYSTEM_RESPONSE_BLOCK

    gov_status = (
        GOVERNANCE_STATUS_POLICY_BLOCKED
        if response not in {SYSTEM_RESPONSE_ALLOW}
        else GOVERNANCE_STATUS_OK
    )

    enforcement_reason = _build_enforcement_reason(
        replay_status=replay_status,
        replay_consistency_sli=score,
        policy=effective_policy,
        system_response=response,
    )

    # BAA: Derive replay_decision_status from replay_status
    rds = _replay_status_to_decision_status(replay_status)

    artifact = _build_artifact_dict(
        replay_analysis_artifact_id=artifact_id,
        run_id=run_id,
        evaluated_at=ts,
        replay_status=replay_status,
        replay_consistency_sli=score,
        effective_policy=effective_policy,
        decision_dict=decision_dict,
        enforcement_reason=enforcement_reason,
        gov_status=gov_status,
        trace_id=effective_trace_id,
        original_run_id=original_run_id,
        replay_run_id=effective_replay_run_id,
        replay_artifact_ids=replay_artifact_ids,
        replay_decision_status=rds,
        replay_validation_mode=replay_validation_mode,
        environment_context=environment_context,
    )

    _validate_or_raise(artifact)

    # BAA: Emit drift event and REPLAY_DRIFT_DETECTED when drift is detected
    if rds == REPLAY_DECISION_STATUS_DRIFT:
        drift_event = _build_drift_event(
            run_id=run_id,
            trace_id=effective_trace_id,
            replay_decision_status=rds,
            replay_consistency_sli=score,
            drift_reason=decision_dict.get("rationale", "Drift detected"),
            evaluated_at=ts,
        )
        artifact["replay_drift_event"] = drift_event
        _emit_observability_event(
            EVENT_REPLAY_DRIFT_DETECTED,
            run_id=run_id,
            trace_id=effective_trace_id,
            replay_decision_status=rds,
            replay_consistency_sli=score,
            system_response=response,
        )
        # Re-validate after adding drift event
        _validate_or_raise(artifact)

    _emit_observability_event(
        EVENT_REPLAY_COMPLETE,
        run_id=run_id,
        trace_id=effective_trace_id,
        replay_decision_status=rds,
        system_response=response,
    )
    _log_governance_event(artifact, run_id, effective_trace_id)
    return artifact


# ---------------------------------------------------------------------------
# Internal artifact construction helpers
# ---------------------------------------------------------------------------

def _build_artifact_dict(
    *,
    replay_analysis_artifact_id: Optional[str],
    run_id: str,
    evaluated_at: str,
    replay_status: Optional[str],
    replay_consistency_sli: Optional[float],
    effective_policy: Dict[str, Any],
    decision_dict: Dict[str, Any],
    enforcement_reason: Dict[str, Any],
    gov_status: str,
    trace_id: Optional[str],
    original_run_id: Optional[str] = None,
    replay_run_id: Optional[str] = None,
    replay_artifact_ids: Optional[List[str]] = None,
    replay_decision_status: Optional[str] = None,
    replay_validation_mode: Optional[str] = None,
    environment_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    artifact: Dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "replay_analysis_artifact_id": replay_analysis_artifact_id,
        "run_id": run_id,
        "evaluated_at": evaluated_at,
        "replay_status": replay_status,
        "replay_consistency_sli": replay_consistency_sli,
        "governance_policy": dict(effective_policy),
        "decision": dict(decision_dict),
        "enforcement_reason": dict(enforcement_reason),
        "status": gov_status,
    }
    if trace_id is not None:
        artifact["trace_id"] = trace_id
    if original_run_id is not None:
        artifact["original_run_id"] = original_run_id
    if replay_run_id is not None:
        artifact["replay_run_id"] = replay_run_id
    if replay_artifact_ids is not None:
        artifact["replay_artifact_ids"] = list(replay_artifact_ids)
    if replay_decision_status is not None:
        artifact["replay_decision_status"] = replay_decision_status
    if replay_validation_mode is not None:
        artifact["replay_validation_mode"] = replay_validation_mode
    if environment_context is not None:
        artifact["environment_context"] = dict(environment_context)
    return artifact


def _build_drift_event(
    *,
    run_id: str,
    trace_id: Optional[str],
    replay_decision_status: str,
    replay_consistency_sli: Optional[float],
    drift_reason: str,
    evaluated_at: str,
) -> Dict[str, Any]:
    """BAA: Build a replay_drift_event structured dict for error budget tracking."""
    return {
        "event_type": EVENT_REPLAY_DRIFT_DETECTED,
        "run_id": run_id,
        "trace_id": trace_id,
        "replay_decision_status": replay_decision_status,
        "replay_consistency_sli": replay_consistency_sli,
        "drift_reason": drift_reason,
        "emitted_at": evaluated_at,
    }


def _emit_observability_event(
    event_type: str,
    *,
    run_id: str,
    trace_id: Optional[str],
    replay_decision_status: Optional[str] = None,
    replay_consistency_sli: Optional[float] = None,
    system_response: Optional[str] = None,
) -> None:
    """BAA: Emit a structured observability event to the logger."""
    extra: Dict[str, Any] = {
        "event": event_type,
        "run_id": run_id,
        "trace_id": trace_id,
    }
    if replay_decision_status is not None:
        extra["replay_decision_status"] = replay_decision_status
    if replay_consistency_sli is not None:
        extra["replay_consistency_sli"] = replay_consistency_sli
    if system_response is not None:
        extra["system_response"] = system_response

    if event_type == EVENT_REPLAY_DRIFT_DETECTED:
        logger.warning(event_type, extra=extra)
    else:
        logger.debug(event_type, extra=extra)


def _build_enforcement_reason(
    *,
    replay_status: str,
    replay_consistency_sli: float,
    policy: Dict[str, Any],
    system_response: str,
) -> Dict[str, Any]:
    if system_response == SYSTEM_RESPONSE_ALLOW:
        summary = "Replay governance: execution allowed; replay is consistent."
    elif system_response == SYSTEM_RESPONSE_REQUIRE_REVIEW:
        summary = "Replay governance escalated the run to require_review."
    elif system_response == SYSTEM_RESPONSE_QUARANTINE:
        summary = "Replay governance escalated the run to quarantine."
    else:
        summary = "Replay governance blocked the run."

    policy_key = f"policy.{replay_status}_action" if replay_status in {
        REPLAY_STATUS_DRIFTED, REPLAY_STATUS_INDETERMINATE
    } else "policy.missing_replay_action"
    if replay_status == REPLAY_STATUS_DRIFTED:
        action_value = policy.get("drift_action", "(unknown)")
    elif replay_status == REPLAY_STATUS_INDETERMINATE:
        action_value = policy.get("indeterminate_action", "(unknown)")
    else:
        action_value = "(n/a)"

    details = [
        f"replay_status={replay_status}",
        f"replay_consistency_sli={replay_consistency_sli}",
    ]
    if replay_status in {REPLAY_STATUS_DRIFTED, REPLAY_STATUS_INDETERMINATE}:
        details.append(f"{policy_key}={action_value}")

    return {"summary": summary, "details": details}


def _validate_or_raise(artifact: Dict[str, Any]) -> None:
    """Validate artifact against the governance schema; raise ValueError on failure."""
    try:
        schema = _load_governance_schema()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not load replay governance schema: {exc}") from exc

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(artifact))
    if errors:
        msgs = [
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in sorted(errors, key=lambda e: list(e.absolute_path))
        ]
        raise ValueError(
            f"replay_governance_decision artifact failed schema validation: {msgs}"
        )


def _log_governance_event(
    artifact: Dict[str, Any],
    run_id: str,
    trace_id: Optional[str],
) -> None:
    """Emit a structured log when replay governance escalates from allow."""
    decision = artifact.get("decision") or {}
    response = decision.get("system_response", SYSTEM_RESPONSE_ALLOW)
    rationale_code = decision.get("rationale_code", "")

    if response != SYSTEM_RESPONSE_ALLOW:
        logger.warning(
            "replay_governance_escalated",
            extra={
                "event": "replay_governance_escalated",
                "run_id": run_id,
                "trace_id": trace_id,
                "system_response": response,
                "rationale_code": rationale_code,
                "replay_status": artifact.get("replay_status"),
                "replay_consistency_sli": artifact.get("replay_consistency_sli"),
            },
        )
    else:
        logger.debug(
            "replay_governance_allowed",
            extra={
                "event": "replay_governance_allowed",
                "run_id": run_id,
                "trace_id": trace_id,
                "rationale_code": rationale_code,
            },
        )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summarize_replay_governance_decision(decision_artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a concise machine-readable summary used by CLI / reports.

    Parameters
    ----------
    decision_artifact:
        A ``replay_governance_decision`` artifact dict.

    Returns
    -------
    dict with keys used by downstream reports / enforcement surfaces.
    """
    decision = decision_artifact.get("decision") or {}
    policy = decision_artifact.get("governance_policy") or {}
    enforcement = decision_artifact.get("enforcement_reason") or {}

    return {
        "replay_governance_response": decision.get("system_response"),
        "replay_governance_rationale_code": decision.get("rationale_code"),
        "replay_governance_severity": decision.get("severity"),
        "replay_governance_replay_governed": decision.get("replay_governed"),
        "replay_status": decision_artifact.get("replay_status"),
        "replay_consistency_sli": decision_artifact.get("replay_consistency_sli"),
        "replay_governance_escalated_final_decision": (
            decision.get("system_response") != SYSTEM_RESPONSE_ALLOW
        ),
        "governance_policy_name": policy.get("policy_name"),
        "enforcement_summary": enforcement.get("summary"),
        "artifact_status": decision_artifact.get("status"),
    }


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def should_block_from_replay_governance(decision_artifact: Dict[str, Any]) -> bool:
    """Return True if replay governance requires execution to be blocked."""
    decision = decision_artifact.get("decision") or {}
    return decision.get("system_response") == SYSTEM_RESPONSE_BLOCK


def should_require_review_from_replay_governance(decision_artifact: Dict[str, Any]) -> bool:
    """Return True if replay governance requires human review before proceeding."""
    decision = decision_artifact.get("decision") or {}
    return decision.get("system_response") == SYSTEM_RESPONSE_REQUIRE_REVIEW


def should_quarantine_from_replay_governance(decision_artifact: Dict[str, Any]) -> bool:
    """Return True if replay governance requires outputs to be quarantined."""
    decision = decision_artifact.get("decision") or {}
    return decision.get("system_response") == SYSTEM_RESPONSE_QUARANTINE


# ---------------------------------------------------------------------------
# System response merger
# ---------------------------------------------------------------------------

def merge_system_responses(responses: List[str]) -> str:
    """Return the strictest system_response from a list.

    Precedence (strictest wins):  block > quarantine > require_review > allow

    Parameters
    ----------
    responses:
        List of system_response strings.  Unknown values are treated as
        'block' per fail-closed policy.

    Returns
    -------
    str
        The strictest response.  Returns 'block' if the list is empty (fail
        closed) or contains any unknown value.
    """
    if not responses:
        return SYSTEM_RESPONSE_BLOCK

    strictest = SYSTEM_RESPONSE_ALLOW
    for r in responses:
        if r not in _SYSTEM_RESPONSE_PRECEDENCE:
            return SYSTEM_RESPONSE_BLOCK
        if _SYSTEM_RESPONSE_PRECEDENCE[r] > _SYSTEM_RESPONSE_PRECEDENCE[strictest]:
            strictest = r
    return strictest
