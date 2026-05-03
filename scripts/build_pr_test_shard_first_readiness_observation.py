#!/usr/bin/env python3
"""EVL-RT-03 PR test shard-first readiness observation builder.

Emits an observation-only ``pr_test_shard_first_readiness_observation``
artifact at
``outputs/pr_test_shard_first_readiness/pr_test_shard_first_readiness_observation.json``
that records, for a PR's already-measured shard run, whether the PR path
is shard-first (focused selection backed by shard evidence refs) or
fallback-justified (broad/full-suite usage explained by the existing
``fallback_justification`` section in ``pr_test_runtime_budget_observation``).

The builder reuses the canonical artifacts emitted upstream:

- ``pr_test_shards_summary`` (per-shard refs, required shards, status),
- ``selection_coverage_record`` (changed paths, selected targets),
- ``pr_test_runtime_budget_observation`` (full-suite/fallback detection
  and ``fallback_justification`` section with fallback_reason_codes).

The builder does NOT:

- run pytest,
- mutate test selection,
- duplicate the canonical PR test selector,
- block PRs,
- weaken or reduce required tests.

Authority scope: ``observation_only``. The artifact emits shard-first,
runtime, and fallback observations only. Canonical ownership of the
selector, shard runner, override policy, and any upstream gate
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
DEFAULT_RUNTIME_BUDGET_REL_PATH = (
    "outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json"
)
DEFAULT_OUTPUT_REL_PATH = (
    "outputs/pr_test_shard_first_readiness/"
    "pr_test_shard_first_readiness_observation.json"
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
    return "pr-shard-first-" + hashlib.sha256(raw).hexdigest()[:16]


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


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _resolve_required_shard_refs(
    shard_summary: dict[str, Any] | None,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (required_shard_refs, missing_shard_refs, failed_shard_refs,
    reason_codes) read from a ``pr_test_shards_summary`` artifact.

    The builder consumes already-emitted shard refs and shard_status; it
    never recomputes selection or re-runs shards.
    """
    reason_codes: list[str] = []
    if shard_summary is None:
        return [], [], [], ["shard_summary_artifact_missing"]
    if shard_summary.get("artifact_type") != "pr_test_shards_summary":
        reason_codes.append("shard_summary_artifact_type_unexpected")

    required_shards = _coerce_str_list(shard_summary.get("required_shards"))
    shard_status = shard_summary.get("shard_status") or {}
    if not isinstance(shard_status, dict):
        shard_status = {}
    shard_artifact_refs = _coerce_str_list(
        shard_summary.get("shard_artifact_refs")
    )

    # Map shard name -> matching artifact ref (last path component
    # equals "<shard>.json"). The summary already lists artifact refs;
    # we never reconstruct paths from selection logic.
    by_shard: dict[str, list[str]] = {}
    for ref in shard_artifact_refs:
        ref_path = Path(ref)
        stem = ref_path.stem
        by_shard.setdefault(stem, []).append(ref)

    required_shard_refs: list[str] = []
    missing_shard_refs: list[str] = []
    failed_shard_refs: list[str] = []
    for shard in required_shards:
        refs = by_shard.get(shard, [])
        status = shard_status.get(shard)
        if status == "pass":
            if refs:
                required_shard_refs.extend(refs)
            else:
                missing_shard_refs.append(shard)
                reason_codes.append(
                    f"required_shard_{shard}_pass_missing_artifact_ref"
                )
        elif status == "fail":
            for ref in refs:
                failed_shard_refs.append(ref)
            reason_codes.append(f"required_shard_{shard}_failed")
        elif status in ("missing", "unknown", None):
            missing_shard_refs.append(shard)
            reason_codes.append(
                f"required_shard_{shard}_{status or 'absent'}"
            )
        elif status == "skipped":
            # Skipped shards are observation-only; record but do not
            # treat as a missing readiness signal here.
            reason_codes.append(f"required_shard_{shard}_skipped")
            for ref in refs:
                required_shard_refs.append(ref)

    return (
        sorted(set(required_shard_refs)),
        sorted(set(missing_shard_refs)),
        sorted(set(failed_shard_refs)),
        reason_codes,
    )


def _resolve_changed_files(
    selection_coverage: dict[str, Any] | None,
) -> list[str]:
    if selection_coverage is None:
        return []
    return sorted(set(_coerce_str_list(selection_coverage.get("changed_paths"))))


def _resolve_runtime_signals(
    runtime_budget: dict[str, Any] | None,
) -> tuple[bool, bool, list[str], dict[str, Any] | None, list[str]]:
    """Read fallback / full-suite signals from the runtime budget artifact.

    Returns ``(fallback_used, full_suite_detected, fallback_reason_codes,
    fallback_justification, reason_codes)``. The runtime budget artifact
    already records these signals (EVL-RT-01 / EVL-RT-02); we only
    consume them.
    """
    reason_codes: list[str] = []
    if runtime_budget is None:
        return False, False, [], None, [
            "runtime_budget_observation_artifact_missing"
        ]
    if (
        runtime_budget.get("artifact_type")
        != "pr_test_runtime_budget_observation"
    ):
        reason_codes.append("runtime_budget_observation_artifact_type_unexpected")

    fallback_used = bool(runtime_budget.get("fallback_used"))
    full_suite_detected = bool(runtime_budget.get("full_suite_detected"))
    fallback_reason_codes = sorted(
        set(_coerce_str_list(runtime_budget.get("fallback_reason_codes")))
    )

    justification = runtime_budget.get("fallback_justification")
    if not isinstance(justification, dict):
        justification = None

    if justification is not None:
        # Prefer the justification section's reason codes when present
        # — they include scope-specific codes (e.g. unknown scope).
        just_codes = sorted(
            set(_coerce_str_list(justification.get("fallback_reason_codes")))
        )
        if just_codes:
            fallback_reason_codes = sorted(
                set(fallback_reason_codes) | set(just_codes)
            )

    return (
        fallback_used,
        full_suite_detected,
        fallback_reason_codes,
        justification,
        reason_codes,
    )


def _classify_shard_first_status(
    *,
    fallback_used: bool,
    full_suite_detected: bool,
    fallback_reason_codes: list[str],
    fallback_justification: dict[str, Any] | None,
    fallback_justification_ref: str | None,
    required_shard_refs: list[str],
    missing_shard_refs: list[str],
    failed_shard_refs: list[str],
    runtime_budget_present: bool,
    shard_summary_present: bool,
) -> tuple[str, list[str]]:
    """Return ``(shard_first_status, extra_reason_codes)``.

    Status values:

    - ``shard_first``: focused selection with required shard refs, no
      fallback observed.
    - ``fallback_justified``: broad/full-suite/shard fallback observed
      AND the runtime budget observation supplies a fallback
      justification section with at least one fallback_reason_code.
    - ``missing``: required inputs are absent.
    - ``partial``: some required shard refs are missing/failed but
      fallback was not declared, or fallback was declared without
      justification refs.
    - ``unknown``: cannot classify (e.g. runtime budget artifact missing
      while fallback signals are absent).
    """
    extra: list[str] = []

    if not shard_summary_present and not runtime_budget_present:
        return "missing", [
            "shard_summary_and_runtime_budget_observations_missing"
        ]

    if not shard_summary_present:
        extra.append("shard_summary_missing")
        if fallback_used or full_suite_detected:
            if fallback_justification_ref and fallback_reason_codes:
                return "fallback_justified", extra
            extra.append("fallback_used_but_justification_incomplete")
            return "partial", extra
        return "missing", extra

    if not runtime_budget_present:
        # Without runtime budget observation we cannot prove fallback
        # status; record unknown rather than treat as shard_first.
        return "unknown", [
            "runtime_budget_observation_missing_cannot_prove_shard_first"
        ]

    if fallback_used or full_suite_detected:
        # Require both an artifact ref AND reason codes for the
        # fallback_justified status. Either missing => partial.
        has_justification_section = (
            fallback_justification is not None
            and bool(fallback_reason_codes)
        )
        if fallback_justification_ref and has_justification_section:
            return "fallback_justified", extra
        if not fallback_justification_ref:
            extra.append("fallback_justification_ref_missing")
        if not fallback_reason_codes:
            extra.append("fallback_reason_codes_missing")
        if fallback_justification is None:
            extra.append("fallback_justification_section_missing")
        return "partial", extra

    if missing_shard_refs:
        extra.append("required_shard_refs_missing")
        return "partial", extra
    if failed_shard_refs:
        extra.append("required_shard_refs_failed")
        return "partial", extra

    if not required_shard_refs:
        extra.append("required_shard_refs_empty")
        return "partial", extra

    return "shard_first", extra


def _resolve_recommended_mapping_candidates(
    fallback_justification: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Re-emit observation-only mapping candidates from the existing
    runtime budget fallback_justification section.

    The shard-first builder does NOT compute new mapping candidates; it
    only surfaces already-recorded recommendations from the canonical
    fallback_justification section. Each candidate is forced to
    ``observation_only=true`` and stripped of any non-schema fields so
    no recommendation can claim authority.
    """
    if not isinstance(fallback_justification, dict):
        return []
    raw = fallback_justification.get("recommended_mapping_candidates")
    if not isinstance(raw, list):
        return []
    candidates: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        targets = entry.get("candidate_test_targets")
        if not isinstance(path, str) or not path:
            continue
        if not isinstance(targets, list):
            continue
        clean_targets = [
            str(t) for t in targets if isinstance(t, str) and t
        ]
        candidate: dict[str, Any] = {
            "path": path,
            "candidate_test_targets": clean_targets,
            "observation_only": True,
        }
        rationale = entry.get("rationale")
        if isinstance(rationale, str) and rationale:
            candidate["rationale"] = rationale
        candidates.append(candidate)
    return candidates


def _resolve_recommended_shard_candidates(
    fallback_justification: dict[str, Any] | None,
    *,
    missing_shard_refs: list[str],
    failed_shard_refs: list[str],
) -> list[dict[str, Any]]:
    """Re-emit observation-only shard candidates from the existing
    runtime budget fallback_justification section, plus a finding for
    any required shard whose ref is missing or failed.

    Recommendations never reassign tests, mutate selection, or change
    sharding. They are operator-facing observations only.
    """
    candidates: list[dict[str, Any]] = []
    if isinstance(fallback_justification, dict):
        raw = fallback_justification.get("recommended_shard_candidates")
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                shard = entry.get("shard")
                if not isinstance(shard, str) or not shard:
                    continue
                candidate: dict[str, Any] = {
                    "shard": shard,
                    "observation_only": True,
                }
                action = entry.get("candidate_action")
                if isinstance(action, str) and action in {
                    "split_shard",
                    "narrow_selection",
                    "review_mapping",
                    "review_runtime_budget",
                }:
                    candidate["candidate_action"] = action
                rationale = entry.get("rationale")
                if isinstance(rationale, str) and rationale:
                    candidate["rationale"] = rationale
                candidates.append(candidate)
    seen = {(c["shard"], c.get("candidate_action")) for c in candidates}
    for shard in missing_shard_refs:
        key = (shard, "review_mapping")
        if key in seen:
            continue
        candidates.append(
            {
                "shard": shard,
                "candidate_action": "review_mapping",
                "observation_only": True,
                "rationale": (
                    f"Required shard {shard} is missing an artifact ref; "
                    "observation only — operators may inspect the shard "
                    "runner output and the override map to confirm the "
                    "shard ran and produced an artifact."
                ),
            }
        )
        seen.add(key)
    for ref in failed_shard_refs:
        shard_name = Path(ref).stem
        key = (shard_name, "review_runtime_budget")
        if key in seen:
            continue
        candidates.append(
            {
                "shard": shard_name,
                "candidate_action": "review_runtime_budget",
                "observation_only": True,
                "rationale": (
                    f"Required shard {shard_name} reported a failed "
                    "result; observation only — operators may inspect "
                    "the shard artifact and the upstream selector "
                    "output."
                ),
            }
        )
        seen.add(key)
    return candidates


def _compute_evidence_hash(
    *,
    shard_summary: dict[str, Any] | None,
    selection_coverage: dict[str, Any] | None,
    runtime_budget: dict[str, Any] | None,
    shard_first_status: str,
) -> str:
    payload = {
        "shard_summary": shard_summary,
        "selection_coverage": selection_coverage,
        "runtime_budget_observation": runtime_budget,
        "shard_first_status": shard_first_status,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def build_shard_first_readiness_observation(
    *,
    base_ref: str,
    head_ref: str,
    shard_summary: dict[str, Any] | None,
    selection_coverage: dict[str, Any] | None,
    runtime_budget: dict[str, Any] | None,
    shard_summary_ref: str | None,
    selection_coverage_ref: str | None,
    runtime_budget_observation_ref: str | None,
    created_at: str | None = None,
    record_id: str | None = None,
) -> dict[str, Any]:
    """Build an observation-only shard-first readiness artifact dict.

    The function never runs tests, mutates selection, or duplicates
    selector logic; it consumes already-emitted shard refs, selection
    coverage, and runtime budget observations.
    """
    created_at_value = created_at or _utc_now_iso()
    record_id_value = record_id or _stable_id(
        base_ref=base_ref,
        head_ref=head_ref,
        created_at=created_at_value,
    )

    (
        required_shard_refs,
        missing_shard_refs,
        failed_shard_refs,
        shard_reason_codes,
    ) = _resolve_required_shard_refs(shard_summary)

    changed_files = _resolve_changed_files(selection_coverage)

    (
        fallback_used,
        full_suite_detected,
        fallback_reason_codes,
        fallback_justification,
        runtime_reason_codes,
    ) = _resolve_runtime_signals(runtime_budget)

    effective_shard_summary_ref = (
        shard_summary_ref if shard_summary is not None else None
    )
    effective_selection_coverage_ref = (
        selection_coverage_ref if selection_coverage is not None else None
    )
    effective_runtime_budget_ref = (
        runtime_budget_observation_ref if runtime_budget is not None else None
    )
    # The fallback_justification section lives inside the runtime budget
    # observation artifact, so the justification ref is the runtime
    # budget observation path whenever the runtime budget artifact is
    # present. If the section itself is malformed or absent the
    # readiness reason_codes record that — but the ref always points to
    # where the section is expected to live.
    fallback_justification_ref: str | None = effective_runtime_budget_ref

    # Classify before synthesizing fail-closed reason codes so the
    # classifier sees the upstream truth: an empty fallback_reason_codes
    # list means upstream did not provide one.
    shard_first_status, classify_reason_codes = _classify_shard_first_status(
        fallback_used=fallback_used,
        full_suite_detected=full_suite_detected,
        fallback_reason_codes=fallback_reason_codes,
        fallback_justification=fallback_justification,
        fallback_justification_ref=fallback_justification_ref,
        required_shard_refs=required_shard_refs,
        missing_shard_refs=missing_shard_refs,
        failed_shard_refs=failed_shard_refs,
        runtime_budget_present=runtime_budget is not None,
        shard_summary_present=shard_summary is not None,
    )

    # Fail-closed: when upstream signals fallback_used or
    # full_suite_detected without populating fallback_reason_codes the
    # readiness artifact synthesizes a reason code so the upstream
    # malformedness is visible and the schema's minItems rule is
    # satisfied. The synthesized code names the upstream gap; it never
    # masks the missingness — synthesis happens after classification so
    # the fallback_justified status is never reached when upstream
    # reason codes are absent.
    extra_synthesized_reason_codes: list[str] = []
    if fallback_used and not fallback_reason_codes:
        fallback_reason_codes = [
            "fallback_used_observed_without_upstream_reason_codes"
        ]
        extra_synthesized_reason_codes.append(
            "fallback_used_observed_without_upstream_reason_codes"
        )
    if full_suite_detected and not fallback_reason_codes:
        fallback_reason_codes = sorted(
            set(fallback_reason_codes)
            | {"full_suite_detected_observed_without_upstream_reason_codes"}
        )
        extra_synthesized_reason_codes.append(
            "full_suite_detected_observed_without_upstream_reason_codes"
        )

    reason_codes = sorted(
        set(
            shard_reason_codes
            + runtime_reason_codes
            + classify_reason_codes
            + extra_synthesized_reason_codes
        )
    )

    recommended_mapping_candidates = _resolve_recommended_mapping_candidates(
        fallback_justification
    )
    recommended_shard_candidates = _resolve_recommended_shard_candidates(
        fallback_justification,
        missing_shard_refs=missing_shard_refs,
        failed_shard_refs=failed_shard_refs,
    )

    evidence_hash = _compute_evidence_hash(
        shard_summary=shard_summary,
        selection_coverage=selection_coverage,
        runtime_budget=runtime_budget,
        shard_first_status=shard_first_status,
    )

    artifact: dict[str, Any] = {
        "artifact_type": "pr_test_shard_first_readiness_observation",
        "schema_version": "1.0.0",
        "id": record_id_value,
        "created_at": created_at_value,
        "authority_scope": "observation_only",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "changed_files": changed_files,
        "selection_coverage_ref": effective_selection_coverage_ref,
        "shard_summary_ref": effective_shard_summary_ref,
        "runtime_budget_observation_ref": effective_runtime_budget_ref,
        "fallback_justification_ref": fallback_justification_ref,
        "shard_first_status": shard_first_status,
        "required_shard_refs": required_shard_refs,
        "missing_shard_refs": missing_shard_refs,
        "failed_shard_refs": failed_shard_refs,
        "fallback_used": fallback_used,
        "full_suite_detected": full_suite_detected,
        "fallback_reason_codes": fallback_reason_codes,
        "reason_codes": reason_codes,
        "recommended_mapping_candidates": recommended_mapping_candidates,
        "recommended_shard_candidates": recommended_shard_candidates,
        "evidence_hash": evidence_hash,
    }
    return artifact


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "EVL-RT-03 PR test shard-first readiness observation builder "
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
        "--runtime-budget",
        default=DEFAULT_RUNTIME_BUDGET_REL_PATH,
        help=(
            "Path to the existing pr_test_runtime_budget_observation "
            "artifact (observation-only input). The fallback_justification "
            "section in that artifact is consumed here; this builder does "
            "not recompute fallback signals."
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
    runtime_budget_path = _resolve_path(args.runtime_budget)

    shard_summary = _load_optional_json(shard_summary_path)
    selection_coverage = _load_optional_json(selection_coverage_path)
    runtime_budget = _load_optional_json(runtime_budget_path)

    shard_summary_ref = (
        _ref_relative(shard_summary_path) if shard_summary is not None else None
    )
    selection_coverage_ref = (
        _ref_relative(selection_coverage_path)
        if selection_coverage is not None
        else None
    )
    runtime_budget_observation_ref = (
        _ref_relative(runtime_budget_path)
        if runtime_budget is not None
        else None
    )

    artifact = build_shard_first_readiness_observation(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        shard_summary=shard_summary,
        selection_coverage=selection_coverage,
        runtime_budget=runtime_budget,
        shard_summary_ref=shard_summary_ref,
        selection_coverage_ref=selection_coverage_ref,
        runtime_budget_observation_ref=runtime_budget_observation_ref,
    )

    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "shard_first_status": artifact["shard_first_status"],
                "fallback_used": artifact["fallback_used"],
                "full_suite_detected": artifact["full_suite_detected"],
                "required_shard_refs_count": len(artifact["required_shard_refs"]),
                "missing_shard_refs": artifact["missing_shard_refs"],
                "failed_shard_refs": artifact["failed_shard_refs"],
                "reason_codes": artifact["reason_codes"],
                "output": _ref_relative(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
