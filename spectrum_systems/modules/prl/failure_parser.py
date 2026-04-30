"""PRL-01: Regex-based CI log parser producing normalized failure messages.

No LLM. Deterministic pattern matching only. Fail-closed: non-zero exit with
no matched pattern emits unknown_failure rather than silently succeeding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ParsedFailure:
    failure_class: str
    raw_excerpt: str
    normalized_message: str
    file_refs: tuple[str, ...]
    line_number: Optional[int]
    exit_code: Optional[int]


# Ordered list: first match wins. More specific patterns first.
_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "authority_shape_violation",
        re.compile(
            r"authority.shape.violation|authority_shape_leak|authority_leak"
            r"|cert_missing_authority_shape_preflight|AGS-\d+.*violation"
            r"|AUTHORITY_SHAPE_VIOLATION"
            r"|violation_count.*[1-9]|canonical_owners",
            re.IGNORECASE,
        ),
        "Authority shape violation detected in changed files",
    ),
    (
        "system_registry_mismatch",
        re.compile(
            r"registry[\._\s]mismatch|system_registry_mismatch"
            r"|validate_system_registry.*FAIL|registry.*not.*registered"
            r"|canonical.*owner.*missing"
            r"|INCOMPLETE_SYSTEM_REGISTRATION|UNOWNED_SYSTEM_SURFACE"
            r"|SHADOW_OWNERSHIP_OVERLAP|DIRECT_OWNERSHIP_OVERLAP"
            r"|PROTECTED_AUTHORITY_VIOLATION|NEW_SYSTEM_MISSING_REGISTRATION"
            r"|AMBIGUOUS_SYSTEM_SURFACE|ACRONYM_NAMESPACE_COLLISION"
            r"|REMOVED_SYSTEM_REFERENCE|SRG_OWNER_INTRODUCTION_FORBIDDEN",
            re.IGNORECASE,
        ),
        "System registry mismatch or guard failure",
    ),
    (
        "contract_schema_violation",
        re.compile(
            r"jsonschema\.exceptions|ValidationError.*schema|contract.schema"
            r"|schema.validation.fail|additionalProperties.*false"
            r"|required.*property.*missing|is not valid under any of"
            r"|is a required property"
            r"|schema_violation|contract_mismatch|control_surface_gap",
            re.IGNORECASE,
        ),
        "Contract schema validation failure",
    ),
    (
        "missing_required_artifact",
        re.compile(
            r"missing.required.artifact|artifact.*not.*found"
            r"|obs_missing|missing_artifact|halt.*missing"
            r"|FileNotFoundError.*artifact|artifact.*absent",
            re.IGNORECASE,
        ),
        "Required artifact is missing",
    ),
    (
        "trace_missing",
        re.compile(
            r"trace.id.*missing|trace.*missing|trace_refs.*empty"
            r"|lineage_missing_trace_id|ArtifactEnvelopeError.*trace"
            r"|primary.*trace.*empty",
            re.IGNORECASE,
        ),
        "Trace reference missing from artifact",
    ),
    (
        "replay_mismatch",
        re.compile(
            r"replay.hash.mismatch|replay.mismatch|replay_integrity.*fail"
            r"|replay.*non.replayable|replay.*not.*deterministic"
            r"|REPLAY_MISMATCH",
            re.IGNORECASE,
        ),
        "Replay integrity mismatch — non-deterministic output",
    ),
    (
        "policy_mismatch",
        re.compile(
            r"policy.mismatch|policy.violation|policy.drift|trust.policy.block"
            r"|tier_drift|tier_indirect|POLICY_MISMATCH"
            r"|downstream_test_failure",
            re.IGNORECASE,
        ),
        "Policy mismatch or violation",
    ),
    (
        "pytest_selection_missing",
        re.compile(
            r"no tests ran|collected 0 items"
            r"|ERROR collecting|pytest.*error.*no.*test|selection.*guard.*missing"
            r"|no module named.*test|test_inventory_regression",
            re.IGNORECASE,
        ),
        "Pytest test selection missing or no tests collected",
    ),
    (
        "timeout",
        re.compile(
            r"TimeoutError|timed?\s*out|timeout.*exceeded|deadline.*exceeded"
            r"|signal\.SIGALRM|execution.*timeout",
            re.IGNORECASE,
        ),
        "Execution timeout",
    ),
    (
        "rate_limited",
        re.compile(
            r"rate.limit|HTTP\s+429|too many requests|RateLimitError"
            r"|quota.*exceeded|backoff.*required",
            re.IGNORECASE,
        ),
        "Rate limited by external service",
    ),
]

_FILE_REF_PATTERN = re.compile(r"([\w/\-\.]+\.(?:py|json|ya?ml|md|txt|sh|toml))(?::(\d+))?")


def _extract_file_refs(text: str) -> tuple[tuple[str, ...], Optional[int]]:
    matches = _FILE_REF_PATTERN.findall(text)
    files: list[str] = []
    line_number: Optional[int] = None
    for fname, lineno in matches:
        if fname not in files:
            files.append(fname)
        if lineno and line_number is None:
            try:
                line_number = int(lineno)
            except ValueError:
                pass
    return tuple(files), line_number


def parse_log_line(line: str) -> Optional[ParsedFailure]:
    """Parse one log line. Returns ParsedFailure on first pattern match, else None."""
    for failure_class, pattern, message in _PATTERNS:
        if pattern.search(line):
            file_refs, line_number = _extract_file_refs(line)
            return ParsedFailure(
                failure_class=failure_class,
                raw_excerpt=line[:500].strip(),
                normalized_message=message,
                file_refs=file_refs,
                line_number=line_number,
                exit_code=None,
            )
    return None


def parse_log(log_text: str, *, exit_code: Optional[int] = None) -> list[ParsedFailure]:
    """Parse a full CI log. Returns deduplicated ParsedFailure list.

    Fail-closed: non-zero exit with zero matches emits unknown_failure.
    """
    seen: set[str] = set()
    results: list[ParsedFailure] = []

    for line in log_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        failure = parse_log_line(stripped)
        if failure is None:
            continue
        key = f"{failure.failure_class}:{failure.raw_excerpt[:100]}"
        if key in seen:
            continue
        seen.add(key)
        if exit_code is not None:
            failure = ParsedFailure(
                failure_class=failure.failure_class,
                raw_excerpt=failure.raw_excerpt,
                normalized_message=failure.normalized_message,
                file_refs=failure.file_refs,
                line_number=failure.line_number,
                exit_code=exit_code,
            )
        results.append(failure)

    if not results and exit_code is not None and exit_code != 0:
        results.append(
            ParsedFailure(
                failure_class="unknown_failure",
                raw_excerpt=log_text[:500].strip(),
                normalized_message="Unclassified failure from non-zero exit code",
                file_refs=(),
                line_number=None,
                exit_code=exit_code,
            )
        )

    return results
