#!/usr/bin/env python3
"""CLI: select test files for a single PR test shard.

Produces a pr_test_shard_selection artifact for the given shard name.
Fail-closed: any exception → exit 1.
Authority scope: observation_only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.pr_test_selection import (  # noqa: E402
    assign_to_shard,
    build_selection_artifact,
    is_docs_only_non_governed,
    resolve_governed_surfaces,
    resolve_required_tests,
    SHARD_NAMES,
)
from spectrum_systems.modules.runtime.changed_path_resolution import resolve_changed_paths  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select test files for a single PR test shard.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["ci", "precheck"],
        help="Execution mode: ci or precheck.",
    )
    parser.add_argument(
        "--shard",
        required=True,
        choices=list(SHARD_NAMES),
        help="Shard name to select tests for.",
    )
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Base git ref (e.g. origin/main).",
    )
    parser.add_argument(
        "--head-ref",
        required=True,
        help="Head git ref (e.g. HEAD or a commit SHA).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path for the selection artifact JSON.",
    )
    return parser.parse_args()


def _collect_all_tests(required_map: dict[str, list[str]]) -> list[str]:
    """Flatten all tests from the required_map into a deduplicated sorted list."""
    all_tests: set[str] = set()
    for tests in required_map.values():
        all_tests.update(tests)
    return sorted(all_tests)


# Shards that run in the required PR matrix. Tests assigned to any shard NOT
# in this set are absorbed by the changed_scope catch-all so they are never
# silently dropped when only the four required shards execute.
_REQUIRED_PR_SHARDS: frozenset[str] = frozenset(
    {"contract", "governance", "dashboard", "changed_scope"}
)


def _select_tests_for_shard(all_tests: list[str], shard_name: str) -> list[str]:
    """Filter tests that belong to *shard_name*.

    For 'changed_scope', include tests that are either unassigned OR assigned
    to a shard that is not in the required PR matrix (_REQUIRED_PR_SHARDS).
    This ensures tests from deferred shards (runtime_core, measurement) are
    never silently skipped — they fall through to changed_scope.

    For all other shards, include tests where assign_to_shard() returns that
    shard name exactly.
    """
    selected: list[str] = []
    for test_path in all_tests:
        assigned = assign_to_shard(test_path)
        if shard_name == "changed_scope":
            # Absorb unassigned tests AND tests from deferred (non-required) shards.
            if assigned is None or assigned not in _REQUIRED_PR_SHARDS:
                selected.append(test_path)
        else:
            if assigned == shard_name:
                selected.append(test_path)
    return selected


def _determine_status(
    governed_surfaces: list[dict],
    selected_tests: list[str],
    changed_paths: list[str],
) -> tuple[str, list[str]]:
    """Compute (status, reason_codes) before handing off to build_selection_artifact."""
    reason_codes: list[str] = []

    if governed_surfaces and not selected_tests:
        return "block", ["governed_surface_empty_selection"]

    if not changed_paths:
        return "empty_allowed", reason_codes

    if not selected_tests:
        if is_docs_only_non_governed(changed_paths):
            return "empty_allowed", reason_codes
        # Non-empty non-governed paths with no tests selected is still surfaced
        # to build_selection_artifact which will apply its own fail-closed rules.

    return "selected", reason_codes


def main() -> int:
    args = _parse_args()

    # 1. Resolve changed paths.
    resolution = resolve_changed_paths(
        repo_root=REPO_ROOT,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
    )
    changed_paths: list[str] = resolution.changed_paths

    # 2. Resolve governed surfaces.
    governed_surfaces = resolve_governed_surfaces(changed_paths)

    # 3. Resolve required tests.
    required_map = resolve_required_tests(REPO_ROOT, changed_paths)

    # 4. Collect all tests from the required map.
    all_tests = _collect_all_tests(required_map)

    # 5. Filter to this shard.
    selected_tests = _select_tests_for_shard(all_tests, args.shard)

    # 6. Compute coverage_ratio.
    all_governed_paths = [e["path"] for e in governed_surfaces]
    coverage_ratio = len(selected_tests) / max(1, len(all_governed_paths))

    # 7. Determine status and reason codes.
    status, reason_codes = _determine_status(governed_surfaces, selected_tests, changed_paths)

    # 8. Build and write the selection artifact.
    trace_refs: list[str] = [
        f"changed_path_detection_mode={resolution.changed_path_detection_mode}",
        f"trust_level={resolution.trust_level}",
        f"fallback_used={resolution.fallback_used}",
    ]
    if resolution.warnings:
        trace_refs.extend(f"warning={w}" for w in resolution.warnings)

    artifact = build_selection_artifact(
        shard_name=args.shard,
        mode=args.mode,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        changed_paths=changed_paths,
        governed_surfaces=governed_surfaces,
        selected_test_files=selected_tests,
        fallback_used=resolution.fallback_used,
        status=status,
        reason_codes=reason_codes,
        trace_refs=trace_refs,
    )
    # Append coverage_ratio and produced_at to the artifact.
    artifact["coverage_ratio"] = coverage_ratio
    artifact["produced_at"] = datetime.now(timezone.utc).isoformat()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        # Default output directory convention.
        output_path = REPO_ROOT / "outputs" / "pr_test_shards" / args.shard / output_path.name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    effective_status = artifact.get("status", status)
    if effective_status == "block":
        print(
            f"[select_pr_test_shard] BLOCK shard={args.shard} "
            f"reason_codes={artifact.get('reason_codes', [])}",
            file=sys.stderr,
        )
        return 1

    print(
        f"[select_pr_test_shard] status={effective_status} shard={args.shard} "
        f"selected={len(selected_tests)} tests → {output_path}",
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[select_pr_test_shard] FATAL: {exc}", file=sys.stderr)
        sys.exit(1)
