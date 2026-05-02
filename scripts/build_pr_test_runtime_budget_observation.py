#!/usr/bin/env python3
"""EVL-RT-01 PR test runtime budget observation builder.

Emits an observation-only ``pr_test_runtime_budget_observation`` artifact
at ``outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json``
that records, for a PR's already-measured pytest run:

- the changed files and selected test targets (read from the existing
  ``selection_coverage_record`` artifact),
- the per-shard durations, total duration, and slowest shard (read from
  the existing ``pr_test_shards_summary`` artifact),
- whether the PR fell back to broad / full-suite testing,
- the configured runtime budget in seconds,
- the resulting ``budget_status`` (``within_budget`` | ``over_budget`` |
  ``unknown``),
- reason codes for ``unknown`` / ``over_budget`` / fallback usage,
- observation-only improvement recommendations (slowest shard, full-suite
  fallback, missing mapping signal, over-budget signal).

The builder reuses existing artifacts. It does NOT:

- run pytest,
- mutate test selection,
- duplicate the canonical PR test selector,
- block PRs,
- weaken or reduce required tests.

Authority scope: ``observation_only``. The artifact emits runtime,
fallback, and recommendation observations only. Canonical ownership of
the selector, shard runner, override policy, and any upstream gate
authority remains with the systems declared in
``docs/architecture/system_registry.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402

DEFAULT_SHARD_SUMMARY_REL_PATH = (
    "outputs/pr_test_shards/pr_test_shards_summary.json"
)
DEFAULT_SELECTION_COVERAGE_REL_PATH = (
    "outputs/selection_coverage/selection_coverage_record.json"
)
DEFAULT_OUTPUT_REL_PATH = (
    "outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json"
)

DEFAULT_RUNTIME_BUDGET_SECONDS: float = 300.0

_FULL_SUITE_TARGET_TOKENS: frozenset[str] = frozenset(
    {"tests", "tests/", "."}
)
_FULL_SUITE_FALLBACK_REASON_TOKENS: tuple[str, ...] = (
    "fallback_full_suite",
    "fallback_full_test_suite",
    "select_all_tests",
    "no_governed_paths_matched",
)


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(*, base_ref: str, head_ref: str, created_at: str) -> str:
    raw = f"{base_ref}|{head_ref}|{created_at}".encode("utf-8")
    return "pr-rt-budget-" + hashlib.sha256(raw).hexdigest()[:16]


def _ref_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _detect_full_suite(
    *,
    selected_test_targets: list[str],
    selection_reason_codes: list[str],
    fallback_used: bool,
    fallback_targets: list[str],
) -> tuple[bool, list[str]]:
    """Return ``(full_suite_detected, fallback_reason_codes)``.

    Detection is conservative and observation-only:

    - any selected target equal to a full-suite token (e.g. ``tests``,
      ``tests/``, ``.``) is treated as broad fallback,
    - any selection_reason_code matching a known full-suite fallback
      token is treated as broad fallback,
    - any fallback_target containing a full-suite token is treated as
      broad fallback.

    fallback_reason_codes always echoes the broad signals so
    full_suite_detected and fallback_used are never silent.
    """
    fallback_reason_codes: set[str] = set()

    for target in selected_test_targets:
        token = target.strip()
        if token in _FULL_SUITE_TARGET_TOKENS:
            fallback_reason_codes.add(f"selected_target_full_suite:{token}")

    for code in selection_reason_codes:
        for token in _FULL_SUITE_FALLBACK_REASON_TOKENS:
            if token in code:
                fallback_reason_codes.add(code)

    for target in fallback_targets:
        token = target.strip()
        if token in _FULL_SUITE_TARGET_TOKENS:
            fallback_reason_codes.add(f"fallback_target_full_suite:{token}")
        elif any(t in token for t in _FULL_SUITE_FALLBACK_REASON_TOKENS):
            fallback_reason_codes.add(f"fallback_target_signal:{token}")

    full_suite_detected = bool(fallback_reason_codes)

    # If selector reports fallback_used but no full-suite signal we keep
    # full_suite_detected False, but we still surface the fallback so it
    # is visible to consumers. Otherwise an unexplained fallback would be
    # silently dropped.
    if fallback_used and not fallback_reason_codes:
        for target in fallback_targets:
            fallback_reason_codes.add(f"fallback_target:{target}")
        if not fallback_reason_codes:
            fallback_reason_codes.add("selector_reported_fallback_used")

    return full_suite_detected, sorted(fallback_reason_codes)


def _resolve_runtime(
    summary: dict[str, Any] | None,
) -> tuple[float | None, str | None, float | None, dict[str, float], list[str]]:
    """Return runtime fields read from a ``pr_test_shards_summary``.

    Returns ``(total, slowest_shard, slowest_duration, by_name, reason_codes)``.
    Missing or unreadable summary yields all-None / empty with reason
    codes set so the consumer never silently treats absence as zero.
    """
    reason_codes: list[str] = []
    if summary is None:
        return None, None, None, {}, ["shard_summary_artifact_missing"]
    if summary.get("artifact_type") != "pr_test_shards_summary":
        reason_codes.append("shard_summary_artifact_type_unexpected")
    raw_total = summary.get("total_duration_seconds")
    raw_slowest = summary.get("slowest_shard")
    raw_slowest_duration = summary.get("max_shard_duration_seconds")
    raw_by_name = summary.get("shard_duration_by_name") or {}

    total = _coerce_float(raw_total)
    slowest_duration = _coerce_float(raw_slowest_duration)
    by_name: dict[str, float] = {}
    for name, value in raw_by_name.items():
        coerced = _coerce_float(value)
        if coerced is None:
            continue
        by_name[str(name)] = round(coerced, 3)

    if total is None and not by_name:
        reason_codes.append("shard_summary_total_duration_missing")
    if raw_slowest is None and not by_name:
        reason_codes.append("shard_summary_slowest_shard_missing")

    slowest_shard: str | None = None
    if isinstance(raw_slowest, str) and raw_slowest:
        slowest_shard = raw_slowest

    return (
        round(total, 3) if total is not None else None,
        slowest_shard,
        round(slowest_duration, 3) if slowest_duration is not None else None,
        by_name,
        reason_codes,
    )


def _resolve_selection(
    coverage: dict[str, Any] | None,
) -> tuple[list[str], list[str], bool, list[str], list[str], list[str]]:
    """Return selection fields from a ``selection_coverage_record``.

    Returns ``(changed_files, selected_test_targets, fallback_used,
    fallback_targets, selection_reason_codes, reason_codes)`` where
    ``reason_codes`` is the list of observation reasons the runtime
    artifact should add when selection inputs are missing or partial.
    """
    reason_codes: list[str] = []
    if coverage is None:
        return [], [], False, [], [], ["selection_coverage_artifact_missing"]
    if coverage.get("artifact_type") != "selection_coverage_record":
        reason_codes.append("selection_coverage_artifact_type_unexpected")

    changed_files = _coerce_str_list(coverage.get("changed_paths"))
    selected_targets = _coerce_str_list(coverage.get("selected_test_targets"))
    fallback_used = bool(coverage.get("fallback_used"))
    fallback_targets = _coerce_str_list(coverage.get("fallback_targets"))
    selection_reason_codes = _coerce_str_list(
        coverage.get("selection_reason_codes")
    )

    coverage_status = coverage.get("coverage_status")
    if coverage_status == "unknown":
        reason_codes.append("selection_coverage_status_unknown")

    return (
        sorted(set(changed_files)),
        sorted(set(selected_targets)),
        fallback_used,
        sorted(set(fallback_targets)),
        sorted(set(selection_reason_codes)),
        reason_codes,
    )


def _resolve_shard_result_refs(
    summary: dict[str, Any] | None,
) -> list[str]:
    if summary is None:
        return []
    refs = _coerce_str_list(summary.get("shard_artifact_refs"))
    return sorted(set(refs))


def _compute_evidence_hash(
    *,
    summary: dict[str, Any] | None,
    coverage: dict[str, Any] | None,
    runtime_budget_seconds: float | None,
) -> str:
    payload = {
        "shard_summary": summary,
        "selection_coverage": coverage,
        "runtime_budget_seconds": runtime_budget_seconds,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _compute_budget_status(
    *,
    total_duration_seconds: float | None,
    runtime_budget_seconds: float | None,
) -> tuple[str, list[str]]:
    if runtime_budget_seconds is None:
        return "unknown", ["runtime_budget_seconds_missing"]
    if total_duration_seconds is None:
        return "unknown", ["total_duration_seconds_missing"]
    if total_duration_seconds > runtime_budget_seconds:
        return (
            "over_budget",
            [
                "total_duration_seconds_over_runtime_budget",
            ],
        )
    return "within_budget", []


def _build_recommendations(
    *,
    full_suite_detected: bool,
    fallback_used: bool,
    budget_status: str,
    slowest_shard: str | None,
    slowest_shard_duration_seconds: float | None,
    shard_duration_by_name: dict[str, float],
    runtime_budget_seconds: float | None,
    total_duration_seconds: float | None,
) -> list[dict[str, Any]]:
    """Return observation-only improvement recommendations.

    Recommendations never reassign tests, mutate selection, or block
    PRs. They are operator-facing observations only.
    """
    recommendations: list[dict[str, Any]] = []

    if slowest_shard and slowest_shard_duration_seconds is not None:
        recommendations.append(
            {
                "code": "slowest_shard_observed",
                "details": {
                    "shard": slowest_shard,
                    "duration_seconds": round(
                        slowest_shard_duration_seconds, 3
                    ),
                },
                "observation_only": True,
                "rationale": (
                    f"{slowest_shard} is the slowest shard for this PR; "
                    "observation only — operators may consider focused "
                    "mapping or splitting this shard if it becomes a "
                    "recurring bottleneck."
                ),
            }
        )

    if full_suite_detected:
        recommendations.append(
            {
                "code": "full_suite_fallback_observed",
                "details": {
                    "fallback_used": fallback_used,
                },
                "observation_only": True,
                "rationale": (
                    "Selection observed broad / full-suite fallback. "
                    "Operators may consider extending the canonical "
                    "selector mappings (override map / needle rules) "
                    "so changed surfaces route to focused tests "
                    "instead of falling back to the full suite."
                ),
            }
        )
    elif fallback_used:
        recommendations.append(
            {
                "code": "selector_fallback_observed",
                "details": {
                    "fallback_used": True,
                },
                "observation_only": True,
                "rationale": (
                    "Selector reported fallback usage without a "
                    "full-suite signal. Operators may inspect "
                    "selection_coverage_record and the override map "
                    "to confirm the fallback is intentional."
                ),
            }
        )

    if budget_status == "over_budget":
        recommendations.append(
            {
                "code": "runtime_budget_exceeded",
                "details": {
                    "total_duration_seconds": (
                        round(total_duration_seconds, 3)
                        if total_duration_seconds is not None
                        else None
                    ),
                    "runtime_budget_seconds": runtime_budget_seconds,
                },
                "observation_only": True,
                "rationale": (
                    "Total PR pytest duration exceeded the configured "
                    "runtime budget. Observation only — operators may "
                    "consider sharding the slowest shard, narrowing "
                    "selection, or revisiting the configured budget."
                ),
            }
        )

    if budget_status == "unknown":
        recommendations.append(
            {
                "code": "runtime_budget_unknown",
                "details": {
                    "runtime_budget_seconds": runtime_budget_seconds,
                    "total_duration_seconds": total_duration_seconds,
                },
                "observation_only": True,
                "rationale": (
                    "Runtime budget status is unknown — required input "
                    "artifacts (shard summary or runtime budget) were "
                    "missing. Operators may regenerate the inputs or "
                    "supply --runtime-budget-seconds."
                ),
            }
        )

    return recommendations


def build_runtime_budget_observation(
    *,
    base_ref: str,
    head_ref: str,
    shard_summary: dict[str, Any] | None,
    selection_coverage: dict[str, Any] | None,
    runtime_budget_seconds: float | None,
    shard_summary_ref: str | None,
    created_at: str | None = None,
    record_id: str | None = None,
) -> dict[str, Any]:
    """Build an observation-only runtime budget artifact dict.

    The function never runs tests, mutates selection, or duplicates
    selector logic; it consumes already-measured shard timings and
    already-recorded selection coverage.
    """
    created_at_value = created_at or _utc_now_iso()
    record_id_value = record_id or _stable_id(
        base_ref=base_ref,
        head_ref=head_ref,
        created_at=created_at_value,
    )

    (
        total_duration_seconds,
        slowest_shard,
        slowest_shard_duration_seconds,
        shard_duration_by_name,
        runtime_reason_codes,
    ) = _resolve_runtime(shard_summary)

    (
        changed_files,
        selected_test_targets,
        fallback_used,
        fallback_targets,
        selection_reason_codes,
        selection_reason_codes_observed,
    ) = _resolve_selection(selection_coverage)

    full_suite_detected, fallback_reason_codes = _detect_full_suite(
        selected_test_targets=selected_test_targets,
        selection_reason_codes=selection_reason_codes,
        fallback_used=fallback_used,
        fallback_targets=fallback_targets,
    )

    budget_status, budget_reason_codes = _compute_budget_status(
        total_duration_seconds=total_duration_seconds,
        runtime_budget_seconds=runtime_budget_seconds,
    )

    reason_codes = sorted(
        set(
            runtime_reason_codes
            + selection_reason_codes_observed
            + budget_reason_codes
        )
    )

    shard_result_refs = _resolve_shard_result_refs(shard_summary)
    if shard_summary is not None and shard_summary_ref:
        shard_result_refs = sorted(set(shard_result_refs + [shard_summary_ref]))

    recommendations = _build_recommendations(
        full_suite_detected=full_suite_detected,
        fallback_used=fallback_used,
        budget_status=budget_status,
        slowest_shard=slowest_shard,
        slowest_shard_duration_seconds=slowest_shard_duration_seconds,
        shard_duration_by_name=shard_duration_by_name,
        runtime_budget_seconds=runtime_budget_seconds,
        total_duration_seconds=total_duration_seconds,
    )

    evidence_hash = _compute_evidence_hash(
        summary=shard_summary,
        coverage=selection_coverage,
        runtime_budget_seconds=runtime_budget_seconds,
    )

    artifact = {
        "artifact_type": "pr_test_runtime_budget_observation",
        "schema_version": "1.0.0",
        "id": record_id_value,
        "created_at": created_at_value,
        "authority_scope": "observation_only",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "changed_files": changed_files,
        "selected_test_targets": selected_test_targets,
        "shard_result_refs": shard_result_refs,
        "shard_summary_ref": shard_summary_ref if shard_summary is not None else None,
        "full_suite_detected": full_suite_detected,
        "fallback_used": fallback_used,
        "fallback_reason_codes": fallback_reason_codes,
        "total_duration_seconds": total_duration_seconds,
        "slowest_shard": slowest_shard,
        "slowest_shard_duration_seconds": slowest_shard_duration_seconds,
        "shard_duration_by_name": shard_duration_by_name,
        "runtime_budget_seconds": runtime_budget_seconds,
        "budget_status": budget_status,
        "reason_codes": reason_codes,
        "improvement_recommendations": recommendations,
        "evidence_hash": evidence_hash,
    }
    return artifact


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "EVL-RT-01 PR test runtime budget observation builder "
            "(observation-only)."
        ),
    )
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument(
        "--shard-summary",
        default=DEFAULT_SHARD_SUMMARY_REL_PATH,
        help=(
            "Path to the existing pr_test_shards_summary artifact "
            "(observation-only input)."
        ),
    )
    parser.add_argument(
        "--selection-coverage",
        default=DEFAULT_SELECTION_COVERAGE_REL_PATH,
        help=(
            "Path to the existing selection_coverage_record artifact "
            "(observation-only input)."
        ),
    )
    parser.add_argument(
        "--runtime-budget-seconds",
        type=float,
        default=DEFAULT_RUNTIME_BUDGET_SECONDS,
        help=(
            "Configured runtime budget in seconds. Observation only — "
            "this builder never blocks PRs."
        ),
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT_REL_PATH)
    return parser.parse_args()


def _resolve_path(arg: str) -> Path:
    candidate = Path(arg)
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def main() -> int:
    args = _parse_args()
    output_path = _resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    shard_summary_path = _resolve_path(args.shard_summary)
    selection_coverage_path = _resolve_path(args.selection_coverage)

    shard_summary = _load_optional_json(shard_summary_path)
    selection_coverage = _load_optional_json(selection_coverage_path)

    shard_summary_ref = (
        _ref_relative(shard_summary_path) if shard_summary is not None else None
    )

    artifact = build_runtime_budget_observation(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        shard_summary=shard_summary,
        selection_coverage=selection_coverage,
        runtime_budget_seconds=args.runtime_budget_seconds,
        shard_summary_ref=shard_summary_ref,
    )

    validate_artifact(artifact, "pr_test_runtime_budget_observation")
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "budget_status": artifact["budget_status"],
                "total_duration_seconds": artifact["total_duration_seconds"],
                "runtime_budget_seconds": artifact["runtime_budget_seconds"],
                "slowest_shard": artifact["slowest_shard"],
                "full_suite_detected": artifact["full_suite_detected"],
                "fallback_used": artifact["fallback_used"],
                "reason_codes": artifact["reason_codes"],
                "output": _ref_relative(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
