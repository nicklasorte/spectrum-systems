#!/usr/bin/env python3
"""Sequential PR test shard runner — emits one ``pr_test_shard_result``
artifact per canonical shard plus a compact summary.

PAR-BATCH-01. The runner reuses the canonical selector
(``spectrum_systems.modules.runtime.pr_test_selection``) and the override
policy already in place; it does NOT duplicate selection logic. Shards
run sequentially. GitHub matrix parallelization is deferred to a later
slice.

Authority scope: observation_only. The runner emits test shard result
evidence and reason codes only. It produces artifact-backed findings
that support APR / EVL consumption. It does not issue admission,
closure, or final-gate signal. Canonical ownership remains with the
systems declared in ``docs/architecture/system_registry.md``.

Status semantics
----------------
- ``pass``     — pytest exit code 0 for the shard's selected tests.
                 Requires at least one ``output_artifact_refs`` entry.
- ``fail``     — pytest exit code != 0. Carries reason codes.
- ``skipped``  — selector reported ``empty_allowed`` (no tests obligated
                 for this shard). Carries reason codes.
- ``missing``  — selector did not produce a usable selection for a
                 required shard. Carries reason codes.
- ``unknown``  — runner could not classify the result; never counts as
                 pass. Carries reason codes.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.changed_path_resolution import (  # noqa: E402
    resolve_changed_paths,
)
from spectrum_systems.modules.runtime.pr_test_selection import (  # noqa: E402
    assign_to_shard,
    is_docs_only_non_governed,
    resolve_governed_surfaces,
    resolve_required_tests,
)


# Canonical shards for PAR-BATCH-01. ``generated_artifacts`` is the new
# canonical name for what the legacy selector calls ``dashboard``. The
# legacy selector module is intentionally left untouched so the existing
# CI matrix keeps emitting its current per-shard artifacts; PAR-CI-01
# will migrate the workflow.
CANONICAL_SHARDS: tuple[str, ...] = (
    "contract",
    "governance",
    "runtime_core",
    "changed_scope",
    "generated_artifacts",
    "measurement",
)

# Canonical shards that PAR-BATCH-01 treats as required for fail-closed
# evaluation. ``runtime_core``, ``generated_artifacts``, and
# ``measurement`` are non-blocking observations until they are explicitly
# wired into CI by a later slice.
DEFAULT_REQUIRED_SHARDS: tuple[str, ...] = (
    "contract",
    "governance",
    "changed_scope",
)

# Map canonical shard name -> the shard name produced by
# ``pr_test_selection.assign_to_shard``. ``generated_artifacts`` reuses
# the legacy ``dashboard`` patterns.
_CANONICAL_TO_SELECTOR_SHARD: dict[str, str] = {
    "contract": "contract",
    "governance": "governance",
    "runtime_core": "runtime_core",
    "changed_scope": "changed_scope",
    "generated_artifacts": "dashboard",
    "measurement": "measurement",
}

# The set of selector shard names that the canonical PR matrix already
# treats as required. Anything assigned to a shard outside this set is
# absorbed by ``changed_scope`` so deferred shards never silently drop
# tests on the floor.
_REQUIRED_SELECTOR_SHARDS: frozenset[str] = frozenset(
    {"contract", "governance", "dashboard", "changed_scope"}
)


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _collect_all_tests(required_map: dict[str, list[str]]) -> list[str]:
    seen: set[str] = set()
    for tests in required_map.values():
        seen.update(tests)
    return sorted(seen)


def _select_tests_for_canonical_shard(
    all_tests: list[str], canonical_shard: str
) -> list[str]:
    """Return tests routed to ``canonical_shard`` via the canonical selector.

    For ``changed_scope`` the catch-all absorbs any test routed to a
    selector shard outside the existing required-PR set, mirroring the
    behavior of ``scripts/select_pr_test_shard.py``.
    """
    target = _CANONICAL_TO_SELECTOR_SHARD[canonical_shard]
    selected: list[str] = []
    for test_path in all_tests:
        assigned = assign_to_shard(test_path)
        if canonical_shard == "changed_scope":
            if assigned is None or assigned not in _REQUIRED_SELECTOR_SHARDS:
                selected.append(test_path)
        else:
            if assigned == target:
                selected.append(test_path)
    return selected


def _run_subprocess(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
    except (FileNotFoundError, OSError) as exc:
        return -1, f"subprocess launch failed: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _shard_artifact_path(output_dir: Path, shard_name: str) -> Path:
    return output_dir / f"{shard_name}.json"


def _build_artifact(
    *,
    shard_name: str,
    status: str,
    selected_tests: list[str],
    command: str | None,
    exit_code: int | None,
    duration_seconds: float,
    output_artifact_refs: list[str],
    reason_codes: list[str],
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "artifact_type": "pr_test_shard_result",
        "schema_version": "1.0.0",
        "shard_name": shard_name,
        "status": status,
        "selected_tests": list(selected_tests),
        "command": command,
        "exit_code": exit_code,
        "duration_seconds": float(round(duration_seconds, 3)),
        "output_artifact_refs": list(output_artifact_refs),
        "reason_codes": list(reason_codes),
        "created_at": created_at or _utc_now_iso(),
        "authority_scope": "observation_only",
    }


def _ref_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def run_shard(
    *,
    shard_name: str,
    selected_tests: list[str],
    selector_status: str,
    output_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    """Run a single shard's selected tests and write an artifact.

    ``selector_status`` is the canonical selector's shard_status for this
    shard:
      - ``selected``      → run pytest on selected_tests
      - ``empty_allowed`` → emit ``skipped`` with reason
      - ``block``         → emit ``missing`` with reason
      - anything else     → emit ``unknown`` with reason
    """
    start = time.monotonic()
    artifact_path = _shard_artifact_path(output_dir, shard_name)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    rel_artifact_ref = _ref_relative(artifact_path)

    known_statuses = {"selected", "empty_allowed", "block"}
    if selector_status not in known_statuses:
        artifact = _build_artifact(
            shard_name=shard_name,
            status="unknown",
            selected_tests=selected_tests,
            command=None,
            exit_code=None,
            duration_seconds=time.monotonic() - start,
            output_artifact_refs=[rel_artifact_ref],
            reason_codes=[f"unknown_selector_status:{selector_status or 'empty'}"],
        )
    elif selector_status == "block":
        artifact = _build_artifact(
            shard_name=shard_name,
            status="missing",
            selected_tests=selected_tests,
            command=None,
            exit_code=None,
            duration_seconds=time.monotonic() - start,
            output_artifact_refs=[rel_artifact_ref],
            reason_codes=["selector_blocked_shard"],
        )
    elif selector_status == "empty_allowed" or not selected_tests:
        artifact = _build_artifact(
            shard_name=shard_name,
            status="skipped",
            selected_tests=selected_tests,
            command=None,
            exit_code=None,
            duration_seconds=time.monotonic() - start,
            output_artifact_refs=[rel_artifact_ref],
            reason_codes=[
                "no_tests_selected_for_shard"
                if selector_status != "empty_allowed"
                else "empty_allowed_by_selector"
            ],
        )
    elif selector_status == "selected":
        cmd = [sys.executable, "-m", "pytest", "-q", *selected_tests]
        cmd_str = " ".join(shlex.quote(p) for p in cmd)
        rc, _combined = _run_subprocess(cmd, cwd=repo_root)
        duration = time.monotonic() - start
        if rc == 0:
            artifact = _build_artifact(
                shard_name=shard_name,
                status="pass",
                selected_tests=selected_tests,
                command=cmd_str,
                exit_code=rc,
                duration_seconds=duration,
                output_artifact_refs=[rel_artifact_ref],
                reason_codes=[],
            )
        else:
            artifact = _build_artifact(
                shard_name=shard_name,
                status="fail",
                selected_tests=selected_tests,
                command=cmd_str,
                exit_code=rc,
                duration_seconds=duration,
                output_artifact_refs=[rel_artifact_ref],
                reason_codes=[f"pytest_returncode_{rc}"],
            )
    else:
        # Defensive: every known status branch above either emits an
        # artifact or moves on. If we land here, treat it as unknown.
        artifact = _build_artifact(
            shard_name=shard_name,
            status="unknown",
            selected_tests=selected_tests,
            command=None,
            exit_code=None,
            duration_seconds=time.monotonic() - start,
            output_artifact_refs=[rel_artifact_ref],
            reason_codes=[f"runner_dropped_through:{selector_status or 'empty'}"],
        )

    validate_artifact(artifact, "pr_test_shard_result")
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def _selector_status_for_shard(
    *,
    canonical_shard: str,
    governed_surfaces: list[dict[str, Any]],
    selected_tests: list[str],
    changed_paths: list[str],
    all_tests: list[str],
) -> str:
    """Mirror ``scripts/select_pr_test_shard.py`` status logic for a shard."""
    if governed_surfaces and not all_tests:
        return "block"
    if governed_surfaces and not selected_tests:
        return "empty_allowed"
    if not changed_paths:
        return "empty_allowed"
    if not selected_tests:
        if is_docs_only_non_governed(changed_paths):
            return "empty_allowed"
        return "empty_allowed"
    return "selected"


def run_all_shards(
    *,
    base_ref: str,
    head_ref: str,
    output_dir: Path,
    repo_root: Path,
    shards: tuple[str, ...] = CANONICAL_SHARDS,
    required_shards: tuple[str, ...] = DEFAULT_REQUIRED_SHARDS,
) -> dict[str, Any]:
    """Run all canonical shards sequentially and return a summary dict."""
    output_dir.mkdir(parents=True, exist_ok=True)

    resolution = resolve_changed_paths(
        repo_root=repo_root,
        base_ref=base_ref,
        head_ref=head_ref,
    )
    changed_paths = list(resolution.changed_paths)
    governed = resolve_governed_surfaces(changed_paths)
    required_map = resolve_required_tests(repo_root, changed_paths)
    all_tests = _collect_all_tests(required_map)

    artifacts_by_shard: dict[str, dict[str, Any]] = {}
    for shard in shards:
        selected = _select_tests_for_canonical_shard(all_tests, shard)
        sel_status = _selector_status_for_shard(
            canonical_shard=shard,
            governed_surfaces=governed,
            selected_tests=selected,
            changed_paths=changed_paths,
            all_tests=all_tests,
        )
        artifacts_by_shard[shard] = run_shard(
            shard_name=shard,
            selected_tests=selected,
            selector_status=sel_status,
            output_dir=output_dir,
            repo_root=repo_root,
        )

    return _build_summary(
        base_ref=base_ref,
        head_ref=head_ref,
        artifacts_by_shard=artifacts_by_shard,
        required_shards=required_shards,
        output_dir=output_dir,
    )


# Shards whose status indicates pytest actually ran. Skipped / missing /
# unknown shards are excluded from balance metrics so a no-op shard does
# not corrupt the imbalance ratio or median.
_ACTIVE_STATUSES: frozenset[str] = frozenset({"pass", "fail"})

# Threshold multipliers for balancing findings. Conservative defaults —
# emit findings only, never auto-rebalance.
_OVER_MEDIAN_DURATION_MULTIPLIER: float = 2.0
_TESTS_COUNT_SKEW_MULTIPLIER: float = 5.0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def compute_shard_timing_summary(
    artifacts_by_shard: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return shard timing observations for the summary artifact.

    Excludes shards whose status is not in :data:`_ACTIVE_STATUSES` from
    the imbalance ratio so a skipped or missing shard does not corrupt
    min/max. Returns ``imbalance_ratio = None`` whenever the eligible
    set has no positive-duration entry.
    """
    durations_by_name: dict[str, float] = {}
    for shard, artifact in artifacts_by_shard.items():
        try:
            durations_by_name[shard] = float(artifact.get("duration_seconds") or 0.0)
        except (TypeError, ValueError):
            durations_by_name[shard] = 0.0

    eligible = {
        shard: durations_by_name[shard]
        for shard, artifact in artifacts_by_shard.items()
        if artifact.get("status") in _ACTIVE_STATUSES
        and durations_by_name.get(shard, 0.0) > 0.0
    }

    total = round(sum(durations_by_name.values()), 3)
    if eligible:
        max_shard, max_dur = max(eligible.items(), key=lambda kv: kv[1])
        min_dur = min(eligible.values())
        slowest_shard: str | None = max_shard
        max_duration: float | None = round(max_dur, 3)
        min_duration: float | None = round(min_dur, 3)
        ratio: float | None = (
            round(max_dur / min_dur, 3) if min_dur > 0.0 else None
        )
    else:
        slowest_shard = None
        max_duration = None
        min_duration = None
        ratio = None

    return {
        "total_duration_seconds": total,
        "max_shard_duration_seconds": max_duration,
        "min_shard_duration_seconds": min_duration,
        "shard_duration_by_name": {
            shard: round(durations_by_name[shard], 3)
            for shard in sorted(durations_by_name)
        },
        "slowest_shard": slowest_shard,
        "imbalance_ratio": ratio,
    }


def compute_balancing_findings(
    artifacts_by_shard: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return artifact-backed balancing findings for the shard summary.

    Findings are observation-only. They never move tests between shards
    and never change shard_status. Each finding carries a stable ``code``
    plus ``shard`` and a ``details`` dict so consumers can read the
    underlying timing observation without reparsing the summary.
    """
    findings: list[dict[str, Any]] = []
    active_durations: dict[str, float] = {}
    selected_counts: dict[str, int] = {}
    for shard, artifact in artifacts_by_shard.items():
        if artifact.get("status") not in _ACTIVE_STATUSES:
            continue
        try:
            duration = float(artifact.get("duration_seconds") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        active_durations[shard] = duration
        selected = artifact.get("selected_tests") or []
        selected_counts[shard] = len(selected)

    if not active_durations:
        return findings

    slowest_shard, slowest_duration = max(
        active_durations.items(), key=lambda kv: kv[1]
    )
    findings.append(
        {
            "code": "slowest_shard_observed",
            "shard": slowest_shard,
            "details": {
                "duration_seconds": round(slowest_duration, 3),
            },
        }
    )

    median_duration = _median(list(active_durations.values()))
    if median_duration > 0.0:
        cutoff = _OVER_MEDIAN_DURATION_MULTIPLIER * median_duration
        for shard in sorted(active_durations):
            if active_durations[shard] > cutoff:
                findings.append(
                    {
                        "code": "shard_duration_over_2x_median",
                        "shard": shard,
                        "details": {
                            "duration_seconds": round(active_durations[shard], 3),
                            "median_seconds": round(median_duration, 3),
                            "multiplier_threshold": _OVER_MEDIAN_DURATION_MULTIPLIER,
                        },
                    }
                )

    for shard in sorted(selected_counts):
        if selected_counts[shard] == 0:
            findings.append(
                {
                    "code": "empty_or_near_empty_shard",
                    "shard": shard,
                    "details": {
                        "selected_tests_count": 0,
                    },
                }
            )

    nonzero_counts = [c for c in selected_counts.values() if c > 0]
    if len(nonzero_counts) >= 2:
        max_count = max(nonzero_counts)
        min_count = min(nonzero_counts)
        if min_count > 0 and max_count >= _TESTS_COUNT_SKEW_MULTIPLIER * min_count:
            for shard in sorted(selected_counts):
                if selected_counts[shard] == max_count:
                    findings.append(
                        {
                            "code": "selected_tests_count_skew",
                            "shard": shard,
                            "details": {
                                "max_selected_tests": max_count,
                                "min_selected_tests": min_count,
                                "skew_threshold": _TESTS_COUNT_SKEW_MULTIPLIER,
                            },
                        }
                    )

    return findings


def _build_summary(
    *,
    base_ref: str,
    head_ref: str,
    artifacts_by_shard: dict[str, dict[str, Any]],
    required_shards: tuple[str, ...],
    output_dir: Path,
) -> dict[str, Any]:
    shard_status_map = {
        shard: artifact.get("status", "unknown")
        for shard, artifact in artifacts_by_shard.items()
    }
    shard_artifact_refs = sorted(
        ref
        for artifact in artifacts_by_shard.values()
        for ref in artifact.get("output_artifact_refs", [])
    )

    blocking_reasons: list[str] = []
    for shard in required_shards:
        status = shard_status_map.get(shard)
        if status is None:
            blocking_reasons.append(f"{shard}:required_shard_missing_artifact")
            continue
        if status == "fail":
            blocking_reasons.append(f"{shard}:required_shard_failed")
        elif status in ("missing", "unknown"):
            blocking_reasons.append(f"{shard}:required_shard_{status}")

    overall_status = "block" if blocking_reasons else "pass"

    timing = compute_shard_timing_summary(artifacts_by_shard)
    balancing_findings = compute_balancing_findings(artifacts_by_shard)

    summary = {
        "artifact_type": "pr_test_shards_summary",
        "schema_version": "1.0.0",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "shard_status": shard_status_map,
        "required_shards": list(required_shards),
        "shard_artifact_refs": shard_artifact_refs,
        "overall_status": overall_status,
        "blocking_reasons": blocking_reasons,
        "total_duration_seconds": timing["total_duration_seconds"],
        "max_shard_duration_seconds": timing["max_shard_duration_seconds"],
        "min_shard_duration_seconds": timing["min_shard_duration_seconds"],
        "shard_duration_by_name": timing["shard_duration_by_name"],
        "slowest_shard": timing["slowest_shard"],
        "imbalance_ratio": timing["imbalance_ratio"],
        "balancing_findings": balancing_findings,
        "created_at": _utc_now_iso(),
        "authority_scope": "observation_only",
    }
    summary_path = output_dir / "pr_test_shards_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequential PR test shard runner (PAR-BATCH-01).",
    )
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument(
        "--output-dir",
        default="outputs/pr_test_shards",
        help="Directory to write per-shard artifacts and summary.",
    )
    parser.add_argument(
        "--shards",
        default=",".join(CANONICAL_SHARDS),
        help="Comma-separated canonical shard names to run.",
    )
    parser.add_argument(
        "--required-shards",
        default=",".join(DEFAULT_REQUIRED_SHARDS),
        help="Shards that fail closed when missing/failed/unknown.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    shards = tuple(s.strip() for s in args.shards.split(",") if s.strip())
    required = tuple(s.strip() for s in args.required_shards.split(",") if s.strip())
    for shard in shards:
        if shard not in CANONICAL_SHARDS:
            print(
                f"[run_pr_test_shards] ERROR: unknown shard {shard!r}",
                file=sys.stderr,
            )
            return 2
    summary = run_all_shards(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        output_dir=output_dir,
        repo_root=REPO_ROOT,
        shards=shards,
        required_shards=required,
    )
    print(
        json.dumps(
            {
                "overall_status": summary["overall_status"],
                "shard_status": summary["shard_status"],
                "blocking_reasons": summary["blocking_reasons"],
                "summary_path": _ref_relative(
                    output_dir / "pr_test_shards_summary.json"
                ),
            },
            indent=2,
        )
    )
    return 0 if summary["overall_status"] == "pass" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[run_pr_test_shards] FATAL: {exc}", file=sys.stderr)
        sys.exit(1)
