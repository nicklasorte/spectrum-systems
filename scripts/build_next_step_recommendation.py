"""Build deterministic next-step recommendation artifact for dashboard consumption.

Usage:
    python scripts/build_next_step_recommendation.py [--out artifacts/next_step_recommendation_report.json]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.dashboard_3ls.next_step_recommendation import write_next_step_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "artifacts" / "next_step_recommendation_report.json"),
        help="Output artifact path.",
    )
    args = parser.parse_args(argv)

    report, hard_failure = write_next_step_report(REPO_ROOT, Path(args.out))
    print(f"[next-step-recommendation] status={report['status']} readiness={report['readiness_state']}")
    return 1 if hard_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
