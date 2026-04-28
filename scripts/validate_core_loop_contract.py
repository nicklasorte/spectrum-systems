#!/usr/bin/env python3
"""CL-01 thin CLI — validate a core_loop_contract artifact.

Loads a candidate ``core_loop_contract`` JSON file and runs the
pure validator. Returns a non-zero exit code on contract violations.
The script is a non-owning renderer; canonical authority for AEX, PQX,
EVL, TPA, CDE, SEL is unchanged.

Exit codes:
  0  contract is well-formed
  1  contract violations detected
  2  IO / parse errors
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.core_loop_contract import (  # noqa: E402
    build_default_core_loop_contract,
    validate_core_loop_contract,
)


def _load_contract(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"contract not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate core_loop_contract artifact")
    parser.add_argument(
        "--path",
        type=Path,
        default=REPO_ROOT / "contracts" / "examples" / "core_loop_contract.json",
        help="Path to a candidate core_loop_contract JSON artifact.",
    )
    parser.add_argument(
        "--print-default",
        action="store_true",
        help="Emit the canonical in-memory core_loop_contract and exit 0.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the validation result as JSON.",
    )
    args = parser.parse_args(argv)

    if args.print_default:
        print(json.dumps(build_default_core_loop_contract(), indent=2))
        return 0

    try:
        contract = _load_contract(args.path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = validate_core_loop_contract(contract)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"core_loop_contract: ok={result['ok']}")
        print(f"primary_reason:     {result['primary_reason']}")
        for v in result["violations"]:
            print(f"  - {v.get('reason_code')}: {v}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
