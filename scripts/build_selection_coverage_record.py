#!/usr/bin/env python3
"""AEX-SELECTION-COVERAGE-01 selection coverage record builder.

Emits an observation-only ``selection_coverage_record`` artifact at
``outputs/selection_coverage/selection_coverage_record.json`` describing
the canonical selector's matched and unmatched changed paths for a
PR. The builder reuses the canonical selector and override policy from
``spectrum_systems/modules/runtime/pr_test_selection.py`` and
``docs/governance/preflight_required_surface_test_overrides.json``.

It does not run pytest, mutate mappings, or auto-repair. Recommended
mapping candidates surfaced in the artifact are observations only.

Authority scope: observation_only. The artifact emits selection
findings, mapping observations, and recommended mapping candidates
only. Canonical ownership of the selector, override policy, and any
upstream gate authority remains with the systems declared in
``docs/architecture/system_registry.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.changed_path_resolution import (  # noqa: E402
    resolve_changed_paths,
)
from spectrum_systems.modules.runtime.pr_test_selection import (  # noqa: E402
    build_selection_coverage_record,
)

DEFAULT_OUTPUT_REL_PATH = (
    "outputs/selection_coverage/selection_coverage_record.json"
)


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_record_id(*, base_ref: str, head_ref: str, created_at: str) -> str:
    raw = f"{base_ref}|{head_ref}|{created_at}".encode("utf-8")
    return "sel-cov-" + hashlib.sha256(raw).hexdigest()[:16]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "AEX-SELECTION-COVERAGE-01 selection coverage record builder "
            "(observation-only)."
        ),
    )
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_REL_PATH)
    return parser.parse_args()


def _resolve_output_path(arg: str) -> Path:
    candidate = Path(arg)
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def _format_output_ref(output_path: Path) -> str:
    try:
        return str(output_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(output_path)


def main() -> int:
    args = _parse_args()
    output_path = _resolve_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resolution = resolve_changed_paths(
        repo_root=REPO_ROOT,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
    )
    changed_paths = list(resolution.changed_paths)
    fallback_used = bool(resolution.fallback_used)
    fallback_targets: list[str] = []
    if fallback_used:
        mode = getattr(resolution, "changed_path_detection_mode", "")
        if mode:
            fallback_targets.append(f"resolution_mode:{mode}")

    created_at = _utc_now_iso()
    record_id = _stable_record_id(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        created_at=created_at,
    )
    record = build_selection_coverage_record(
        repo_root=REPO_ROOT,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        changed_paths=changed_paths,
        record_id=record_id,
        created_at=created_at,
        fallback_used=fallback_used,
        fallback_targets=fallback_targets,
    )

    validate_artifact(record, "selection_coverage_record")
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    summary = {
        "coverage_status": record["coverage_status"],
        "changed_paths_count": len(record["changed_paths"]),
        "matched_paths_count": len(record["matched_paths"]),
        "unmatched_changed_paths_count": len(record["unmatched_changed_paths"]),
        "missing_required_surface_mapping_count": record[
            "missing_required_surface_mapping_count"
        ],
        "fallback_used": record["fallback_used"],
        "output": _format_output_ref(output_path),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
