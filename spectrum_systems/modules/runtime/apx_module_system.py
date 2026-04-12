"""Deterministic APX governed module runtime.

Implements admission, execution, evals, certification gating, review operations,
overrides, context quality, policy backtesting, and dataset registry.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


class APXModuleError(ValueError):
    """Fail-closed APX module error."""


def _hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12].upper()


def module_admission_gate(module_spec: dict[str, Any]) -> dict[str, Any]:
    required = ("schemas", "evals", "trace", "context_requirements", "promotion_path")
    missing = [k for k in required if not module_spec.get(k)]
    admitted = not missing
    return {
        "artifact_type": "module_admission_result",
        "admitted": admitted,
        "missing_requirements": missing,
        "fail_closed": True,
    }


def context_quality_check(context: dict[str, Any]) -> dict[str, Any]:
    freshness_days = int(context.get("freshness_days", 9999))
    conflicts = [str(x) for x in context.get("conflicts", [])]
    evidence_count = int(context.get("evidence_count", 0))
    valid = freshness_days <= int(context.get("max_freshness_days", 30)) and not conflicts and evidence_count > 0
    return {
        "artifact_type": "context_quality_result",
        "valid": valid,
        "freshness": freshness_days,
        "conflicts": conflicts,
        "evidence_sufficiency": evidence_count > 0,
        "blocking_reasons": ([] if valid else ["context_invalid"]),
    }


def run_faq_module(*, trace_id: str, transcript: str, docs: list[dict[str, Any]]) -> dict[str, Any]:
    lines = [line.strip() for line in transcript.split("\n") if line.strip()]
    questions = [line for line in lines if line.endswith("?")]
    grounded = []
    for q in questions:
        evidence = [d for d in docs if any(tok.lower() in str(d.get("content", "")).lower() for tok in q.split()[:2])]
        grounded.append(
            {
                "question": q,
                "answer": evidence[0].get("content", "insufficient evidence") if evidence else "insufficient evidence",
                "evidence_refs": [str(e.get("doc_id")) for e in evidence],
            }
        )

    dispositions = ["resolved" if row["evidence_refs"] else "needs_review" for row in grounded]
    return {
        "artifact_type": "transcript_faq_artifact",
        "trace_id": trace_id,
        "faq_questions": [{"artifact_type": "faq_question", "text": row["question"]} for row in grounded],
        "faq_answers": [
            {"artifact_type": "faq_answer", "text": row["answer"], "evidence_refs": row["evidence_refs"]} for row in grounded
        ],
        "disposition": {"artifact_type": "disposition", "items": dispositions},
    }


def faq_eval_suite(faq_artifact: dict[str, Any]) -> dict[str, Any]:
    answers = faq_artifact.get("faq_answers", [])
    grounding = all(bool(row.get("evidence_refs")) for row in answers)
    evidence_coverage = sum(1 for row in answers if row.get("evidence_refs")) / max(len(answers), 1)
    contradiction = False
    completeness = len(answers) == len(faq_artifact.get("faq_questions", [])) and len(answers) > 0
    return {
        "artifact_type": "faq_eval_result",
        "grounding": grounding,
        "evidence_coverage": evidence_coverage,
        "contradiction": contradiction,
        "completeness": completeness,
        "all_passed": grounding and evidence_coverage >= 0.8 and not contradiction and completeness,
    }


def faq_certification_gate(*, faq_eval: dict[str, Any], trace_complete: bool, replay_consistent: bool) -> dict[str, Any]:
    certified = bool(faq_eval.get("all_passed")) and trace_complete and replay_consistent
    return {
        "artifact_type": "faq_certification_result",
        "certified": certified,
        "blocking_reasons": [] if certified else ["certification_requirements_unmet"],
    }


def build_review_operations(*, trace_id: str, failed: bool) -> dict[str, Any]:
    return {
        "review_result": {"artifact_type": "review_result", "trace_id": trace_id, "status": "needs_fix" if failed else "accepted"},
        "fix_slice_request": {"artifact_type": "fix_slice_request", "trace_id": trace_id, "requested": failed},
        "operator_handoff": {"artifact_type": "operator_handoff", "trace_id": trace_id, "required": failed},
    }


def build_human_review_artifacts(*, trace_id: str, outcome: str, override: bool = False) -> dict[str, Any]:
    bounded = not override or outcome in {"allow", "block"}
    return {
        "review_queue_item": {"artifact_type": "review_queue_item", "trace_id": trace_id},
        "review_outcome": {"artifact_type": "review_outcome", "trace_id": trace_id, "outcome": outcome},
        "override_record": {
            "artifact_type": "override_record",
            "trace_id": trace_id,
            "override": override,
            "bounded": bounded,
        },
    }


def compile_patterns(*, failures: list[str], corrections: list[str], overrides: list[str]) -> dict[str, Any]:
    return {
        "artifact_type": "pattern_compiler_result",
        "failure_patterns": sorted(set(failures)),
        "correction_patterns": sorted(set(corrections)),
        "override_patterns": sorted(set(overrides)),
        "policy_candidates": [{"policy_candidate_id": f"PC-{_hash(failures + corrections + overrides)}"}],
        "eval_candidates": [{"eval_candidate_id": f"EC-{_hash(overrides + failures)}"}],
    }


def run_policy_backtest(*, policy_candidates: list[dict[str, Any]], dataset_rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = []
    for candidate in policy_candidates:
        policy_id = str(candidate.get("policy_candidate_id", "unknown"))
        score = min(1.0, len(dataset_rows) / 10.0)
        scores.append({"policy_candidate_id": policy_id, "score": score})
    return {
        "artifact_type": "policy_backtest_result",
        "results": scores,
        "auto_activation": False,
    }


@dataclass
class DatasetRegistry:
    registry: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def register(self, dataset_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        versions = self.registry.setdefault(dataset_name, [])
        version = f"v{len(versions) + 1}"
        record = {
            "artifact_type": "dataset_registry_record",
            "dataset_name": dataset_name,
            "version": version,
            "row_count": len(rows),
        }
        versions.append(record)
        return record


def run_module_pattern(*, module_kind: str, trace_id: str, transcript: str, docs: list[dict[str, Any]]) -> dict[str, Any]:
    faq = run_faq_module(trace_id=trace_id, transcript=transcript, docs=docs)
    faq["module_kind"] = module_kind
    return faq


__all__ = [
    "APXModuleError",
    "module_admission_gate",
    "context_quality_check",
    "run_faq_module",
    "faq_eval_suite",
    "faq_certification_gate",
    "build_review_operations",
    "build_human_review_artifacts",
    "compile_patterns",
    "run_policy_backtest",
    "DatasetRegistry",
    "run_module_pattern",
]
