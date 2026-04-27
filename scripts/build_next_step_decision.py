"""Build deterministic next-step decision artifact for dashboard consumption.

Usage:
    python scripts/build_next_step_decision.py [--out artifacts/next_step_decision_report.json]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.next_step import write_next_step_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "artifacts" / "next_step_decision_report.json"),
        help="Output artifact path.",
    )
    args = parser.parse_args(argv)

    report, hard_failure = write_next_step_report(REPO_ROOT, Path(args.out))
    print(f"[next-step] status={report['status']} readiness={report['readiness_state']}")
    if hard_failure:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
