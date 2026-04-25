"""Leakage and tamper detection for HOP harness candidates.

These checks complement the validator. They look at the candidate's *code
source* and the produced eval-case-keyed outputs and try to detect:

- ``hardcoded_answer``: candidate code embeds a verbatim eval-case answer
  substring (or any forbidden substring listed by an eval case).
- ``eval_dataset_leakage``: candidate code embeds eval_case_id strings or
  reads eval files at runtime.
- ``schema_weakening``: candidate code attempts to monkey-patch or weaken
  HOP schema validation (e.g. by writing to ``_TYPE_TO_DIR``,
  ``additionalProperties``, or by replacing ``validate_hop_artifact``).
- ``eval_bypass_attempt``: candidate code references the experience store's
  internal write path or skips the evaluator API.

Every detection emits a ``hop_harness_failure_hypothesis`` artifact at
severity ``reject``. The candidate is rejected before the evaluator runs.

The scan is intentionally a static, deterministic textual matcher — it does
NOT execute candidate code. Static matching can yield false positives, but
HOP's policy is fail-closed: a flagged candidate is rejected and the
operator must rewrite or annotate it. False negatives are addressed by
combining safety_checks with the evaluator's per-case sandbox.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

# Patterns that suggest schema-weakening intent.
_SCHEMA_WEAKENING_PATTERNS: tuple[str, ...] = (
    "additionalProperties",
    "_TYPE_TO_DIR",
    "validate_hop_artifact = ",
    "validate_hop_artifact=",
    "monkeypatch",
    "Draft202012Validator = ",
    "load_hop_schema = ",
    "schemas._SCHEMA_FILES",
)

# Patterns that suggest eval bypass.
_EVAL_BYPASS_PATTERNS: tuple[str, ...] = (
    "experience_store._path_for",
    "ExperienceStore._build_index_record",
    "ExperienceStore.write_artifact = ",
    "evaluator.run_candidate = ",
    "evaluator.evaluate_candidate = ",
    "open(\"contracts/evals/hop",
    "open('contracts/evals/hop",
    "Path('contracts/evals/hop')",
    "Path(\"contracts/evals/hop\")",
)


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _build_failure(
    *,
    candidate_id: str,
    failure_class: str,
    evidence: list[dict[str, str]],
    trace_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_failure_hypothesis",
        "schema_ref": "hop/harness_failure_hypothesis.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "hypothesis_id": f"sc_{failure_class}_{candidate_id}",
        "candidate_id": candidate_id,
        "run_id": None,
        "stage": "safety_check",
        "failure_class": failure_class,
        "severity": "reject",
        "evidence": evidence,
        "detected_at": _utcnow(),
        "release_block_signal": True,
    }
    finalize_artifact(payload, id_prefix="hop_failure_")
    return payload


_TRANSCRIPT_ID_MIN_LENGTH_FOR_SCAN = 12


def _collect_eval_signals(
    eval_cases: Iterable[Mapping[str, Any]],
) -> tuple[set[str], set[str], set[str]]:
    """Return (eval_ids_and_long_transcript_ids, leak_substrings, forbidden_substrings)."""
    ids: set[str] = set()
    leak: set[str] = set()
    forbidden: set[str] = set()
    for case in eval_cases:
        case_id = case.get("eval_case_id")
        if isinstance(case_id, str):
            ids.add(case_id)
        # Only scan transcript_id substrings that are long enough to be
        # uniquely identifying — short ids ("t_short") would produce false
        # positives against innocuous English text.
        transcript_id = case.get("input", {}).get("transcript_id")
        if (
            isinstance(transcript_id, str)
            and len(transcript_id) >= _TRANSCRIPT_ID_MIN_LENGTH_FOR_SCAN
        ):
            ids.add(transcript_id)
        rules = case.get("pass_criteria", {}).get("rules", {})
        for pair in rules.get("expected_answer_substrings_per_question", []) or []:
            answer = pair.get("answer_substring")
            if isinstance(answer, str) and len(answer) >= 6:
                # Treat long expected answer substrings as leakage signals.
                leak.add(answer)
        for forb in rules.get("forbidden_substrings_in_answers", []) or []:
            if isinstance(forb, str) and forb:
                forbidden.add(forb)
    return ids, leak, forbidden


def scan_candidate(
    candidate_payload: Mapping[str, Any],
    eval_cases: Iterable[Mapping[str, Any]],
    *,
    trace_id: str = "hop_safety_checks",
) -> tuple[bool, list[dict[str, Any]]]:
    """Static scan of candidate source against eval-derived signals.

    Returns ``(ok, failures)``. ``ok`` is True only if no block-severity issue
    was detected.
    """
    failures: list[dict[str, Any]] = []
    candidate_id = candidate_payload.get("candidate_id") or "unknown"
    code = candidate_payload.get("code_source") or ""

    eval_ids, leak_substrings, forbidden_substrings = _collect_eval_signals(eval_cases)

    # eval_dataset_leakage — eval_case_id appears in code
    leaked_ids = sorted(eid for eid in eval_ids if eid and eid in code)
    if leaked_ids:
        failures.append(
            _build_failure(
                candidate_id=str(candidate_id),
                failure_class="eval_dataset_leakage",
                evidence=[
                    {"kind": "snippet", "detail": "eval_case_ids=" + ",".join(leaked_ids)},
                ],
                trace_id=trace_id,
            )
        )

    # hardcoded_answer — expected answer substrings appear directly in code
    hardcoded = sorted(s for s in leak_substrings if s in code)
    if hardcoded:
        failures.append(
            _build_failure(
                candidate_id=str(candidate_id),
                failure_class="hardcoded_answer",
                evidence=[
                    {"kind": "snippet", "detail": "hardcoded=" + "|".join(hardcoded)},
                ],
                trace_id=trace_id,
            )
        )

    # forbidden substrings — explicit "must not appear in code" markers
    forbidden_hits = sorted(s for s in forbidden_substrings if s in code)
    if forbidden_hits:
        failures.append(
            _build_failure(
                candidate_id=str(candidate_id),
                failure_class="hardcoded_answer",
                evidence=[
                    {
                        "kind": "snippet",
                        "detail": "forbidden=" + "|".join(forbidden_hits),
                    }
                ],
                trace_id=trace_id,
            )
        )

    # schema_weakening
    weakening_hits = sorted(p for p in _SCHEMA_WEAKENING_PATTERNS if p in code)
    if weakening_hits:
        failures.append(
            _build_failure(
                candidate_id=str(candidate_id),
                failure_class="schema_weakening",
                evidence=[
                    {"kind": "snippet", "detail": "weakening=" + "|".join(weakening_hits)},
                ],
                trace_id=trace_id,
            )
        )

    # eval_bypass
    bypass_hits = sorted(p for p in _EVAL_BYPASS_PATTERNS if p in code)
    if bypass_hits:
        failures.append(
            _build_failure(
                candidate_id=str(candidate_id),
                failure_class="eval_bypass_attempt",
                evidence=[
                    {"kind": "snippet", "detail": "bypass=" + "|".join(bypass_hits)},
                ],
                trace_id=trace_id,
            )
        )

    return not failures, failures
