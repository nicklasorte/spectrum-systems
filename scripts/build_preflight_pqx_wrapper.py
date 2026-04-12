#!/usr/bin/env python3
"""Build canonical preflight PQX wrapper using changed-path resolution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.changed_path_resolution import resolve_changed_paths  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build preflight PQX wrapper")
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--template", default="contracts/examples/codex_pqx_task_wrapper.json")
    parser.add_argument("--output", default="outputs/contract_preflight/preflight_pqx_task_wrapper.json")
    parser.add_argument("--changed-path", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    template_path = _REPO_ROOT / args.template
    if not template_path.exists():
        print(f"ERROR: wrapper template missing: {template_path}", file=sys.stderr)
        return 2

    resolution = resolve_changed_paths(
        repo_root=_REPO_ROOT,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        explicit=args.changed_path,
    )

    if resolution.insufficient_context:
        print(
            "ERROR: changed-path resolution insufficient; cannot build authoritative preflight wrapper.",
            file=sys.stderr,
        )
        return 2

    payload = json.loads(template_path.read_text(encoding="utf-8"))
    payload["changed_paths"] = resolution.changed_paths
    payload["changed_path_resolution"] = {
        "changed_path_detection_mode": resolution.changed_path_detection_mode,
        "resolution_mode": resolution.resolution_mode,
        "trust_level": resolution.trust_level,
        "bounded_runtime": resolution.bounded_runtime,
        "refs_attempted": resolution.refs_attempted,
        "warnings": resolution.warnings,
    }

    output_path = _REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(str(output_path.relative_to(_REPO_ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
