#!/usr/bin/env python3
"""OC-16: Fast trust gate runner.

Loads the fast trust gate manifest and produces a coverage audit. The
runner does NOT execute the full pytest suite; it verifies that the
manifest covers every required seam and (optionally) renders the
manifest selectors so the operator can run them individually.

Exit codes:
  0  manifest coverage is sufficient
  1  manifest coverage is insufficient (missing seams or selectors)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.fast_trust_gate import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    audit_fast_trust_gate_coverage,
    load_fast_trust_gate_manifest,
)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit the fast trust gate manifest for required-seam coverage."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="path to the fast trust gate manifest JSON",
    )
    parser.add_argument(
        "--print-selectors",
        action="store_true",
        help="print the selectors so the operator can run them individually",
    )
    args = parser.parse_args(argv)

    manifest = load_fast_trust_gate_manifest(args.manifest)
    coverage = audit_fast_trust_gate_coverage(manifest)

    print(f"manifest_id: {manifest.get('manifest_id', '-')}")
    print(f"coverage_status: {coverage['coverage_status']}")
    print(f"reason_code: {coverage['reason_code']}")
    if coverage["missing_seams"]:
        print(f"missing_seams: {','.join(coverage['missing_seams'])}")
    if coverage["missing_selectors"]:
        print(f"missing_selectors: {','.join(coverage['missing_selectors'])}")

    if args.print_selectors:
        print("\nselectors:")
        for sel in manifest.get("selectors", []) or []:
            print(
                f"  {sel.get('seam'):28} {sel.get('selector_kind'):14} {sel.get('selector')}"
            )

    return 0 if coverage["coverage_status"] == "sufficient" else 1


if __name__ == "__main__":
    raise SystemExit(main())
