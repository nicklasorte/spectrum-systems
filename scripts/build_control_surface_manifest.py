#!/usr/bin/env python3
"""Build deterministic control surface manifest artifact and validate schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.control_surface_manifest import (
    ControlSurfaceManifestError,
    build_control_surface_manifest,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build control surface manifest")
    parser.add_argument("--output-dir", default="outputs/control_surface_manifest", help="Output directory")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "control_surface_manifest.json"

    try:
        manifest = build_control_surface_manifest()
        schema = load_schema("control_surface_manifest")
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(manifest), key=lambda err: list(err.absolute_path))
        if errors:
            details = "; ".join(error.message for error in errors)
            raise ControlSurfaceManifestError(f"manifest failed schema validation: {details}")
    except ControlSurfaceManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
