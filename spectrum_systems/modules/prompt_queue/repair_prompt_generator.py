"""Deterministic FAIL-findings to bounded repair prompt generation."""

from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.prompt_queue.findings_artifact_io import validate_findings_artifact
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now

GENERATOR_VERSION = "1.0.0"
DEFAULT_NOT_IN_SCOPE = [
    "Automatic child repair work item creation.",
    "Automatic Codex execution.",
    "Semantic ranking across multiple findings artifacts.",
    "Dependency planning and queue parallelism.",
    "Repair-loop retry policy and merge/close automation.",
]


class RepairPromptGenerationError(ValueError):
    """Raised when repair prompt generation cannot proceed safely."""


def _unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _normalize_rel_path(path: str) -> str:
    value = path.strip()
    if not value:
        return value
    try:
        return str(Path(value).as_posix())
    except Exception:  # pragma: no cover - defensive path normalization
        return value


def _collect_likely_files(findings: dict) -> list[str]:
    file_refs: list[str] = []
    for section in ("required_fixes", "critical_findings"):
        for item in findings.get(section, []):
            file_refs.extend(_normalize_rel_path(v) for v in item.get("file_references", []))
    return _unique_ordered(file_refs)


def _derive_test_commands(likely_files: list[str]) -> list[str]:
    tests: list[str] = []
    for path in likely_files:
        if path.startswith("tests/") and path.endswith(".py"):
            tests.append(f"pytest -q {path}")
    return _unique_ordered(tests)


def _required_fixes_lines(findings: dict) -> list[str]:
    lines: list[str] = []
    for idx, item in enumerate(findings["required_fixes"], start=1):
        ref_files = item.get("file_references") or []
        files_suffix = ""
        if ref_files:
            quoted = ", ".join(f"`{_normalize_rel_path(p)}`" for p in ref_files)
            files_suffix = f" (files: {quoted})"
        lines.append(f"{idx}. [{item['finding_id']}] {item['summary']}: {item['body']}{files_suffix}")
    return lines


def _critical_context_lines(findings: dict) -> list[str]:
    lines: list[str] = []
    for idx, item in enumerate(findings.get("critical_findings", []), start=1):
        lines.append(f"{idx}. [{item['finding_id']}] {item['summary']}: {item['body']}")
    return lines


def _optional_out_of_scope(findings: dict) -> list[str]:
    not_in_scope = [
        f"{item['finding_id']}: {item['summary']}"
        for item in findings.get("optional_improvements", [])
    ]
    return _unique_ordered(not_in_scope + DEFAULT_NOT_IN_SCOPE)


def generate_repair_prompt_artifact(
    *,
    work_item: dict,
    findings_artifact: dict,
    source_findings_artifact_path: str,
    clock=utc_now,
) -> dict:
    validate_findings_artifact(findings_artifact)

    if findings_artifact.get("review_decision") != "FAIL":
        raise RepairPromptGenerationError(
            "Repair prompt generation is only allowed for FAIL review decisions."
        )

    required_fixes = findings_artifact.get("required_fixes", [])
    if not required_fixes:
        raise RepairPromptGenerationError("FAIL findings artifact must include at least one required fix.")

    generated_at = iso_now(clock)
    artifact_id = f"repair-prompt-{work_item['work_item_id']}-{generated_at.replace(':', '').replace('-', '')}"
    likely_files = _collect_likely_files(findings_artifact)
    suggested_test_commands = _derive_test_commands(likely_files)
    required_fix_lines = _required_fixes_lines(findings_artifact)
    critical_context_lines = _critical_context_lines(findings_artifact)
    not_in_scope = _optional_out_of_scope(findings_artifact)

    scope_summary = (
        f"Implement {len(required_fixes)} required fix(es) from FAIL findings for "
        f"work item {work_item['work_item_id']} in one bounded patch."
    )

    prompt_lines = [
        "Motivation",
        f"- Resolve FAIL review findings for work item {work_item['work_item_id']}.",
        "- Generate only a single bounded remediation patch from required fixes.",
        "",
        "Scope",
        f"- Work item: {work_item['work_item_id']}",
        f"- Source findings artifact: `{source_findings_artifact_path}`",
        f"- Source review artifact: `{findings_artifact['source_review_artifact_path']}`",
        "",
        "Required fixes",
        *required_fix_lines,
        "",
    ]

    if critical_context_lines:
        prompt_lines.extend(["Critical context (only to explain fix scope)", *critical_context_lines, ""])

    prompt_lines.extend(["Likely files involved"])
    prompt_lines.extend([f"- `{value}`" for value in likely_files] or ["- None specified in findings."])
    prompt_lines.extend(["", "Tests to run"])
    prompt_lines.extend([f"- {value}" for value in suggested_test_commands] or ["- No explicit tests inferred from file references."])
    prompt_lines.extend(
        [
            "",
            "Implementation constraints",
            "- Prioritize required fixes before any optional improvement.",
            "- Keep scope bounded to changes needed for required fixes and validating tests.",
            "- Preserve provider/fallback lineage metadata in artifacts.",
            "- Do not claim full closure beyond implemented required fixes.",
            "",
            "Not in scope",
            *[f"- {value}" for value in not_in_scope],
            "",
            "Mandatory delivery contract",
            "- Provide intent, architecture, guarantees, tests mapped to guarantees, failure modes, and remaining gaps.",
        ]
    )

    finding_ids_included = _unique_ordered(
        [item["finding_id"] for item in required_fixes]
        + [item["finding_id"] for item in findings_artifact.get("critical_findings", [])]
    )

    return {
        "repair_prompt_artifact_id": artifact_id,
        "work_item_id": work_item["work_item_id"],
        "source_findings_artifact_path": source_findings_artifact_path,
        "source_review_artifact_path": findings_artifact["source_review_artifact_path"],
        "review_provider": findings_artifact["review_provider"],
        "fallback_used": findings_artifact["fallback_used"],
        "fallback_reason": findings_artifact["fallback_reason"],
        "review_decision": "FAIL",
        "prompt_generation_status": "generated",
        "prompt_scope_summary": scope_summary,
        "prompt_text": "\n".join(prompt_lines),
        "required_fixes_count": len(required_fixes),
        "critical_findings_count": len(findings_artifact.get("critical_findings", [])),
        "likely_files": likely_files,
        "suggested_test_commands": suggested_test_commands,
        "bounded_not_in_scope": not_in_scope,
        "finding_ids_included": finding_ids_included,
        "generated_at": generated_at,
        "generator_version": GENERATOR_VERSION,
    }


def default_repair_prompt_path(*, work_item_id: str, root_dir: Path) -> Path:
    return root_dir / "artifacts" / "prompt_queue" / "repair_prompts" / f"{work_item_id}.repair_prompt.json"
