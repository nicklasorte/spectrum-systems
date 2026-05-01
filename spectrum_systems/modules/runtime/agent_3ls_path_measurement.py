"""M3L-02 — Agent 3LS Path Measurement (pure aggregation).

This module produces an ``agent_3ls_path_measurement_record``: a
measurement-only readout of whether an agent traversed the canonical
loop AEX -> PQX -> EVL -> TPA -> CDE -> SEL, where it fell out, and
what was the first missing leg / first failed check.

The module is pure aggregation. It reads existing artifacts
(``agent_pr_precheck_result`` (APR), ``core_loop_pre_pr_gate_result``
(CLP), ``agent_pr_update_ready_result`` (APU), and
``agent_core_loop_run_record`` (AGL)), and produces a single
observation. It MUST NOT:

- recompute upstream gates
- run any checks
- mutate any input artifact
- claim admission, execution, eval, policy, control, or final-gate
  authority

Canonical authority remains with AEX (admission), PQX (bounded
execution closure), EVL (eval evidence), TPA (policy/scope), CDE
(continuation/closure), SEL (final gate signal), LIN (lineage), REP
(replay), and GOV per ``docs/architecture/system_registry.md``. M3L
emits readiness observations and compliance observations only.

Mapping from inputs to 3LS legs
-------------------------------

The canonical leg order for measurement is::

    AEX -> PQX -> EVL -> TPA -> CDE -> SEL

For each leg the module gathers evidence from up to four input
artifacts. Each input is a non-owning support source; canonical
ownership is unchanged.

==== ===================================================================
Leg  Sources (in fall-back order)
==== ===================================================================
AEX  APR ``phase_summaries.AEX`` + ``checks[phase=AEX]``;
     APU ``evidence.AEX``; AGL ``loop_legs.AEX``;
     CLP ``checks[owner_system=AEX]``
PQX  APR ``phase_summaries.PQX`` + ``checks[phase=PQX]``;
     APU ``evidence.PQX``; AGL ``loop_legs.PQX``;
     CLP ``checks[owner_system=PQX]``
EVL  APR ``phase_summaries.EVL`` + ``checks[phase=EVL]``;
     APU ``evidence.EVL``; AGL ``loop_legs.EVL``;
     CLP ``checks[owner_system=EVL]``
TPA  APR ``phase_summaries.TPA`` + ``checks[phase=TPA]``;
     APU ``evidence.TPA``; AGL ``loop_legs.TPA``;
     CLP ``checks[owner_system=TPA]``
CDE  APR ``phase_summaries.CDE`` + ``checks[phase=CDE]``;
     APU ``evidence.CDE``; AGL ``loop_legs.CDE``;
     CLP ``checks[owner_system=CDE]``
SEL  APR ``phase_summaries.SEL`` + ``checks[phase=SEL]``;
     APU ``evidence.SEL``; AGL ``loop_legs.SEL``;
     CLP ``checks[owner_system=SEL]``
==== ===================================================================

Hard invariants
---------------

- ``present`` requires at least one ``artifact_ref``; bare ``present``
  without refs is downgraded to ``partial`` with a reason code.
- ``partial``/``missing``/``unknown`` legs require at least one reason
  code.
- ``unknown`` is never treated as ``present``.
- PR body prose, comments, CI success, and agent self-assertions
  cannot substitute for ``artifact_refs``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

LOOP_ORDER: tuple[str, ...] = ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL")

DEFAULT_OUTPUT_REL_PATH = (
    "outputs/agent_3ls_path_measurement/agent_3ls_path_measurement_record.json"
)

_AGENT_TYPES = {"codex", "claude", "other", "unknown", "unknown_ai_agent"}


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def stable_measurement_id(*, work_item_id: str, generated_at: str) -> str:
    raw = f"{work_item_id}|{generated_at}".encode("utf-8")
    return "m3l-path-" + hashlib.sha256(raw).hexdigest()[:16]


def _load_json_artifact(path: Path | None, expected_type: str) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
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


def load_apr_result(path: Path | None) -> dict[str, Any] | None:
    return _load_json_artifact(path, "agent_pr_precheck_result")


def load_clp_result(path: Path | None) -> dict[str, Any] | None:
    return _load_json_artifact(path, "core_loop_pre_pr_gate_result")


def load_apu_result(path: Path | None) -> dict[str, Any] | None:
    return _load_json_artifact(path, "agent_pr_update_ready_result")


def load_agl_record(path: Path | None) -> dict[str, Any] | None:
    return _load_json_artifact(path, "agent_core_loop_run_record")


# ---------------------------------------------------------------------------
# Per-source leg observation extractors
# ---------------------------------------------------------------------------


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if isinstance(v, str) and v]


def _leg_from_apr(apr: Mapping[str, Any] | None, leg: str) -> dict[str, Any] | None:
    if apr is None:
        return None
    summaries = apr.get("phase_summaries")
    if not isinstance(summaries, Mapping):
        return None
    summary = summaries.get(leg)
    if not isinstance(summary, Mapping):
        return None
    status = summary.get("status")
    summary_reason_codes = _string_list(summary.get("reason_codes"))
    artifact_refs: list[str] = []
    failed_check_reasons: list[str] = []
    for check in apr.get("checks") or []:
        if not isinstance(check, Mapping):
            continue
        if check.get("phase") != leg:
            continue
        check_status = check.get("status")
        if check_status == "pass":
            artifact_refs.extend(_string_list(check.get("output_artifact_refs")))
        elif check_status in {"warn", "block", "missing", "unknown", "skipped"}:
            failed_check_reasons.extend(_string_list(check.get("reason_codes")))
    if status == "pass":
        if artifact_refs:
            return {
                "status": "present",
                "artifact_refs": artifact_refs,
                "reason_codes": [],
                "source": "apr",
            }
        return {
            "status": "partial",
            "artifact_refs": [],
            "reason_codes": ["apr_phase_pass_without_artifact_refs"],
            "source": "apr",
        }
    if status == "warn":
        reasons = summary_reason_codes + failed_check_reasons or ["apr_phase_warn"]
        return {
            "status": "partial",
            "artifact_refs": artifact_refs,
            "reason_codes": list(dict.fromkeys(reasons)),
            "source": "apr",
        }
    if status in {"block", "missing"}:
        reasons = summary_reason_codes + failed_check_reasons or [
            f"apr_phase_{status}"
        ]
        return {
            "status": "missing",
            "artifact_refs": artifact_refs,
            "reason_codes": list(dict.fromkeys(reasons)),
            "source": "apr",
        }
    if status == "skipped":
        return {
            "status": "missing",
            "artifact_refs": artifact_refs,
            "reason_codes": summary_reason_codes or ["apr_phase_skipped"],
            "source": "apr",
        }
    if status == "unknown":
        return {
            "status": "unknown",
            "artifact_refs": artifact_refs,
            "reason_codes": summary_reason_codes or ["apr_phase_unknown"],
            "source": "apr",
        }
    return None


def _leg_from_apu(apu: Mapping[str, Any] | None, leg: str) -> dict[str, Any] | None:
    if apu is None:
        return None
    evidence = apu.get("evidence")
    if not isinstance(evidence, Mapping):
        return None
    payload = evidence.get(leg)
    if not isinstance(payload, Mapping):
        return None
    status = payload.get("status")
    artifact_refs = _string_list(payload.get("artifact_refs"))
    reason_codes = _string_list(payload.get("reason_codes"))
    if status == "present":
        if not artifact_refs:
            return {
                "status": "partial",
                "artifact_refs": [],
                "reason_codes": ["apu_present_without_artifact_refs"],
                "source": "apu",
            }
        return {
            "status": "present",
            "artifact_refs": artifact_refs,
            "reason_codes": [],
            "source": "apu",
        }
    if status in {"partial", "missing", "unknown"}:
        return {
            "status": status,
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes or [f"apu_status_{status}"],
            "source": "apu",
        }
    if status == "not_required":
        return {
            "status": "unknown",
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes or ["apu_status_not_required"],
            "source": "apu",
        }
    return None


def _leg_from_agl(agl: Mapping[str, Any] | None, leg: str) -> dict[str, Any] | None:
    if agl is None:
        return None
    legs = agl.get("loop_legs")
    if not isinstance(legs, Mapping):
        return None
    payload = legs.get(leg)
    if not isinstance(payload, Mapping):
        return None
    status = payload.get("status")
    artifact_refs = _string_list(payload.get("artifact_refs"))
    reason_codes = _string_list(payload.get("reason_codes"))
    if status == "present":
        if not artifact_refs:
            return {
                "status": "partial",
                "artifact_refs": [],
                "reason_codes": ["agl_present_without_artifact_refs"],
                "source": "agl",
            }
        return {
            "status": "present",
            "artifact_refs": artifact_refs,
            "reason_codes": [],
            "source": "agl",
        }
    if status in {"partial", "missing", "unknown"}:
        return {
            "status": status,
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes or [f"agl_status_{status}"],
            "source": "agl",
        }
    if status == "failed":
        return {
            "status": "partial",
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes or ["agl_status_failed"],
            "source": "agl",
        }
    if status == "not_required":
        return {
            "status": "unknown",
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes or ["agl_status_not_required"],
            "source": "agl",
        }
    return None


def _leg_from_clp(clp: Mapping[str, Any] | None, leg: str) -> dict[str, Any] | None:
    if clp is None:
        return None
    artifact_refs: list[str] = []
    reason_codes: list[str] = []
    has_pass = False
    has_warn = False
    has_block = False
    seen = False
    for check in clp.get("checks") or []:
        if not isinstance(check, Mapping):
            continue
        if check.get("owner_system") != leg:
            continue
        seen = True
        status = check.get("status")
        ref = check.get("output_ref")
        if isinstance(ref, str) and ref:
            artifact_refs.append(ref)
        for code in _string_list(check.get("reason_codes")):
            if code not in reason_codes:
                reason_codes.append(code)
        if status == "pass":
            has_pass = True
        elif status == "warn":
            has_warn = True
        elif status in {"block", "skipped"}:
            has_block = True
    if not seen:
        return None
    if has_block:
        return {
            "status": "missing",
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes or [f"clp_{leg.lower()}_check_blocked"],
            "source": "clp",
        }
    if has_warn:
        return {
            "status": "partial",
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes or [f"clp_{leg.lower()}_check_warn"],
            "source": "clp",
        }
    if has_pass and artifact_refs:
        return {
            "status": "present",
            "artifact_refs": artifact_refs,
            "reason_codes": [],
            "source": "clp",
        }
    return {
        "status": "unknown",
        "artifact_refs": artifact_refs,
        "reason_codes": reason_codes or [f"clp_{leg.lower()}_status_unknown"],
        "source": "clp",
    }


def _merge_leg_observations(
    leg: str,
    candidates: list[dict[str, Any] | None],
) -> dict[str, Any]:
    """Combine per-source observations into a single leg observation.

    Priority order is ``present`` > ``partial`` > ``missing`` > ``unknown``.
    Artifact refs and reason codes from contributing sources are merged.
    A leg with no candidates is reported as ``unknown`` with a default
    reason code.
    """
    real = [c for c in candidates if c is not None]
    if not real:
        return {
            "status": "unknown",
            "artifact_refs": [],
            "reason_codes": [f"{leg.lower()}_no_observation_available"],
            "source": "none",
        }
    rank = {"present": 0, "partial": 1, "missing": 2, "unknown": 3}
    chosen = min(real, key=lambda c: rank.get(c["status"], 4))
    artifact_refs: list[str] = []
    reason_codes: list[str] = []
    sources: list[str] = []
    for cand in real:
        for ref in cand.get("artifact_refs") or []:
            if ref not in artifact_refs:
                artifact_refs.append(ref)
        for code in cand.get("reason_codes") or []:
            if code not in reason_codes:
                reason_codes.append(code)
        src = cand.get("source")
        if isinstance(src, str) and src and src not in sources:
            sources.append(src)
    status = chosen["status"]
    if status == "present":
        if not artifact_refs:
            return {
                "status": "partial",
                "artifact_refs": [],
                "reason_codes": list(
                    dict.fromkeys(
                        reason_codes + [f"{leg.lower()}_present_without_artifact_refs"]
                    )
                ),
                "source": "+".join(sources) or "merged",
            }
        return {
            "status": "present",
            "artifact_refs": artifact_refs,
            "reason_codes": [],
            "source": "+".join(sources) or "merged",
        }
    if status in {"partial", "missing", "unknown"}:
        if not reason_codes:
            reason_codes = [f"{leg.lower()}_{status}_without_reason_codes"]
        return {
            "status": status,
            "artifact_refs": artifact_refs,
            "reason_codes": reason_codes,
            "source": "+".join(sources) or "merged",
        }
    return {
        "status": "unknown",
        "artifact_refs": artifact_refs,
        "reason_codes": reason_codes
        or [f"{leg.lower()}_status_unrecognized"],
        "source": "+".join(sources) or "merged",
    }


# ---------------------------------------------------------------------------
# Top-level derivation
# ---------------------------------------------------------------------------


def _resolve_pr_status(
    apr: Mapping[str, Any] | None,
    apu: Mapping[str, Any] | None,
    field: str,
) -> str:
    """Pull the PR (update) ready status from APR or APU. Defaults to ``unknown``."""
    if isinstance(apr, Mapping):
        value = apr.get(field)
        if value in {"ready", "not_ready", "human_review_required"}:
            return value
    if isinstance(apu, Mapping) and field == "pr_update_ready_status":
        readiness = apu.get("readiness_status")
        if readiness in {"ready", "not_ready", "human_review_required"}:
            return readiness
    return "unknown"


def _derive_first_failed_check(
    apr: Mapping[str, Any] | None,
    clp: Mapping[str, Any] | None,
) -> str | None:
    if isinstance(apr, Mapping):
        candidate = apr.get("first_failed_check")
        if isinstance(candidate, str) and candidate:
            return candidate
    if isinstance(clp, Mapping):
        candidate = clp.get("first_failed_check")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _normalize_agent_type(value: Any) -> str:
    if isinstance(value, str) and value in _AGENT_TYPES:
        return value
    return "unknown"


def _normalize_repo_mutating(
    explicit: bool | None,
    apr: Mapping[str, Any] | None,
    apu: Mapping[str, Any] | None,
    agl: Mapping[str, Any] | None,
) -> bool | None:
    if explicit is not None:
        return bool(explicit)
    for source in (apr, apu, agl):
        if isinstance(source, Mapping):
            value = source.get("repo_mutating")
            if isinstance(value, bool):
                return value
    return None


def build_agent_3ls_path_measurement_record(
    *,
    work_item_id: str,
    agent_type: str,
    repo_mutating: bool | None,
    apr_result: Mapping[str, Any] | None = None,
    clp_result: Mapping[str, Any] | None = None,
    apu_result: Mapping[str, Any] | None = None,
    agl_record: Mapping[str, Any] | None = None,
    apr_result_ref: str | None = None,
    clp_result_ref: str | None = None,
    apu_result_ref: str | None = None,
    agl_record_ref: str | None = None,
    generated_at: str | None = None,
    measurement_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate APR/CLP/APU/AGL evidence into a measurement record.

    This is pure aggregation. No gates are recomputed; no checks are
    run; no inputs are mutated. Canonical authority remains with the
    owner systems declared in ``docs/architecture/system_registry.md``.
    """
    ts = generated_at or utc_now_iso()
    mid = measurement_id or stable_measurement_id(
        work_item_id=work_item_id, generated_at=ts
    )
    normalized_agent = _normalize_agent_type(agent_type)
    normalized_repo_mut = _normalize_repo_mutating(
        repo_mutating, apr_result, apu_result, agl_record
    )

    loop_path: dict[str, dict[str, Any]] = {}
    for leg in LOOP_ORDER:
        candidates = [
            _leg_from_apr(apr_result, leg),
            _leg_from_apu(apu_result, leg),
            _leg_from_agl(agl_record, leg),
            _leg_from_clp(clp_result, leg),
        ]
        loop_path[leg] = _merge_leg_observations(leg, candidates)

    first_missing_leg: str | None = None
    fell_out_at: str | None = None
    for leg in LOOP_ORDER:
        observation = loop_path[leg]
        if observation["status"] == "missing" and first_missing_leg is None:
            first_missing_leg = leg
        if observation["status"] != "present" and fell_out_at is None:
            fell_out_at = leg

    loop_complete = all(
        loop_path[leg]["status"] == "present" for leg in LOOP_ORDER
    )

    if loop_complete:
        first_missing_leg = None
        fell_out_at = None

    first_failed_check = _derive_first_failed_check(apr_result, clp_result)
    pr_ready_status = _resolve_pr_status(apr_result, apu_result, "pr_ready_status")
    pr_update_ready_status = _resolve_pr_status(
        apr_result, apu_result, "pr_update_ready_status"
    )
    if normalized_repo_mut is None:
        pr_update_ready_status = "not_ready"

    aggregate_reason_codes: list[str] = []
    for leg in LOOP_ORDER:
        for code in loop_path[leg]["reason_codes"]:
            tagged = f"{leg.lower()}:{code}"
            if tagged not in aggregate_reason_codes:
                aggregate_reason_codes.append(tagged)

    source_artifact_refs = [
        ref
        for ref in (apr_result_ref, clp_result_ref, apu_result_ref, agl_record_ref)
        if isinstance(ref, str) and ref
    ]

    record: dict[str, Any] = {
        "artifact_type": "agent_3ls_path_measurement_record",
        "schema_version": "1.0.0",
        "measurement_id": mid,
        "created_at": ts,
        "work_item_id": work_item_id,
        "agent_type": normalized_agent,
        "repo_mutating": normalized_repo_mut,
        "loop_path": loop_path,
        "first_missing_leg": first_missing_leg,
        "first_failed_check": first_failed_check,
        "fell_out_at": fell_out_at,
        "loop_complete": loop_complete,
        "pr_ready_status": pr_ready_status,
        "pr_update_ready_status": pr_update_ready_status,
        "source_artifact_refs": source_artifact_refs,
        "apr_result_ref": apr_result_ref,
        "clp_result_ref": clp_result_ref,
        "apu_result_ref": apu_result_ref,
        "agl_record_ref": agl_record_ref,
        "reason_codes": aggregate_reason_codes,
        "authority_scope": "observation_only",
    }
    return record


def write_measurement_record(record: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
