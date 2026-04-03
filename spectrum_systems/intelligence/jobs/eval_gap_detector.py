from __future__ import annotations

from typing import Dict, Iterable, List


def detect_eval_gaps(required_eval_ids: Iterable[str], completed_eval_ids: Iterable[str]) -> List[str]:
    return sorted(set(required_eval_ids) - set(completed_eval_ids))
