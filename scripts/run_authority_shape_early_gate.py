#!/usr/bin/env python3
"""Run authority-shape early gate against changed files."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_EARLY_GATE_PATH = REPO_ROOT / "spectrum_systems" / "governance" / "authority_shape_early_gate.py"
_CHANGED_FILES_PATH = REPO_ROOT / "spectrum_systems" / "modules" / "governance" / "changed_files.py"
_early_gate = _load_module_from_path("_authority_shape_early_gate", _EARLY_GATE_PATH)
_changed_files = _load_module_from_path("_authority_shape_changed_files", _CHANGED_FILES_PATH)

AuthorityShapeEarlyGateError = _early_gate.AuthorityShapeEarlyGateError
evaluate_early_gate = _early_gate.evaluate_early_gate
write_result = _early_gate.write_result
ChangedFilesResolutionError = _changed_files.ChangedFilesResolutionError
resolve_changed_files = _changed_files.resolve_changed_files


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authority-shape early gate")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    parser.add_argument(
        "--output",
        default="outputs/authority_shape_preflight/authority_shape_early_gate_result.json",
        help="Output artifact path",
    )
    parser.add_argument(
        "--owner-registry",
        default="docs/architecture/system_registry.md",
        help="Canonical system owner registry path",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        changed_files = resolve_changed_files(
            repo_root=REPO_ROOT,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            explicit_changed_files=list(args.changed_files or []),
        )
    except ChangedFilesResolutionError as exc:
        raise AuthorityShapeEarlyGateError(str(exc)) from exc

    result = evaluate_early_gate(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        owner_registry_path=REPO_ROOT / args.owner_registry,
    )
    output_path = REPO_ROOT / args.output
    write_result(output_path, result)
    payload = result.to_dict()
    summary = {
        "status": payload["status"],
        "changed_files": changed_files,
        "hit_count": payload["summary"]["hit_count"],
        "rename_required_count": payload["summary"]["rename_required_count"],
        "review_required_count": payload["summary"]["review_required_count"],
        "output": str(output_path),
    }
    print(json.dumps(summary, indent=2))
    return 1 if result.status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
