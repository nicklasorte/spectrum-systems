from __future__ import annotations

from typing import Any, Dict, Iterable, Set


class RequiredEvalMissingError(RuntimeError):
    """Raised when required evals are missing for an artifact family."""


def enforce_required_evals(registry_entry: Dict[str, Any], completed_eval_ids: Iterable[str]) -> None:
    required = set(registry_entry.get("required_eval_ids", []))
    completed: Set[str] = set(completed_eval_ids)
    missing = sorted(required - completed)
    if missing:
        raise RequiredEvalMissingError(
            f"missing required eval ids for {registry_entry.get('artifact_family', 'unknown')}: {missing}"
        )
