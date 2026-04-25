#!/usr/bin/env python3
"""Run deterministic 3LS ownership + gate enforcement audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.system_registry_guard import parse_system_registry  # noqa: E402
from spectrum_systems.modules.governance.three_letter_system_enforcement import (  # noqa: E402
    evaluate_three_letter_system_enforcement,
)
from spectrum_systems.modules.governance.changed_files import (  # noqa: E402
    resolve_changed_files,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic 3LS ownership + gate enforcement audit.")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--changed-files", nargs="*", default=[])
    parser.add_argument("--policy-path", default="docs/governance/three_letter_system_policy.json")
    parser.add_argument("--output", default="outputs/three_letter_system_enforcement/three_letter_system_enforcement_audit_result.json")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    changed_files = resolve_changed_files(
        repo_root=REPO_ROOT,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        explicit_changed_files=list(args.changed_files or []),
    )

    policy_path = REPO_ROOT / args.policy_path
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    registry = parse_system_registry(REPO_ROOT / "docs/architecture/system_registry.md")

    result = evaluate_three_letter_system_enforcement(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        policy=policy,
        registry_model=registry,
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({"output": str(output_path), "final_decision": result["final_decision"], "violations": result["violations"]}, indent=2))
    return 1 if result["final_decision"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
