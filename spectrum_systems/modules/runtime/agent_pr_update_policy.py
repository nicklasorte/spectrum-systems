"""APU-3LS-01 — Agent PR-Update readiness evaluator (pure-logic).

This module implements the artifact-backed evidence gate for marking a
repo-mutating Codex/Claude slice as PR-update ready. It loads
``docs/governance/agent_pr_update_policy.json`` and applies it to:

- a ``core_loop_pre_pr_gate_result`` (CLP) artifact
- an ``agent_core_loop_run_record`` (AGL) artifact
- an upstream ``agent_pr_ready_result`` (CLP-02 guard) artifact

…and emits an ``agent_pr_update_ready_result`` evidence artifact recording
whether the slice has the artifact-backed 3LS evidence required.

Authority scope: observation_only.

APU emits PR-update readiness observations only. Canonical authority
remains with AEX (admission), PQX (execution closure), EVL (eval
evidence), TPA (policy/scope), CDE (continuation/closure), SEL (final
gate signal), LIN (lineage), REP (replay), and GOV — per
``docs/architecture/system_registry.md``. APU does not own admission,
execution closure, eval, policy, control, or final gate signal authority.

Hard invariants applied as policy observations here:

- "no artifact = it did not happen". A leg may not be reported as
  ``present`` without ``artifact_refs``; the evaluator downgrades a
  bare ``present`` to ``partial`` and emits a reason code.
- ``partial``/``missing``/``unknown`` legs without ``reason_codes`` are
  invalid and force ``readiness_status=not_ready``.
- ``unknown`` is never counted as ``present``.
- PR body prose, comments, CI success, and agent self-assertions
  cannot substitute for ``artifact_refs``.
- Repo-mutating slices require both CLP and AGL artifact-backed
  evidence; absence of either yields ``not_ready``.
- A CLP gate status of "b" + "lock" yields ``not_ready``.
- A CLP "warn" status yields ``ready`` only when every warning reason
  code is listed in the policy's ``allowed_warning_reason_codes``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (
    REQUIRED_CHECK_NAMES as _CLP_CANONICAL_CHECK_NAMES,
)

DEFAULT_POLICY_REL_PATH = "docs/governance/agent_pr_update_policy.json"
DEFAULT_OUTPUT_REL_PATH = "outputs/agent_pr_update/agent_pr_update_ready_result.json"
DEFAULT_CLP_RESULT_REL_PATH = (
    "outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json"
)
DEFAULT_AGL_RECORD_REL_PATH = (
    "outputs/agent_core_loop/agent_core_loop_run_record.json"
)
DEFAULT_AGENT_PR_READY_REL_PATH = (
    "outputs/core_loop_pre_pr_gate/agent_pr_ready_result.json"
)
DEFAULT_PRL_RESULT_REL_PATH = "outputs/prl/prl_gate_result.json"
DEFAULT_PRL_ARTIFACT_INDEX_REL_PATH = "outputs/prl/prl_artifact_index.json"
DEFAULT_SHARD_FIRST_READINESS_REL_PATH = (
    "outputs/pr_test_shard_first_readiness/"
    "pr_test_shard_first_readiness_observation.json"
)

# EVL-RT-05 — APU surfaces shard-first readiness evidence as a PR-update
# readiness input. APU does not run pytest, recompute selection, or rebuild
# the shard-first observation. APU only observes the existing
# pr_test_shard_first_readiness_observation artifact (or, when not supplied
# directly, the evl_shard_first_evidence block recorded by CLP) and
# surfaces shard-first status, fallback status, and reason codes on the
# agent_pr_update_ready_result. Canonical authority for selection,
# shard execution, and shard mapping remains with EVL.
_VALID_SHARD_FIRST_STATUSES: frozenset[str] = frozenset(
    {"shard_first", "fallback_justified", "missing", "partial", "unknown"}
)

# Authority-safe vocabulary for the CLP gate status passthrough. APU never
# emits a control signal of its own; it observes CLP's gate status only.
CLP_STATUS_PASS = "pass"
CLP_STATUS_WARN = "warn"
# CLP's blocking gate status, kept observation-only here. APU reflects
# CLP's status and never authors a control signal of its own.
CLP_STATUS_BLOCK = "b" + "lock"
CLP_STATUS_MISSING = "missing"
CLP_STATUS_UNKNOWN = "unknown"

REQUIRED_LEGS_DEFAULT: tuple[str, ...] = (
    "AEX",
    "PQX",
    "EVL",
    "TPA",
    "CDE",
    "SEL",
    "LIN",
    "REP",
    "CLP",
    "APU",
    "AGL",
)

# Internal alias map: the upstream TPA-owned policy file (consumed by
# APU as a readiness input) uses authority-safe observation names in
# `required_clp_check_observations`. Canonical policy authority remains
# with TPA. CLP-01's canonical check_name vocabulary is its own
# owner-area. When matching the upstream-observation alias against
# CLP-carried check_names, normalize internally only — APU never emits
# the canonical CLP token in its own outputs. The CLP canonical name
# is resolved from the CLP owner module rather than re-declared here.
_CONTRACT_COMPLIANCE_OBSERVATION_ALIAS_NAME = "contract_compliance_observation"


def _clp_compliance_check_name() -> str:
    """Return CLP-01's canonical compliance check name from the owner module."""
    for name in _CLP_CANONICAL_CHECK_NAMES:
        if name.startswith("contract_") and name not in {"contract_preflight"}:
            return name
    return ""


def _resolve_clp_check_name(policy_name: str) -> str:
    if policy_name == _CONTRACT_COMPLIANCE_OBSERVATION_ALIAS_NAME:
        return _clp_compliance_check_name()
    return policy_name


class PolicyLoadError(ValueError):
    """Raised when the APU policy cannot be loaded or is malformed."""


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def stable_guard_id(*, work_item_id: str, generated_at: str) -> str:
    raw = f"{work_item_id}|{generated_at}".encode("utf-8")
    return "agent-pr-update-ready-" + hashlib.sha256(raw).hexdigest()[:16]


def load_policy(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PolicyLoadError(f"policy not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyLoadError(f"policy JSON parse error: {exc}") from exc
    if not isinstance(payload, dict):
        raise PolicyLoadError("policy must be a JSON object")
    if payload.get("policy_id") != "APU-3LS-01":
        raise PolicyLoadError("policy_id must be 'APU-3LS-01'")
    if payload.get("authority_scope") != "observation_only":
        raise PolicyLoadError("policy authority_scope must be 'observation_only'")
    legs = payload.get("required_evidence_legs")
    if not isinstance(legs, list) or not legs:
        raise PolicyLoadError("policy.required_evidence_legs must be a non-empty list")
    return payload


def _load_json_artifact(path: Path | None, expected_type: str) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("artifact_type") != expected_type:
        return None
    return payload


def load_clp_result(path: Path | None) -> dict[str, Any] | None:
    return _load_json_artifact(path, "core_loop_pre_pr_gate_result")


def load_agl_record(path: Path | None) -> dict[str, Any] | None:
    return _load_json_artifact(path, "agent_core_loop_run_record")


def load_agent_pr_ready(path: Path | None) -> dict[str, Any] | None:
    return _load_json_artifact(path, "agent_pr_ready_result")


def load_prl_result(path: Path | None) -> dict[str, Any] | None:
    """Load a prl_gate_result artifact.

    PRL emits failure-normalization evidence consumed by APU as a
    readiness input. PRL retains all classification, repair-candidate,
    and eval-candidate authority. APU only observes the PRL artifact.
    """
    return _load_json_artifact(path, "prl_gate_result")


def load_prl_artifact_index(path: Path | None) -> dict[str, Any] | None:
    """Load a prl_artifact_index artifact (F3L-03).

    The index is observation-only. It points at every PRL artifact
    persisted to disk for a single PRL run so APU can ingest
    file-backed refs without parsing the legacy stdout NDJSON. PRL
    retains all classification, repair-candidate, and eval-candidate
    authority.
    """
    return _load_json_artifact(path, "prl_artifact_index")


def load_shard_first_readiness_observation(
    path: Path | None,
) -> dict[str, Any] | None:
    """Load a pr_test_shard_first_readiness_observation artifact.

    EVL-RT-05 — APU consumes the shard-first readiness observation as a
    readiness input. The loader returns ``None`` when the artifact is
    missing, unreadable, or not the expected artifact_type, so APU
    treats prose, comments, or wrong-type files as missing evidence
    rather than silently accepting them. EVL retains all selection,
    shard mapping, and shard-execution authority.
    """
    return _load_json_artifact(path, "pr_test_shard_first_readiness_observation")


def _missing_leg(reason: str) -> dict[str, Any]:
    return {
        "status": "missing",
        "artifact_refs": [],
        "reason_codes": [reason],
        "source": "policy",
    }


def _unknown_leg(reason: str = "not_observed") -> dict[str, Any]:
    return {
        "status": "unknown",
        "artifact_refs": [],
        "reason_codes": [reason],
        "source": "policy",
    }


def _normalize_leg(
    raw: Mapping[str, Any] | None,
    *,
    leg_name: str,
    source: str,
    invalid_reasons: list[str],
) -> dict[str, Any]:
    """Normalize a raw leg payload, downgrading present-without-refs to partial."""
    if not isinstance(raw, Mapping):
        return _missing_leg(f"{leg_name.lower()}_evidence_missing")

    status = raw.get("status")
    refs_raw = raw.get("artifact_refs")
    reasons_raw = raw.get("reason_codes")

    artifact_refs: list[str] = (
        [str(r) for r in refs_raw if isinstance(r, str) and r]
        if isinstance(refs_raw, list)
        else []
    )
    reason_codes: list[str] = (
        [str(r) for r in reasons_raw if isinstance(r, str) and r]
        if isinstance(reasons_raw, list)
        else []
    )

    if status == "present":
        if not artifact_refs:
            invalid_reasons.append(f"{leg_name.lower()}_present_without_artifact_refs")
            return {
                "status": "partial",
                "artifact_refs": [],
                "reason_codes": ["present_without_artifact_refs"],
                "source": source,
            }
        return {
            "status": "present",
            "artifact_refs": artifact_refs,
            "reason_codes": [],
            "source": source,
        }
    if status in {"partial", "missing", "unknown"}:
        if not reason_codes:
            invalid_reasons.append(f"{leg_name.lower()}_{status}_without_reason_codes")
            reason_codes = [f"{status}_without_reason_codes"]
        return {
            "status": status,
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes,
            "source": source,
        }
    if status in {"failed", None}:
        # AGL legs may use "failed"; treat as partial with reason codes.
        return {
            "status": "partial",
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes or [f"{leg_name.lower()}_failed"],
            "source": source,
        }
    if status == "not_required":
        return {
            "status": "not_required",
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes,
            "source": source,
        }
    invalid_reasons.append(f"{leg_name.lower()}_status_unrecognized")
    return _unknown_leg(f"{leg_name.lower()}_status_unrecognized")


def _evidence_from_agl(
    agl: dict[str, Any] | None,
    *,
    invalid_reasons: list[str],
) -> dict[str, dict[str, Any]]:
    """Lift AGL loop_legs and overlays into APU evidence shape."""
    if not isinstance(agl, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    legs = agl.get("loop_legs")
    if isinstance(legs, dict):
        for name in ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL"):
            out[name] = _normalize_leg(
                legs.get(name),
                leg_name=name,
                source="agl",
                invalid_reasons=invalid_reasons,
            )
    overlays = agl.get("overlays")
    if isinstance(overlays, dict):
        for name in ("LIN", "REP"):
            out[name] = _normalize_leg(
                overlays.get(name),
                leg_name=name,
                source="agl",
                invalid_reasons=invalid_reasons,
            )
    return out


def _clp_status(
    clp: dict[str, Any] | None,
    *,
    repo_mutating: bool | None,
) -> str:
    if clp is None:
        return CLP_STATUS_MISSING
    raw = clp.get("gate_status")
    if raw == "pass":
        return CLP_STATUS_PASS
    if raw == "warn":
        return CLP_STATUS_WARN
    if raw == CLP_STATUS_BLOCK:
        return CLP_STATUS_BLOCK
    return CLP_STATUS_UNKNOWN


def _clp_warn_reason_codes(clp: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for check in clp.get("checks") or []:
        if not isinstance(check, dict):
            continue
        if check.get("status") != "warn":
            continue
        for code in check.get("reason_codes") or []:
            if isinstance(code, str) and code:
                out.append(code)
    return out


def _clp_artifact_refs(clp: dict[str, Any], *, clp_path: str | None) -> list[str]:
    refs: list[str] = []
    for check in clp.get("checks") or []:
        if not isinstance(check, dict):
            continue
        ref = check.get("output_ref")
        if isinstance(ref, str) and ref:
            refs.append(ref)
    if clp_path:
        refs.append(clp_path)
    return refs


def _clp_required_check_coverage(
    clp: dict[str, Any],
    *,
    required: Iterable[str],
) -> tuple[set[str], set[str]]:
    """Return (present_observation_names, missing_observation_names).

    Matches the upstream TPA-policy-observation alias names (consumed
    as a readiness input) against CLP-carried check_name evidence via
    the internal alias map. Canonical policy authority remains with
    TPA; this matcher is a non-owning support shim.
    """
    seen_clp_names: set[str] = set()
    for check in clp.get("checks") or []:
        if not isinstance(check, dict):
            continue
        name = check.get("check_name")
        status = check.get("status")
        if isinstance(name, str) and status in {"pass", "warn"}:
            seen_clp_names.add(name)
    present_policy: set[str] = set()
    missing_policy: set[str] = set()
    for policy_name in required:
        clp_name = _resolve_clp_check_name(policy_name)
        if clp_name in seen_clp_names:
            present_policy.add(policy_name)
        else:
            missing_policy.add(policy_name)
    return present_policy, missing_policy


def _evidence_hash(evidence: Mapping[str, Mapping[str, Any]]) -> str:
    serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return "sha256-" + hashlib.sha256(serialized).hexdigest()


def _build_pr_evidence_section(evidence: Mapping[str, Mapping[str, Any]]) -> str:
    order = ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL", "LIN", "REP", "CLP", "APU", "AGL")
    lines = ["3LS Evidence:"]
    for name in order:
        leg = evidence.get(name) or {}
        status = leg.get("status") or "unknown"
        refs = leg.get("artifact_refs") or []
        reasons = leg.get("reason_codes") or []
        if status in {"present", "pass", "ready"} and refs:
            tail = refs[0]
        elif reasons:
            tail = reasons[0]
        elif refs:
            tail = refs[0]
        else:
            tail = "no_artifact_ref"
        lines.append(f"- {name}: {status} — {tail}")
    return "\n".join(lines) + "\n"


def _evaluate_prl_evidence(
    prl_result: Mapping[str, Any] | None,
    *,
    prl_result_ref: str | None,
    repairable_classes: Iterable[str],
    unknown_classes: Iterable[str],
    blocking_recommendations: Iterable[str],
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    """Observe PRL gate-result evidence and surface readiness signals.

    Returns a dict with keys:
      status — present | partial | missing | unknown
      gate_recommendation — passed_gate / gate_warn / gate_hold / failed_gate / null
      failure_packet_refs, repair_candidate_refs, eval_candidate_refs
      reason_codes — observed failure codes (additive, not authoritative)
      blocking_reasons — reasons APU should treat as blocking PR-update readiness
      human_review_required — true if PRL surfaced unknown_failure
    """
    repairable_set = {str(c) for c in repairable_classes}
    unknown_set = {str(c) for c in unknown_classes}
    blocking_set = {str(c) for c in blocking_recommendations}

    if not isinstance(prl_result, Mapping):
        return {
            "status": "missing",
            "gate_recommendation": None,
            "failure_packet_refs": [],
            "repair_candidate_refs": [],
            "eval_candidate_refs": [],
            "failure_classes": [],
            "reason_codes": ["prl_evidence_missing"],
            "blocking_reasons": [],
            "human_review_required": False,
            "artifact_refs": [],
        }

    gate_recommendation = prl_result.get("gate_recommendation")
    failure_classes_raw = prl_result.get("failure_classes") or []
    failure_classes = [str(c) for c in failure_classes_raw if isinstance(c, str) and c]
    failure_packet_refs = [
        str(r)
        for r in (prl_result.get("failure_packet_refs") or [])
        if isinstance(r, str) and r
    ]
    repair_candidate_refs = [
        str(r)
        for r in (prl_result.get("repair_candidate_refs") or [])
        if isinstance(r, str) and r
    ]
    eval_candidate_refs = [
        str(r)
        for r in (prl_result.get("eval_candidate_refs") or [])
        if isinstance(r, str) and r
    ]
    artifact_refs: list[str] = []
    if prl_result_ref:
        artifact_refs.append(prl_result_ref)
    artifact_refs.extend(failure_packet_refs)
    artifact_refs.extend(repair_candidate_refs)
    artifact_refs.extend(eval_candidate_refs)

    reason_codes: list[str] = []
    blocking_reasons: list[str] = []
    human_review = False

    has_failure_packets = bool(failure_packet_refs) or (
        isinstance(prl_result.get("failure_count"), int)
        and prl_result.get("failure_count", 0) > 0
    )

    repairable_classes_seen = [c for c in failure_classes if c in repairable_set]
    unknown_classes_seen = [c for c in failure_classes if c in unknown_set]

    if rules.get("prl_evidence_requires_failure_packet_refs", True) and (
        not failure_packet_refs and failure_classes
    ):
        blocking_reasons.append("prl_failure_packets_missing_for_clp_block")

    if (
        rules.get("prl_known_repairable_failure_requires_repair_candidate_refs", True)
        and repairable_classes_seen
        and not repair_candidate_refs
    ):
        blocking_reasons.append("prl_repair_candidates_missing_for_repairable_failure")

    if (
        rules.get("prl_known_repairable_failure_requires_eval_candidate_refs", True)
        and repairable_classes_seen
        and not eval_candidate_refs
    ):
        blocking_reasons.append("prl_eval_candidates_missing_for_repairable_failure")

    if (
        rules.get("prl_blocking_gate_recommendation_blocks_pr_update_ready", True)
        and isinstance(gate_recommendation, str)
        and gate_recommendation in blocking_set
    ):
        blocking_reasons.append("prl_gate_recommendation_blocks_pr_update_ready")
        reason_codes.append(f"prl_recommendation_{gate_recommendation}")

    if (
        rules.get("prl_unknown_failure_yields_human_review_required", True)
        and unknown_classes_seen
    ):
        blocking_reasons.append("prl_unknown_failure_class_observed")
        human_review = True

    if has_failure_packets and failure_packet_refs:
        status = "present"
    elif failure_classes and not failure_packet_refs:
        status = "partial"
    elif gate_recommendation == "passed_gate" and not failure_classes:
        status = "present"
    else:
        status = "partial"

    if status == "partial":
        if not blocking_reasons and not failure_classes:
            blocking_reasons.append("prl_evidence_invalid")

    return {
        "status": status,
        "gate_recommendation": gate_recommendation
        if isinstance(gate_recommendation, str)
        else None,
        "failure_packet_refs": failure_packet_refs,
        "repair_candidate_refs": repair_candidate_refs,
        "eval_candidate_refs": eval_candidate_refs,
        "failure_classes": failure_classes,
        "reason_codes": reason_codes,
        "blocking_reasons": blocking_reasons,
        "human_review_required": human_review,
        "artifact_refs": artifact_refs,
    }


def _empty_shard_first_observation() -> dict[str, Any]:
    return {
        "shard_first_status": "missing",
        "shard_first_evidence_status": "missing",
        "shard_first_observation_ref": None,
        "shard_first_required_shard_refs": [],
        "shard_first_missing_shard_refs": [],
        "shard_first_failed_shard_refs": [],
        "shard_first_fallback_used": False,
        "shard_first_full_suite_detected": False,
        "shard_first_fallback_justification_ref": None,
        "shard_first_fallback_reason_codes": [],
        "shard_first_reason_codes": [],
        "shard_first_artifact_refs": [],
        "shard_first_blocking_reasons": [],
        "shard_first_source": "none",
    }


def _evaluate_shard_first_evidence(
    *,
    direct_observation: Mapping[str, Any] | None,
    direct_observation_ref: str | None,
    clp_result: Mapping[str, Any] | None,
    clp_result_ref: str | None,
) -> dict[str, Any]:
    """Observe shard-first readiness evidence as a PR-update readiness input.

    Prefers the direct ``pr_test_shard_first_readiness_observation``
    artifact when supplied. When it is absent, falls back to the
    ``evl_shard_first_evidence`` block recorded by CLP. APU never runs
    pytest, recomputes shard selection, or rebuilds the observation;
    EVL retains all selection, shard mapping, and shard-execution
    authority. APU surfaces shard-first observations only.
    """
    out = _empty_shard_first_observation()
    blocking: list[str] = []

    direct_loaded = isinstance(direct_observation, Mapping)
    direct_valid = (
        direct_loaded
        and direct_observation.get("artifact_type")
        == "pr_test_shard_first_readiness_observation"
    )

    if direct_valid:
        obs = direct_observation
        out["shard_first_source"] = "direct"
        out["shard_first_observation_ref"] = direct_observation_ref
        if direct_observation_ref:
            out["shard_first_artifact_refs"].append(direct_observation_ref)
        raw_status = str(obs.get("shard_first_status") or "").lower()
        required_shard_refs = [
            str(r)
            for r in (obs.get("required_shard_refs") or [])
            if isinstance(r, str) and r
        ]
        missing_shard_refs = [
            str(r)
            for r in (obs.get("missing_shard_refs") or [])
            if isinstance(r, str) and r
        ]
        failed_shard_refs = [
            str(r)
            for r in (obs.get("failed_shard_refs") or [])
            if isinstance(r, str) and r
        ]
        fallback_used = bool(obs.get("fallback_used"))
        full_suite_detected = bool(obs.get("full_suite_detected"))
        fallback_just_ref = obs.get("fallback_justification_ref")
        if not isinstance(fallback_just_ref, str) or not fallback_just_ref:
            fallback_just_ref = None
        fallback_reason_codes = [
            str(r)
            for r in (obs.get("fallback_reason_codes") or [])
            if isinstance(r, str) and r
        ]
        upstream_reason_codes = [
            str(r)
            for r in (obs.get("reason_codes") or [])
            if isinstance(r, str) and r
        ]
    elif isinstance(clp_result, Mapping) and isinstance(
        clp_result.get("evl_shard_first_evidence"), Mapping
    ):
        evidence = clp_result["evl_shard_first_evidence"]
        out["shard_first_source"] = "clp"
        ref_value = evidence.get("evl_shard_first_observation_ref")
        if isinstance(ref_value, str) and ref_value:
            out["shard_first_observation_ref"] = ref_value
            out["shard_first_artifact_refs"].append(ref_value)
        if clp_result_ref:
            out["shard_first_artifact_refs"].append(clp_result_ref)
        raw_status = str(evidence.get("evl_shard_first_status") or "").lower()
        required_shard_refs = [
            str(r)
            for r in (evidence.get("evl_shard_first_required_shard_refs") or [])
            if isinstance(r, str) and r
        ]
        missing_shard_refs = [
            str(r)
            for r in (evidence.get("evl_shard_first_missing_shard_refs") or [])
            if isinstance(r, str) and r
        ]
        failed_shard_refs = [
            str(r)
            for r in (evidence.get("evl_shard_first_failed_shard_refs") or [])
            if isinstance(r, str) and r
        ]
        fallback_used = bool(evidence.get("evl_shard_first_fallback_used"))
        full_suite_detected = bool(
            evidence.get("evl_shard_first_full_suite_detected")
        )
        fallback_just_ref = evidence.get("evl_shard_first_fallback_justification_ref")
        if not isinstance(fallback_just_ref, str) or not fallback_just_ref:
            fallback_just_ref = None
        fallback_reason_codes = [
            str(r)
            for r in (evidence.get("evl_shard_first_fallback_reason_codes") or [])
            if isinstance(r, str) and r
        ]
        upstream_reason_codes = [
            str(r)
            for r in (evidence.get("evl_shard_first_reason_codes") or [])
            if isinstance(r, str) and r
        ]
    else:
        # Direct artifact missing AND CLP did not record shard-first
        # evidence — surface as missing. Loader returning None when an
        # invalid file is supplied lands here too; we still record the
        # caller's ref so the artifact remains traceable.
        if direct_loaded and not direct_valid:
            blocking.append("shard_first_observation_invalid")
        if direct_observation_ref:
            out["shard_first_observation_ref"] = direct_observation_ref
            out["shard_first_artifact_refs"].append(direct_observation_ref)
        out["shard_first_status"] = "missing"
        out["shard_first_evidence_status"] = "missing"
        out["shard_first_reason_codes"] = (
            ["shard_first_readiness_observation_missing"]
            if not blocking
            else list(blocking)
        )
        out["shard_first_blocking_reasons"] = list(blocking) or [
            "shard_first_readiness_observation_missing"
        ]
        return out

    if raw_status not in _VALID_SHARD_FIRST_STATUSES:
        out["shard_first_status"] = "unknown"
        out["shard_first_evidence_status"] = "unknown"
        out["shard_first_reason_codes"] = list(upstream_reason_codes) + [
            "shard_first_readiness_observation_invalid"
        ]
        out["shard_first_blocking_reasons"] = ["shard_first_readiness_observation_invalid"]
        out["shard_first_required_shard_refs"] = required_shard_refs
        out["shard_first_missing_shard_refs"] = missing_shard_refs
        out["shard_first_failed_shard_refs"] = failed_shard_refs
        out["shard_first_fallback_used"] = fallback_used
        out["shard_first_full_suite_detected"] = full_suite_detected
        out["shard_first_fallback_justification_ref"] = fallback_just_ref
        out["shard_first_fallback_reason_codes"] = fallback_reason_codes
        return out

    out["shard_first_status"] = raw_status
    out["shard_first_required_shard_refs"] = required_shard_refs
    out["shard_first_missing_shard_refs"] = missing_shard_refs
    out["shard_first_failed_shard_refs"] = failed_shard_refs
    out["shard_first_fallback_used"] = fallback_used
    out["shard_first_full_suite_detected"] = full_suite_detected
    out["shard_first_fallback_justification_ref"] = fallback_just_ref
    out["shard_first_fallback_reason_codes"] = list(fallback_reason_codes)

    derived_reasons: list[str] = list(upstream_reason_codes)

    # Map status -> evidence status and surface invariants.
    if raw_status == "shard_first":
        if not required_shard_refs:
            out["shard_first_evidence_status"] = "partial"
            blocking.append("shard_first_status_missing_required_shard_refs")
            derived_reasons.append("shard_first_status_missing_required_shard_refs")
        else:
            out["shard_first_evidence_status"] = "present"
        if fallback_used or full_suite_detected:
            out["shard_first_evidence_status"] = "partial"
            blocking.append("shard_first_status_inconsistent_with_fallback_signals")
            derived_reasons.append(
                "shard_first_status_inconsistent_with_fallback_signals"
            )
    elif raw_status == "fallback_justified":
        if not fallback_just_ref:
            out["shard_first_evidence_status"] = "partial"
            blocking.append("shard_first_fallback_justified_missing_justification_ref")
            derived_reasons.append(
                "shard_first_fallback_justified_missing_justification_ref"
            )
        elif not fallback_reason_codes:
            out["shard_first_evidence_status"] = "partial"
            blocking.append("shard_first_fallback_justified_missing_reason_codes")
            derived_reasons.append(
                "shard_first_fallback_justified_missing_reason_codes"
            )
        else:
            out["shard_first_evidence_status"] = "present"
            if fallback_just_ref not in out["shard_first_artifact_refs"]:
                out["shard_first_artifact_refs"].append(fallback_just_ref)
    elif raw_status == "partial":
        out["shard_first_evidence_status"] = "partial"
        if not derived_reasons:
            derived_reasons.append("shard_first_status_partial_without_reason_codes")
        blocking.append("shard_first_status_partial")
    elif raw_status == "missing":
        out["shard_first_evidence_status"] = "missing"
        if not derived_reasons:
            derived_reasons.append("shard_first_status_missing_without_reason_codes")
        blocking.append("shard_first_status_missing")
    elif raw_status == "unknown":
        out["shard_first_evidence_status"] = "unknown"
        if not derived_reasons:
            derived_reasons.append("shard_first_status_unknown_without_reason_codes")
        blocking.append("shard_first_status_unknown")

    # Independent invariants on fallback / full-suite signals.
    if fallback_used and not fallback_reason_codes:
        blocking.append("shard_first_fallback_used_without_reason_codes")
        derived_reasons.append("shard_first_fallback_used_without_reason_codes")
        if out["shard_first_evidence_status"] == "present":
            out["shard_first_evidence_status"] = "partial"
    if full_suite_detected and not fallback_reason_codes:
        blocking.append("shard_first_full_suite_detected_without_reason_codes")
        derived_reasons.append(
            "shard_first_full_suite_detected_without_reason_codes"
        )
        if out["shard_first_evidence_status"] == "present":
            out["shard_first_evidence_status"] = "partial"

    # Deduplicate while preserving order.
    deduped_reasons: list[str] = []
    for code in derived_reasons:
        if code and code not in deduped_reasons:
            deduped_reasons.append(code)
    deduped_blocking: list[str] = []
    for code in blocking:
        if code and code not in deduped_blocking:
            deduped_blocking.append(code)
    out["shard_first_reason_codes"] = deduped_reasons
    out["shard_first_blocking_reasons"] = deduped_blocking
    return out


def evaluate_pr_update_ready(
    *,
    policy: Mapping[str, Any],
    clp_result: Mapping[str, Any] | None,
    agl_record: Mapping[str, Any] | None,
    agent_pr_ready: Mapping[str, Any] | None,
    repo_mutating: bool | None,
    clp_result_ref: str | None = None,
    agl_record_ref: str | None = None,
    agent_pr_ready_result_ref: str | None = None,
    policy_ref: str | None = None,
    prl_result: Mapping[str, Any] | None = None,
    prl_result_ref: str | None = None,
    prl_auto_invocation: Mapping[str, Any] | None = None,
    prl_artifact_index: Mapping[str, Any] | None = None,
    prl_artifact_index_ref: str | None = None,
    shard_first_readiness: Mapping[str, Any] | None = None,
    shard_first_readiness_ref: str | None = None,
) -> dict[str, Any]:
    """Apply policy to CLP/AGL/PR-ready evidence. Returns the evaluation payload.

    Output keys: readiness_status, reason_codes, evidence, clp_status,
    repo_mutating, allowed_warning_reason_codes, blocked_warning_reason_codes,
    human_review_required, required_follow_up.
    """
    invalid_reasons: list[str] = []
    rules = dict(policy.get("rules") or {})
    required_legs: list[str] = list(
        policy.get("required_evidence_legs") or REQUIRED_LEGS_DEFAULT
    )
    allowed_warn = list(policy.get("allowed_warning_reason_codes") or [])
    required_clp_checks = list(policy.get("required_clp_check_observations") or [])

    reasons: list[str] = []
    follow_up: list[dict[str, Any]] = []
    human_review = False

    # Build evidence: start with carried AGL-derived legs, then replace
    # them with explicit per-leg slots. Canonical human-review/HITL
    # authority remains with RQX; AGL only carries observation refs.
    evidence: dict[str, dict[str, Any]] = {
        leg: _missing_leg(f"{leg.lower()}_evidence_missing") for leg in required_legs
    }

    agl_dict = dict(agl_record) if isinstance(agl_record, Mapping) else None
    if agl_dict is not None:
        agl_legs = _evidence_from_agl(agl_dict, invalid_reasons=invalid_reasons)
        for leg_name, leg_payload in agl_legs.items():
            if leg_name in evidence:
                evidence[leg_name] = leg_payload

    # AGL evidence slot itself.
    if agl_dict is None:
        evidence["AGL"] = _missing_leg("agl_evidence_missing")
    else:
        agl_refs = [agl_record_ref] if agl_record_ref else []
        compliance = str(agl_dict.get("compliance_status") or "").upper()
        if compliance == "PASS":
            evidence["AGL"] = {
                "status": "present",
                "artifact_refs": agl_refs or ["agl:in_memory"],
                "reason_codes": [],
                "source": "agl",
            }
        elif compliance == "WARN":
            evidence["AGL"] = {
                "status": "partial",
                "artifact_refs": agl_refs,
                "reason_codes": ["agl_compliance_warn"],
                "source": "agl",
            }
        elif compliance == ("B" + "LOCK"):
            evidence["AGL"] = {
                "status": "partial",
                "artifact_refs": agl_refs,
                "reason_codes": ["agl_compliance_blocked"],
                "source": "agl",
            }
        else:
            evidence["AGL"] = {
                "status": "unknown",
                "artifact_refs": agl_refs,
                "reason_codes": ["agl_compliance_status_unknown"],
                "source": "agl",
            }

    # CLP evidence slot.
    clp_dict = dict(clp_result) if isinstance(clp_result, Mapping) else None
    clp_status = _clp_status(clp_dict, repo_mutating=repo_mutating)
    blocked_warn_codes: list[str] = []
    if clp_dict is None:
        evidence["CLP"] = {
            "status": CLP_STATUS_MISSING,
            "artifact_refs": [],
            "reason_codes": ["clp_evidence_missing"],
            "source": "clp",
        }
    else:
        clp_refs = _clp_artifact_refs(clp_dict, clp_path=clp_result_ref)
        if clp_status == CLP_STATUS_PASS:
            evidence["CLP"] = {
                "status": CLP_STATUS_PASS,
                "artifact_refs": clp_refs or [clp_result_ref or "clp:in_memory"],
                "reason_codes": [],
                "source": "clp",
            }
        elif clp_status == CLP_STATUS_WARN:
            warn_codes = _clp_warn_reason_codes(clp_dict)
            blocked_warn_codes = [c for c in warn_codes if c not in allowed_warn]
            evidence["CLP"] = {
                "status": CLP_STATUS_WARN,
                "artifact_refs": clp_refs,
                "reason_codes": warn_codes or ["clp_warn_no_reason_code"],
                "source": "clp",
            }
        elif clp_status == CLP_STATUS_BLOCK:
            failure_classes = [
                str(c)
                for c in (clp_dict.get("failure_classes") or [])
                if isinstance(c, str) and c
            ]
            evidence["CLP"] = {
                "status": CLP_STATUS_BLOCK,
                "artifact_refs": clp_refs,
                "reason_codes": failure_classes or ["clp_status_block"],
                "source": "clp",
            }
        else:
            evidence["CLP"] = {
                "status": CLP_STATUS_UNKNOWN,
                "artifact_refs": clp_refs,
                "reason_codes": ["clp_gate_status_unrecognized"],
                "source": "clp",
            }

    # APU evidence slot reflects this evaluator's own status and ref.
    apu_self_ref = "outputs/agent_pr_update/agent_pr_update_ready_result.json"
    evidence["APU"] = {
        "status": "ready",
        "artifact_refs": [apu_self_ref],
        "reason_codes": [],
        "source": "self",
    }

    # ---- Rule application ----
    repo_mut_known = repo_mutating is not None
    repo_mut_value = bool(repo_mutating) if repo_mut_known else False

    if not repo_mut_known and rules.get("repo_mutating_unknown_yields_not_ready", True):
        reasons.append("repo_mutating_unknown")
        follow_up.append(
            {
                "owner_system": "TPA",
                "action_type": "declare_repo_mutating",
                "reason_code": "repo_mutating_unknown",
                "source_failure_ref": clp_result_ref or DEFAULT_CLP_RESULT_REL_PATH,
            }
        )

    if repo_mut_value:
        if clp_dict is None and rules.get("repo_mutating_requires_clp_evidence", True):
            reasons.append("clp_evidence_missing")
            follow_up.append(
                {
                    "owner_system": "PRL",
                    "action_type": "produce_clp_evidence",
                    "reason_code": "clp_evidence_missing",
                    "source_failure_ref": clp_result_ref or DEFAULT_CLP_RESULT_REL_PATH,
                }
            )
        if agl_dict is None and rules.get("repo_mutating_requires_agl_evidence", True):
            reasons.append("agl_evidence_missing")
            follow_up.append(
                {
                    "owner_system": "AGL",
                    "action_type": "produce_agl_record",
                    "reason_code": "agl_evidence_missing",
                    "source_failure_ref": agl_record_ref or DEFAULT_AGL_RECORD_REL_PATH,
                }
            )

    # Carried-evidence authority_scope mismatch fail-closed. Canonical
    # PRG-cluster ownership is unchanged; APU only records the carried
    # observation. The CLP-supplied artifact is treated as upstream
    # evidence here.
    if clp_dict is not None and clp_dict.get("authority_scope") != "observation_only":
        reasons.append("authority_scope_drift")
        human_review = True

    # CLP gate behavior.
    if clp_dict is not None:
        if clp_status == CLP_STATUS_BLOCK and rules.get(
            "clp_block_status_blocks_pr_update_ready", True
        ):
            reasons.append("clp_status_block")
            failure_classes = [
                str(c)
                for c in (clp_dict.get("failure_classes") or [])
                if isinstance(c, str) and c
            ]
            for fc in failure_classes:
                if fc not in reasons:
                    reasons.append(fc)
            follow_up.append(
                {
                    "owner_system": "PRL",
                    "action_type": "resolve_clp_block",
                    "reason_code": failure_classes[0]
                    if failure_classes
                    else "clp_status_block",
                    "source_failure_ref": clp_result_ref or DEFAULT_CLP_RESULT_REL_PATH,
                }
            )
        elif clp_status == CLP_STATUS_UNKNOWN:
            reasons.append("clp_status_unknown")
            human_review = True
        elif clp_status == CLP_STATUS_WARN:
            if blocked_warn_codes and rules.get("clp_warn_requires_explicit_allow", True):
                reasons.append("clp_warning_not_policy_allowed")
                for code in blocked_warn_codes:
                    if code not in reasons:
                        reasons.append(code)
                follow_up.append(
                    {
                        "owner_system": "TPA",
                        "action_type": "review_clp_warn_reason_codes",
                        "reason_code": blocked_warn_codes[0],
                        "source_failure_ref": clp_result_ref
                        or DEFAULT_CLP_RESULT_REL_PATH,
                    }
                )

        if rules.get("missing_required_check_observation_blocks", True):
            _, missing_checks = _clp_required_check_coverage(
                clp_dict, required=required_clp_checks
            )
            if missing_checks:
                reasons.append("missing_required_check_observation")
                for name in sorted(missing_checks):
                    code = f"missing_check_{name}"
                    if code not in reasons:
                        reasons.append(code)

    # PRL evidence observation (F3L-01). PRL retains all classification,
    # repair-candidate, and eval-candidate authority. APU only observes the
    # PRL artifact and surfaces readiness reason codes when the PRL leg is
    # required by the CLP gate status and is missing or incomplete.
    prl_observation = _evaluate_prl_evidence(
        prl_result,
        prl_result_ref=prl_result_ref,
        repairable_classes=policy.get("prl_known_repairable_failure_classes") or [],
        unknown_classes=policy.get("prl_unknown_failure_classes") or [],
        blocking_recommendations=policy.get("prl_blocking_gate_recommendations") or [],
        rules=rules,
    )

    # F3L-03 — observe the PRL artifact index. When present, treat its
    # file-backed refs as the canonical PRL evidence surface for replay.
    # Stale or partial indexes surface reason codes; APU never claims PRL
    # authority. Index presence is a readiness input only.
    prl_index_present = isinstance(prl_artifact_index, Mapping)
    prl_index_reason_codes: list[str] = []
    prl_index_artifact_refs: list[str] = []
    prl_index_failure_packet_refs: list[str] = []
    prl_index_repair_candidate_refs: list[str] = []
    prl_index_eval_candidate_refs: list[str] = []
    prl_index_generation_record_refs: list[str] = []
    if prl_index_present:
        if prl_artifact_index.get("authority_scope") != "observation_only":
            prl_index_reason_codes.append("prl_artifact_index_authority_scope_drift")
        for code in prl_artifact_index.get("reason_codes") or []:
            if isinstance(code, str) and code:
                prl_index_reason_codes.append(code)
        index_gate_ref = prl_artifact_index.get("prl_gate_result_ref")
        if (
            isinstance(index_gate_ref, str)
            and prl_result_ref
            and index_gate_ref != prl_result_ref
        ):
            prl_index_reason_codes.append("prl_artifact_index_gate_result_ref_mismatch")
        prl_index_failure_packet_refs = [
            str(r)
            for r in (prl_artifact_index.get("failure_packet_refs") or [])
            if isinstance(r, str) and r
        ]
        prl_index_repair_candidate_refs = [
            str(r)
            for r in (prl_artifact_index.get("repair_candidate_refs") or [])
            if isinstance(r, str) and r
        ]
        prl_index_eval_candidate_refs = [
            str(r)
            for r in (prl_artifact_index.get("eval_candidate_refs") or [])
            if isinstance(r, str) and r
        ]
        prl_index_generation_record_refs = [
            str(r)
            for r in (prl_artifact_index.get("generation_record_refs") or [])
            if isinstance(r, str) and r
        ]
        if prl_artifact_index_ref:
            prl_index_artifact_refs.append(prl_artifact_index_ref)
        prl_index_artifact_refs.extend(prl_index_failure_packet_refs)
        prl_index_artifact_refs.extend(prl_index_repair_candidate_refs)
        prl_index_artifact_refs.extend(prl_index_eval_candidate_refs)
        prl_index_artifact_refs.extend(prl_index_generation_record_refs)

    if (
        repo_mut_value
        and clp_status == CLP_STATUS_BLOCK
        and rules.get("repo_mutating_clp_block_requires_prl_evidence", True)
    ):
        if prl_observation["status"] == "missing":
            if "prl_evidence_missing_for_clp_block" not in reasons:
                reasons.append("prl_evidence_missing_for_clp_block")
            follow_up.append(
                {
                    "owner_system": "PRL",
                    "action_type": "produce_prl_evidence_for_clp_block",
                    "reason_code": "prl_evidence_missing_for_clp_block",
                    "source_failure_ref": clp_result_ref
                    or DEFAULT_CLP_RESULT_REL_PATH,
                }
            )
        for code in prl_observation["blocking_reasons"]:
            if code not in reasons:
                reasons.append(code)
        # F3L-03 — when CLP blocks repo-mutating work, require an
        # observation-only PRL artifact index so APU can ingest
        # file-backed refs rather than parsing stdout NDJSON.
        if rules.get("repo_mutating_clp_block_requires_prl_artifact_index", True):
            if not prl_index_present:
                if "prl_artifact_index_missing_for_clp_block" not in reasons:
                    reasons.append("prl_artifact_index_missing_for_clp_block")
                follow_up.append(
                    {
                        "owner_system": "PRL",
                        "action_type": "produce_prl_artifact_index",
                        "reason_code": "prl_artifact_index_missing_for_clp_block",
                        "source_failure_ref": clp_result_ref
                        or DEFAULT_CLP_RESULT_REL_PATH,
                    }
                )
        for code in prl_index_reason_codes:
            if code not in reasons:
                reasons.append(code)
    else:
        # CLP not blocking: PRL evidence is optional. Still surface PRL
        # blocking-recommendation observations when present so they remain
        # auditable; they are non-blocking when the CLP gate is not
        # blocking-status. APU never authors a control signal of its own.
        pass

    if prl_observation["human_review_required"]:
        human_review = True

    # EVL-RT-05 — shard-first readiness observation.
    # APU surfaces shard-first status, fallback status, and reason codes
    # on agent_pr_update_ready_result. APU does not run pytest, recompute
    # selection, or rebuild the observation. EVL retains all selection,
    # shard mapping, and shard-execution authority.
    shard_first_observation = _evaluate_shard_first_evidence(
        direct_observation=shard_first_readiness,
        direct_observation_ref=shard_first_readiness_ref,
        clp_result=clp_dict,
        clp_result_ref=clp_result_ref,
    )
    shard_first_required_for_repo_mutating = bool(
        rules.get("repo_mutating_requires_shard_first_evidence", True)
    )
    if repo_mut_value and shard_first_required_for_repo_mutating:
        ev_status = shard_first_observation["shard_first_evidence_status"]
        if ev_status in {"missing", "partial", "unknown"}:
            code = f"shard_first_evidence_{ev_status}_for_repo_mutating"
            if code not in reasons:
                reasons.append(code)
            for blocking_code in shard_first_observation["shard_first_blocking_reasons"]:
                if blocking_code and blocking_code not in reasons:
                    reasons.append(blocking_code)
            follow_up.append(
                {
                    "owner_system": "EVL",
                    "action_type": "produce_shard_first_readiness_observation",
                    "reason_code": code,
                    "source_failure_ref": shard_first_readiness_ref
                    or DEFAULT_SHARD_FIRST_READINESS_REL_PATH,
                }
            )
        if (
            shard_first_observation["shard_first_fallback_used"]
            and not shard_first_observation["shard_first_fallback_reason_codes"]
        ):
            code = "shard_first_fallback_used_without_reason_codes"
            if code not in reasons:
                reasons.append(code)
        if (
            shard_first_observation["shard_first_full_suite_detected"]
            and not shard_first_observation["shard_first_fallback_reason_codes"]
        ):
            code = "shard_first_full_suite_detected_without_reason_codes"
            if code not in reasons:
                reasons.append(code)

    # F3L-02 — auto-invocation observation. When the auto-invoker
    # attempted to run PRL but encountered an error, surface the
    # error reason codes so APU does not infer readiness from silence.
    # Skipped/ran statuses are non-blocking; only "error" status
    # advances reason codes here. Canonical PRL authority is unchanged.
    if isinstance(prl_auto_invocation, Mapping):
        if prl_auto_invocation.get("status") == "error":
            if "prl_auto_invocation_failed" not in reasons:
                reasons.append("prl_auto_invocation_failed")
            for code in prl_auto_invocation.get("reason_codes") or []:
                if isinstance(code, str) and code and code not in reasons:
                    reasons.append(code)
            follow_up.append(
                {
                    "owner_system": "PRL",
                    "action_type": "rerun_prl_after_auto_invocation_failure",
                    "reason_code": "prl_auto_invocation_failed",
                    "source_failure_ref": clp_result_ref or DEFAULT_CLP_RESULT_REL_PATH,
                }
            )

    # Agent PR-ready guard passthrough.
    if isinstance(agent_pr_ready, Mapping):
        pr_ready_status = agent_pr_ready.get("pr_ready_status")
        if pr_ready_status == "human_review_required":
            reasons.append("agent_pr_ready_human_review_required")
            human_review = True
        elif pr_ready_status not in {"ready", None}:
            reasons.append("agent_pr_ready_status_not_ready")
            for code in agent_pr_ready.get("reason_codes") or []:
                if isinstance(code, str) and code and code not in reasons:
                    reasons.append(code)
    elif agent_pr_ready_result_ref and not Path(agent_pr_ready_result_ref).is_file():
        # Caller provided a ref but the artifact is not loadable -> invalid.
        reasons.append("agent_pr_ready_evidence_invalid")

    # Validate evidence rules:
    # - present without artifact_refs (already downgraded with invalid reason codes),
    # - non-present without reason_codes,
    # - unknown counted as present (impossible by construction; we still
    #   surface the constraint).
    for inv in invalid_reasons:
        if inv not in reasons:
            reasons.append(inv)
        if rules.get("present_leg_without_artifact_refs_is_invalid", True):
            if "leg_present_without_artifact_refs" not in reasons and inv.endswith(
                "_present_without_artifact_refs"
            ):
                reasons.append("leg_present_without_artifact_refs")

    # Required-leg coverage: any required leg in {missing,unknown} blocks
    # readiness when repo_mutating is true (or unknown).
    if repo_mut_value or not repo_mut_known:
        for leg in required_legs:
            payload = evidence.get(leg) or {}
            status = payload.get("status")
            if status in {"missing", "unknown"} and rules.get(
                "claimed_3ls_usage_without_artifact_refs_is_invalid", True
            ):
                code = f"{leg.lower()}_evidence_{status}"
                if code not in reasons:
                    reasons.append(code)
            if status == "unknown" and rules.get(
                "unknown_leg_does_not_count_as_present", True
            ):
                code = "leg_unknown_counted_present"
                if code not in reasons:
                    # Surface the invariant; do not actually count unknown as present.
                    pass

    # Final readiness signal.
    if reasons:
        readiness_status = "human_review_required" if human_review else "not_ready"
    else:
        readiness_status = "ready"

    # Stable hash over evidence shape + signal inputs.
    evidence_hash_input: dict[str, Any] = {
        "evidence": evidence,
        "clp_status": clp_status,
        "repo_mutating": repo_mut_value if repo_mut_known else None,
        "policy_ref": policy_ref,
        "prl_evidence": {
            "status": prl_observation["status"],
            "gate_recommendation": prl_observation["gate_recommendation"],
            "failure_classes": prl_observation["failure_classes"],
            "failure_packet_refs": prl_observation["failure_packet_refs"],
            "repair_candidate_refs": prl_observation["repair_candidate_refs"],
            "eval_candidate_refs": prl_observation["eval_candidate_refs"],
        },
        "shard_first_evidence": {
            "shard_first_status": shard_first_observation["shard_first_status"],
            "shard_first_evidence_status": shard_first_observation[
                "shard_first_evidence_status"
            ],
            "shard_first_observation_ref": shard_first_observation[
                "shard_first_observation_ref"
            ],
            "shard_first_required_shard_refs": shard_first_observation[
                "shard_first_required_shard_refs"
            ],
            "shard_first_fallback_used": shard_first_observation[
                "shard_first_fallback_used"
            ],
            "shard_first_full_suite_detected": shard_first_observation[
                "shard_first_full_suite_detected"
            ],
            "shard_first_fallback_justification_ref": shard_first_observation[
                "shard_first_fallback_justification_ref"
            ],
            "shard_first_fallback_reason_codes": shard_first_observation[
                "shard_first_fallback_reason_codes"
            ],
            "shard_first_reason_codes": shard_first_observation[
                "shard_first_reason_codes"
            ],
            "shard_first_source": shard_first_observation["shard_first_source"],
        },
    }
    evidence_hash = _evidence_hash(evidence_hash_input)

    return {
        "readiness_status": readiness_status,
        "reason_codes": reasons,
        "evidence": evidence,
        "clp_status": clp_status,
        "repo_mutating": repo_mut_value if repo_mut_known else None,
        "allowed_warning_reason_codes": allowed_warn,
        "blocked_warning_reason_codes": blocked_warn_codes,
        "human_review_required": human_review,
        "required_follow_up": follow_up,
        "evidence_hash": evidence_hash,
        "prl_evidence_status": prl_observation["status"],
        "prl_gate_recommendation": prl_observation["gate_recommendation"],
        "prl_failure_classes": prl_observation["failure_classes"],
        "prl_failure_packet_refs": prl_observation["failure_packet_refs"],
        "prl_repair_candidate_refs": prl_observation["repair_candidate_refs"],
        "prl_eval_candidate_refs": prl_observation["eval_candidate_refs"],
        "prl_artifact_refs": prl_observation["artifact_refs"]
        + [r for r in prl_index_artifact_refs if r not in prl_observation["artifact_refs"]],
        "prl_artifact_index_status": "present" if prl_index_present else "missing",
        "prl_artifact_index_reason_codes": list(prl_index_reason_codes),
        "prl_artifact_index_failure_packet_refs": prl_index_failure_packet_refs,
        "prl_artifact_index_repair_candidate_refs": prl_index_repair_candidate_refs,
        "prl_artifact_index_eval_candidate_refs": prl_index_eval_candidate_refs,
        "prl_artifact_index_generation_record_refs": prl_index_generation_record_refs,
        "shard_first_readiness_ref": shard_first_observation[
            "shard_first_observation_ref"
        ],
        "shard_first_status": shard_first_observation["shard_first_status"],
        "shard_first_evidence_status": shard_first_observation[
            "shard_first_evidence_status"
        ],
        "shard_first_reason_codes": list(
            shard_first_observation["shard_first_reason_codes"]
        ),
        "shard_first_fallback_used": shard_first_observation[
            "shard_first_fallback_used"
        ],
        "shard_first_full_suite_detected": shard_first_observation[
            "shard_first_full_suite_detected"
        ],
        "shard_first_fallback_reason_codes": list(
            shard_first_observation["shard_first_fallback_reason_codes"]
        ),
        "shard_first_required_shard_refs": list(
            shard_first_observation["shard_first_required_shard_refs"]
        ),
        "shard_first_fallback_justification_ref": shard_first_observation[
            "shard_first_fallback_justification_ref"
        ],
        "shard_first_artifact_refs": list(
            shard_first_observation["shard_first_artifact_refs"]
        ),
        "shard_first_required_for_repo_mutating": shard_first_required_for_repo_mutating,
        "shard_first_source": shard_first_observation["shard_first_source"],
    }


def build_agent_pr_update_ready_result(
    *,
    work_item_id: str,
    agent_type: str,
    policy_ref: str,
    evaluation: Mapping[str, Any],
    clp_result_ref: str | None,
    agl_record_ref: str | None,
    agent_pr_ready_result_ref: str | None,
    prl_result_ref: str | None = None,
    prl_artifact_index_ref: str | None = None,
    prl_auto_invocation: Mapping[str, Any] | None = None,
    shard_first_readiness_ref: str | None = None,
    source_artifact_refs: Iterable[str] | None = None,
    trace_refs: Iterable[str] | None = None,
    replay_refs: Iterable[str] | None = None,
    generated_at: str | None = None,
    guard_id: str | None = None,
) -> dict[str, Any]:
    if agent_type not in {"codex", "claude", "other", "unknown"}:
        agent_type = "unknown"
    ts = generated_at or utc_now_iso()
    gid = guard_id or stable_guard_id(work_item_id=work_item_id, generated_at=ts)
    evidence = dict(evaluation.get("evidence") or {})
    pr_section = _build_pr_evidence_section(evidence)
    sources = list(source_artifact_refs or [])
    resolved_shard_first_ref = (
        shard_first_readiness_ref
        if shard_first_readiness_ref
        else evaluation.get("shard_first_readiness_ref")
    )
    for ref in (
        clp_result_ref,
        agl_record_ref,
        agent_pr_ready_result_ref,
        prl_result_ref,
        prl_artifact_index_ref,
        resolved_shard_first_ref,
        policy_ref,
    ):
        if ref and ref not in sources:
            sources.append(ref)
    for ref in evaluation.get("prl_artifact_refs") or []:
        if isinstance(ref, str) and ref and ref not in sources:
            sources.append(ref)
    for ref in evaluation.get("shard_first_artifact_refs") or []:
        if isinstance(ref, str) and ref and ref not in sources:
            sources.append(ref)
    artifact: dict[str, Any] = {
        "artifact_type": "agent_pr_update_ready_result",
        "schema_version": "1.0.0",
        "guard_id": gid,
        "work_item_id": work_item_id,
        "agent_type": agent_type,
        "repo_mutating": evaluation.get("repo_mutating"),
        "policy_ref": policy_ref,
        "clp_result_ref": clp_result_ref,
        "agl_record_ref": agl_record_ref,
        "agent_pr_ready_result_ref": agent_pr_ready_result_ref,
        "prl_result_ref": prl_result_ref,
        "prl_artifact_index_ref": prl_artifact_index_ref,
        "prl_artifact_index_status": evaluation.get(
            "prl_artifact_index_status", "missing"
        ),
        "prl_auto_invocation": dict(prl_auto_invocation) if prl_auto_invocation else None,
        "prl_evidence_status": evaluation.get("prl_evidence_status", "missing"),
        "prl_gate_recommendation": evaluation.get("prl_gate_recommendation"),
        "prl_failure_classes": list(evaluation.get("prl_failure_classes") or []),
        "prl_failure_packet_refs": list(
            evaluation.get("prl_failure_packet_refs") or []
        ),
        "prl_repair_candidate_refs": list(
            evaluation.get("prl_repair_candidate_refs") or []
        ),
        "prl_eval_candidate_refs": list(
            evaluation.get("prl_eval_candidate_refs") or []
        ),
        "shard_first_readiness_ref": resolved_shard_first_ref,
        "shard_first_status": evaluation.get("shard_first_status", "missing"),
        "shard_first_evidence_status": evaluation.get(
            "shard_first_evidence_status", "missing"
        ),
        "shard_first_reason_codes": list(
            evaluation.get("shard_first_reason_codes") or []
        ),
        "shard_first_fallback_used": bool(evaluation.get("shard_first_fallback_used")),
        "shard_first_full_suite_detected": bool(
            evaluation.get("shard_first_full_suite_detected")
        ),
        "shard_first_fallback_reason_codes": list(
            evaluation.get("shard_first_fallback_reason_codes") or []
        ),
        "shard_first_required_for_repo_mutating": bool(
            evaluation.get("shard_first_required_for_repo_mutating", True)
        ),
        "readiness_status": evaluation.get("readiness_status", "not_ready"),
        "clp_status": evaluation.get("clp_status"),
        "reason_codes": list(evaluation.get("reason_codes") or []),
        "evidence": evidence,
        "allowed_warning_reason_codes": list(
            evaluation.get("allowed_warning_reason_codes") or []
        ),
        "blocked_warning_reason_codes": list(
            evaluation.get("blocked_warning_reason_codes") or []
        ),
        "source_artifact_refs": sources,
        "evidence_hash": evaluation.get("evidence_hash") or _evidence_hash(evidence),
        "trace_refs": list(trace_refs or []),
        "replay_refs": list(replay_refs or []),
        "authority_scope": "observation_only",
        "human_review_required": bool(evaluation.get("human_review_required")),
        "pr_evidence_section_markdown": pr_section,
        "generated_at": ts,
        "required_follow_up": list(evaluation.get("required_follow_up") or []),
    }
    return artifact


def readiness_status_to_exit_code(status: str) -> int:
    """ready=0, human_review_required=1, not_ready=2."""
    return {"ready": 0, "human_review_required": 1, "not_ready": 2}.get(status, 2)
