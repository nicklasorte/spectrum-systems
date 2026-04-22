"""ENT: Entropy accumulation detector.

Tracks correction patterns across execution history.
Flags issue types that have been corrected more than RECURRENCE_THRESHOLD times,
recommending policy or eval adoption instead of continued manual correction.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List

RECURRENCE_THRESHOLD = 2


def detect_repeated_corrections(corrections: List[Dict]) -> List[Dict]:
    """Identify issue types corrected more than RECURRENCE_THRESHOLD times.

    Parameters
    ----------
    corrections:
        List of correction records, each with an 'issue_type' field.

    Returns
    -------
    List of recurrent issue reports with recommendation.
    """
    counts: Counter = Counter(c.get("issue_type", "UNKNOWN") for c in corrections)

    recurrent = []
    for issue_type, count in counts.items():
        if count > RECURRENCE_THRESHOLD:
            recurrent.append({
                "issue_type": issue_type,
                "correction_count": count,
                "recommendation": (
                    f"Issue '{issue_type}' has been corrected {count} times. "
                    "Convert to a governing policy or eval case instead of continued manual correction."
                ),
            })

    return recurrent
