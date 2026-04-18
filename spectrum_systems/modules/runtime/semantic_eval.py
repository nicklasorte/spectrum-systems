from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from spectrum_systems.modules.runtime.bne_utils import ensure_contract
from spectrum_systems.modules.wpg.common import normalize_text_tokens


SEMANTIC_EVAL_CLASSES = (
    "contradiction_detection",
    "grounding_check",
    "uncertainty_detection",
    "missing_question_detection",
    "answer_support_check",
)


@dataclass(frozen=True)
class SemanticEvalEvidence:
    recommended_action: str
    requires_control_review: bool
    blocking_reasons: List[str]
    severity_rollup: str


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    lower = text.lower()
    return any(needle in lower for needle in needles)


def _detect_contradictions(transcript: Dict[str, Any]) -> Dict[str, Any]:
    answers_by_question: Dict[str, set[str]] = {}
    for segment in transcript.get("segments", []):
        text = str(segment.get("text", ""))
        if "?" not in text:
            continue
        question = text.split("?", 1)[0].strip().lower()
        answer = text.split("?", 1)[1].strip().lower()
        normalized = "unknown"
        if _contains_any(answer, (" yes", "yes ", " yes.", " yes,")):
            normalized = "yes"
        elif _contains_any(answer, (" no", "no ", " no.", " no,")):
            normalized = "no"
        answers_by_question.setdefault(question, set()).add(normalized)

    contradictions = [q for q, vals in answers_by_question.items() if "yes" in vals and "no" in vals]
    passed = not contradictions
    return {
        "passed": passed,
        "severity": "HIGH" if contradictions else "LOW",
        "details": {
            "conflicting_questions": contradictions,
            "conflict_count": len(contradictions),
        },
    }


def _grounding_check(transcript: Dict[str, Any], faqs: List[Dict[str, Any]]) -> Dict[str, Any]:
    source_tokens = normalize_text_tokens(" ".join(str(s.get("text", "")) for s in transcript.get("segments", [])))
    unsupported_claims = []
    for idx, faq in enumerate(faqs, start=1):
        answer_tokens = normalize_text_tokens(str(faq.get("answer", "")))
        if answer_tokens and not (answer_tokens & source_tokens):
            unsupported_claims.append(f"faq-{idx:02d}")
    passed = not unsupported_claims
    return {
        "passed": passed,
        "severity": "HIGH" if unsupported_claims else "LOW",
        "details": {
            "unsupported_claims": unsupported_claims,
            "unsupported_count": len(unsupported_claims),
        },
    }


def _uncertainty_detection(faqs: List[Dict[str, Any]]) -> Dict[str, Any]:
    overconfident_unknowns = []
    for idx, faq in enumerate(faqs, start=1):
        answer = str(faq.get("answer", ""))
        if _contains_any(answer, ("unknown", "unclear", "not enough information")) and _contains_any(
            answer, ("definitely", "certainly", "always")
        ):
            overconfident_unknowns.append(f"faq-{idx:02d}")
    passed = not overconfident_unknowns
    return {
        "passed": passed,
        "severity": "MEDIUM" if overconfident_unknowns else "LOW",
        "details": {
            "overconfident_unknowns": overconfident_unknowns,
            "unknown_count": len(overconfident_unknowns),
        },
    }


def _missing_question_detection(transcript: Dict[str, Any], faqs: List[Dict[str, Any]]) -> Dict[str, Any]:
    transcript_questions = [str(s.get("text", "")).split("?", 1)[0].strip().lower() for s in transcript.get("segments", []) if "?" in str(s.get("text", ""))]
    faq_questions = [str(f.get("question", "")).strip().lower().rstrip("?") for f in faqs]
    missing = []
    for q in transcript_questions:
        if q and all(q not in fq for fq in faq_questions):
            missing.append(q)
    passed = not missing
    return {
        "passed": passed,
        "severity": "MEDIUM" if missing else "LOW",
        "details": {
            "missing_questions": missing,
            "missing_count": len(missing),
        },
    }


def _answer_support_check(transcript: Dict[str, Any], faqs: List[Dict[str, Any]]) -> Dict[str, Any]:
    lines = [str(s.get("text", "")).lower() for s in transcript.get("segments", [])]
    unsupported = []
    for idx, faq in enumerate(faqs, start=1):
        answer = str(faq.get("answer", "")).lower().strip()
        if answer and all(answer not in line for line in lines):
            unsupported.append(f"faq-{idx:02d}")
    passed = not unsupported
    return {
        "passed": passed,
        "severity": "HIGH" if unsupported else "LOW",
        "details": {
            "unsupported_answers": unsupported,
            "unsupported_count": len(unsupported),
        },
    }


def evaluate_semantic_classes(*, trace_id: str, stage: str, transcript: Dict[str, Any], faqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    evaluators = {
        "contradiction_detection": lambda: _detect_contradictions(transcript),
        "grounding_check": lambda: _grounding_check(transcript, faqs),
        "uncertainty_detection": lambda: _uncertainty_detection(faqs),
        "missing_question_detection": lambda: _missing_question_detection(transcript, faqs),
        "answer_support_check": lambda: _answer_support_check(transcript, faqs),
    }
    results: List[Dict[str, Any]] = []
    for eval_class in SEMANTIC_EVAL_CLASSES:
        output = evaluators[eval_class]()
        result = ensure_contract(
            {
                "artifact_type": "semantic_eval_result",
                "schema_version": "1.0.0",
                "trace_id": trace_id,
                "stage": stage,
                "eval_class": eval_class,
                "result": "pass" if output["passed"] else "fail",
                "severity": output["severity"],
                "indeterminate": False,
                "details": output["details"],
            },
            "semantic_eval_result",
        )
        results.append(result)
    return results


def summarize_semantic_evidence(results: List[Dict[str, Any]]) -> SemanticEvalEvidence:
    reasons: List[str] = []
    highest_severity = "LOW"
    severity_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

    by_class = {row.get("eval_class"): row for row in results}
    for row in results:
        severity = str(row.get("severity", "LOW")).upper()
        if severity_rank.get(severity, 0) > severity_rank[highest_severity]:
            highest_severity = severity

    contradiction = by_class.get("contradiction_detection", {})
    if contradiction.get("indeterminate"):
        reasons.append("contradiction_indeterminate")
    elif contradiction.get("result") == "fail":
        reasons.append("contradiction_detected")

    grounding = by_class.get("grounding_check", {})
    if grounding.get("result") == "fail":
        reasons.append("grounding_failure")

    if any(row.get("indeterminate") for row in results):
        reasons.append("indeterminate_eval")

    requires_control_review = bool(reasons)
    recommended_action = "control_review_required" if requires_control_review else "continue_with_monitoring"

    return SemanticEvalEvidence(
        recommended_action=recommended_action,
        requires_control_review=requires_control_review,
        blocking_reasons=reasons,
        severity_rollup=highest_severity,
    )
