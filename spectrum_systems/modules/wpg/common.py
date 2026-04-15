from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Set

from spectrum_systems.contracts import validate_artifact

POLICY_VERSION = "1.0.0"
EVAL_VERSION = "1.0.0"
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


class WPGError(Exception):
    """Raised when the WPG pipeline cannot continue under fail-closed policy."""


@dataclass(frozen=True)
class StageContext:
    run_id: str
    trace_id: str
    policy_version: str = POLICY_VERSION
    eval_version: str = EVAL_VERSION


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stage_provenance(stage_name: str, ctx: StageContext, input_refs: Iterable[str]) -> Dict[str, Any]:
    return {
        "stage": stage_name,
        "run_id": ctx.run_id,
        "trace_id": ctx.trace_id,
        "policy_version": ctx.policy_version,
        "eval_version": ctx.eval_version,
        "input_hash": stable_hash(sorted(input_refs)),
    }


def normalize_text_tokens(text: str) -> Set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token and token not in _STOPWORDS
    }


def jaccard_similarity(left: Sequence[str] | Set[str], right: Sequence[str] | Set[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def normalize_transcript_payload(transcript_payload: Dict[str, Any], *, trace_id: str) -> Dict[str, Any]:
    source_segments = transcript_payload.get("segments", []) if isinstance(transcript_payload, dict) else []
    if not isinstance(source_segments, list):
        raise WPGError("transcript segments must be a list")

    segments: List[Dict[str, Any]] = []
    for idx, raw in enumerate(source_segments, start=1):
        if not isinstance(raw, dict):
            raise WPGError("transcript segment must be an object")
        seg = {
            "segment_id": str(raw.get("segment_id") or f"seg-{idx}"),
            "speaker": str(raw.get("speaker") or "unknown"),
            "agency": str(raw.get("agency") or "unknown"),
            "text": str(raw.get("text") or "").strip(),
        }
        timestamp = raw.get("timestamp")
        if timestamp is not None:
            seg["timestamp"] = str(timestamp)
        if not seg["text"]:
            raise WPGError(f"transcript segment text missing at index {idx}")
        segments.append(seg)

    if not segments:
        raise WPGError("transcript must include at least one segment")

    identity_input = {
        "segments": segments,
        "source_refs": transcript_payload.get("source_refs", []),
        "meeting_id": transcript_payload.get("meeting_id"),
    }
    artifact_identity = f"trx-{stable_hash(identity_input)[:16]}"

    return {
        "artifact_type": "transcript_artifact",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {
            "artifact_id": artifact_identity,
            "metadata": {
                "segment_count": len(segments),
                "has_timestamps": any("timestamp" in seg for seg in segments),
                "meeting_id": transcript_payload.get("meeting_id", "unknown"),
            },
            "source_refs": transcript_payload.get("source_refs", []),
            "segments": segments,
            "provenance": {
                "ingress": "wpg_pipeline",
                "normalization": "deterministic",
                "identity_hash": stable_hash(identity_input),
            },
        },
    }


def make_eval_artifacts(stage: str, checks: List[Dict[str, Any]], ctx: StageContext) -> Dict[str, Any]:
    eval_cases: List[Dict[str, Any]] = []
    eval_results: List[Dict[str, Any]] = []
    for idx, check in enumerate(checks, start=1):
        cid = f"{stage}-case-{idx:02d}"
        passed = bool(check.get("passed", False))
        score = 1.0 if passed else 0.0
        eval_cases.append(
            {
                "artifact_type": "eval_case",
                "schema_version": "1.0.0",
                "run_id": ctx.run_id,
                "trace_id": ctx.trace_id,
                "eval_case_id": cid,
                "input_artifact_refs": check.get("input_refs", [stage]),
                "expected_output_spec": {"description": check.get("description", "")},
                "scoring_rubric": {"pass_condition": check.get("description", "")},
                "evaluation_type": "deterministic",
                "created_from": "manual",
            }
        )
        eval_results.append(
            {
                "artifact_type": "eval_result",
                "schema_version": "1.0.0",
                "eval_case_id": cid,
                "run_id": ctx.run_id,
                "trace_id": ctx.trace_id,
                "result_status": "pass" if passed else "fail",
                "score": score,
                "failure_modes": [] if passed else [check.get("failure_mode", "stage_failure")],
                "provenance_refs": [stage],
            }
        )

    pass_rate = sum(1 for r in eval_results if r["result_status"] == "pass") / max(len(eval_results), 1)
    summary = {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": ctx.trace_id,
        "eval_run_id": f"{ctx.run_id}:{stage}",
        "pass_rate": pass_rate,
        "failure_rate": 1 - pass_rate,
        "drift_rate": 0.0,
        "reproducibility_score": 1.0,
        "system_status": "healthy" if pass_rate == 1.0 else "degraded",
    }
    return {"eval_case": eval_cases, "eval_result": eval_results, "eval_summary": summary}


def control_decision_from_eval(
    *,
    stage: str,
    eval_summary: Dict[str, Any],
    contradictions_unresolved: int = 0,
    low_confidence_count: int = 0,
    no_content: bool = False,
    unknown_count: int = 0,
    grounding_failures: int = 0,
) -> Dict[str, Any]:
    decision = "ALLOW"
    reasons: List[str] = []

    if eval_summary.get("pass_rate", 0) < 1.0:
        reasons.append("missing_or_failed_eval")
        decision = "BLOCK"
    if no_content:
        reasons.append("no_content")
        decision = "BLOCK"
    if grounding_failures > 0:
        reasons.append("grounding_failure")
        decision = "BLOCK"
    if contradictions_unresolved > 0:
        reasons.append("contradictions_unresolved")
        decision = "BLOCK" if contradictions_unresolved > 1 else "WARN"
    if unknown_count > 0 and decision == "ALLOW":
        decision = "WARN"
        reasons.append("unknown_state")
    if low_confidence_count > 0 and decision == "ALLOW":
        decision = "WARN"
        reasons.append("low_confidence")

    return {
        "stage": stage,
        "decision": decision,
        "reasons": reasons,
        "enforcement": {
            "action": {
                "ALLOW": "proceed",
                "WARN": "annotate",
                "BLOCK": "trigger_repair",
                "FREEZE": "halt",
            }[decision]
        },
    }


def ensure_contract(artifact: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
    validate_artifact(artifact, schema_name)
    return artifact


def deterministic_copy(payload: Dict[str, Any]) -> Dict[str, Any]:
    return deepcopy(payload)
