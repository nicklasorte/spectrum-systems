#!/usr/bin/env python3
"""AEX shift-left authority-shape admission CLI (AEX-FRE-AUTH-SHAPE-01).

Runs before PQX/build preflight to catch authority-shape vocabulary leaks
earlier than ``run_authority_shape_preflight.py`` and
``run_system_registry_guard.py``.

Output:
    outputs/authority_shape_admission/authority_shape_admission_result.json

Exit:
    * non-zero when admission status is ``block`` and ``--suggest-only`` is
      not provided (so PQX cannot proceed on unrepaired authority-shape leaks)
    * zero in ``--suggest-only`` mode (advisory shift-left run)

Like the upstream preflight, this CLI loads its support modules by file path
to avoid pulling in ``jsonschema`` on minimal CI surfaces.
"""

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


_PREFLIGHT_PATH = REPO_ROOT / "spectrum_systems" / "governance" / "authority_shape_preflight.py"
_CHANGED_FILES_PATH = REPO_ROOT / "spectrum_systems" / "modules" / "governance" / "changed_files.py"
_ADMISSION_PATH = REPO_ROOT / "spectrum_systems" / "aex" / "authority_shape_admission.py"

_preflight = _load_module_from_path("_admission_preflight_core", _PREFLIGHT_PATH)
_changed_files = _load_module_from_path("_admission_changed_files", _CHANGED_FILES_PATH)
_admission = _load_module_from_path("_admission_aex_module", _ADMISSION_PATH)

resolve_changed_files = _changed_files.resolve_changed_files
ChangedFilesResolutionError = _changed_files.ChangedFilesResolutionError
load_vocabulary = _preflight.load_vocabulary
AuthorityShapePreflightError = _preflight.AuthorityShapePreflightError
evaluate_admission = _admission.evaluate_admission


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authority-shape admission (AEX shift-left)")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--changed-files", nargs="*", default=[])
    parser.add_argument(
        "--vocabulary",
        default="contracts/governance/authority_shape_vocabulary.json",
    )
    parser.add_argument(
        "--output",
        default="outputs/authority_shape_admission/authority_shape_admission_result.json",
    )
    parser.add_argument(
        "--suggest-only",
        action="store_true",
        help="Emit advisory diagnostics but always exit 0",
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
        raise AuthorityShapePreflightError(str(exc)) from exc

    vocab = load_vocabulary(REPO_ROOT / args.vocabulary)
    payload = evaluate_admission(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        vocab=vocab,
        mode="suggest-only" if args.suggest_only else "enforce",
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": payload["status"],
        "mode": payload["mode"],
        "changed_files": changed_files,
        "violation_count": payload["summary"]["violation_count"],
        "block_count": payload["summary"]["block_count"],
        "output": str(output_path),
    }
    if payload["diagnostics"]:
        summary["first_diagnostics"] = [
            {
                "file": d["file"],
                "line": d.get("line"),
                "symbol": d.get("symbol"),
                "cluster": d["cluster"],
                "canonical_owner": d.get("canonical_owner"),
                "context_kind": d["context_kind"],
                "fail_closed_reason_code": d["fail_closed_reason_code"],
                "suggested_safe_replacements": d.get("suggested_safe_replacements", []),
            }
            for d in payload["diagnostics"][:10]
        ]
    print(json.dumps(summary, indent=2))

    if args.suggest_only:
        return 0
    return 1 if payload["status"] == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
