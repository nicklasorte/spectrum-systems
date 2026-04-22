"""EVL: Stale fixture detector.

Identifies eval fixtures that haven't been re-run in threshold_days days.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "evals" / "fixtures"
DEFAULT_THRESHOLD_DAYS = 30


def detect_stale_fixtures(
    threshold_days: int = DEFAULT_THRESHOLD_DAYS,
    fixtures_dir: Path | None = None,
) -> List[Dict]:
    """Return fixtures whose mtime exceeds threshold_days.

    Each entry contains: fixture path, age_days, is_stale.
    """
    base = fixtures_dir or FIXTURES_DIR
    if not base.exists():
        return []

    stale: List[Dict] = []
    now = time.time()

    for fixture_path in base.rglob("*"):
        if not fixture_path.is_file():
            continue
        mtime = fixture_path.stat().st_mtime
        age_days = (now - mtime) / 86400

        if age_days > threshold_days:
            stale.append(
                {
                    "fixture": str(fixture_path.relative_to(REPO_ROOT)),
                    "age_days": round(age_days, 1),
                    "is_stale": True,
                    "threshold_days": threshold_days,
                }
            )

    return stale
