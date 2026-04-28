"""CL-22 / CL-24: Primary reason policy — pure selector.

Loads ``contracts/governance/primary_reason_policy.json`` and selects
exactly one primary canonical reason from a multi-stage failure set
using the stable precedence:

  admission > execution > eval > policy > decision > action

Supporting reasons are preserved alongside the elected primary reason.
The selector is non-owning. It does not enforce, gate, or decide. It
just makes block/freeze reason selection deterministic so an operator
sees one canonical headline plus full supporting detail every time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = (
    REPO_ROOT / "contracts" / "governance" / "primary_reason_policy.json"
)


class PrimaryReasonPolicyError(ValueError):
    """Raised only on programmer-misuse."""


def load_primary_reason_policy(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path is not None else POLICY_PATH
    if not p.exists():
        raise PrimaryReasonPolicyError(f"policy not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _classify_reason(
    reason_code: str, policy: Mapping[str, Any]
) -> Optional[str]:
    """Return the precedence class (admission/execution/...) for a reason
    code, or None if the code is not in the policy table.
    """
    table = policy.get("canonical_reason_codes") or {}
    for cls, codes in table.items():
        if reason_code in codes:
            return cls
    return None


def select_primary_reason(
    *,
    candidate_findings: Sequence[Mapping[str, Any]],
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a primary_reason record from a flat list of stage findings.

    Each finding shape: ``{"reason_code": str, "stage": "AEX|PQX|EVL|TPA|CDE|SEL",
    "detail": str|None, "failing_artifact_refs": list[str]?}``.

    Output:
      ``{"primary_canonical_reason": str, "source_stage": str, "supporting_reasons": [...],
        "failing_artifact_refs": [...], "next_allowed_action": str}``.
    """
    if policy is None:
        policy = load_primary_reason_policy()

    precedence = list(policy.get("precedence_order") or ())
    stage_to_class = policy.get("stage_to_precedence_class") or {}
    pass_code = policy.get("pass_reason_code") or "CORE_LOOP_PASS"

    if not candidate_findings:
        return {
            "primary_canonical_reason": pass_code,
            "source_stage": "NONE",
            "supporting_reasons": [],
            "failing_artifact_refs": [],
            "next_allowed_action": "allow_continuation",
        }

    by_class: Dict[str, List[Mapping[str, Any]]] = {p: [] for p in precedence}
    extras: List[Mapping[str, Any]] = []

    for finding in candidate_findings:
        if not isinstance(finding, Mapping):
            continue
        code = finding.get("reason_code")
        if not isinstance(code, str) or not code.strip():
            continue
        # Prefer explicit stage; fall back to reason-code lookup.
        stage = finding.get("stage")
        precedence_class = (
            stage_to_class.get(stage) if isinstance(stage, str) else None
        )
        if precedence_class is None:
            precedence_class = _classify_reason(code, policy)
        if precedence_class in by_class:
            by_class[precedence_class].append(finding)
        else:
            extras.append(finding)

    chosen: Optional[Mapping[str, Any]] = None
    chosen_class: Optional[str] = None
    for cls in precedence:
        if by_class[cls]:
            chosen = by_class[cls][0]
            chosen_class = cls
            break
    if chosen is None and extras:
        chosen = extras[0]
        chosen_class = "extra"

    if chosen is None:
        return {
            "primary_canonical_reason": pass_code,
            "source_stage": "NONE",
            "supporting_reasons": [],
            "failing_artifact_refs": [],
            "next_allowed_action": "allow_continuation",
        }

    primary_code = chosen.get("reason_code")
    primary_stage = chosen.get("stage") or _stage_for_class(chosen_class)
    failing_refs: List[str] = []
    supporting: List[Dict[str, Any]] = []
    for finding in candidate_findings:
        if finding is chosen:
            for r in finding.get("failing_artifact_refs") or ():
                if isinstance(r, str) and r.strip() and r not in failing_refs:
                    failing_refs.append(r)
            continue
        code = finding.get("reason_code")
        if not isinstance(code, str) or not code.strip():
            continue
        supporting.append(
            {
                "reason_code": code,
                "stage": finding.get("stage") or "AEX",
                "detail": finding.get("detail"),
            }
        )
        for r in finding.get("failing_artifact_refs") or ():
            if isinstance(r, str) and r.strip() and r not in failing_refs:
                failing_refs.append(r)

    next_action = next_action_for_class(chosen_class)

    return {
        "primary_canonical_reason": primary_code,
        "source_stage": primary_stage or "AEX",
        "supporting_reasons": supporting,
        "failing_artifact_refs": failing_refs,
        "next_allowed_action": next_action,
    }


def _stage_for_class(cls: Optional[str]) -> str:
    return {
        "admission": "AEX",
        "execution": "PQX",
        "eval": "EVL",
        "policy": "TPA",
        "decision": "CDE",
        "action": "SEL",
    }.get(cls or "", "AEX")


def next_action_for_class(cls: Optional[str]) -> str:
    """Map a precedence class to the next-allowed-action token used in
    the core loop proof's primary_reason.next_allowed_action.
    """
    if cls in ("admission", "execution", "eval", "policy"):
        return "block_no_mutation"
    if cls == "decision":
        return "freeze_hold"
    if cls == "action":
        return "block_no_mutation"
    return "no_action"


__all__ = [
    "POLICY_PATH",
    "PrimaryReasonPolicyError",
    "load_primary_reason_policy",
    "select_primary_reason",
    "next_action_for_class",
]
