"""Deterministic routing policy helper for bounded artifact family."""

from __future__ import annotations


def select_route(*, artifact_family: str, preferred_route: str | None, fallback_route: str) -> dict[str, str]:
    route = preferred_route or fallback_route
    return {
        "artifact_family": artifact_family,
        "selected_route": route,
        "decision_reason": "preferred_route" if preferred_route else "fallback_route",
    }
