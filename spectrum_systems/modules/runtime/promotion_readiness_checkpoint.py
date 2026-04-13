"""Hard promotion-readiness checkpoint for bounded artifact family."""

from __future__ import annotations


def enforce_promotion_readiness(*, lineage: dict[str, bool]) -> tuple[bool, list[str]]:
    required = [
        "tax_lineage",
        "bax_lineage",
        "cax_lineage",
        "cde_lineage",
        "replay_complete",
        "trace_complete",
        "required_eval_coverage",
        "context_preflight_success",
    ]
    missing = [key for key in required if not bool(lineage.get(key, False))]
    return len(missing) == 0, [f"missing:{item}" for item in missing]
