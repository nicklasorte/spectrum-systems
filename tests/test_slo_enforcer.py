"""Tests for BH–BJ SLO Enforcer (slo_enforcer.py).

Covers:
- healthy → allow
- degraded + acceptable burn rate → warn
- degraded + high burn rate → warn
- breached → block
- enforcement transitions
- fail-closed behaviour on malformed input
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.slo_enforcer import (  # noqa: E402
    ACTION_ALLOW,
    ACTION_BLOCK,
    ACTION_WARN,
    enforce_slo_policy,
    _HIGH_BURN_RATE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _low_burn() -> Dict[str, float]:
    """Burn rate clearly below high-burn-rate threshold."""
    return {
        "completeness": 0.0,
        "timeliness": 0.0,
        "traceability": 0.0,
        "traceability_integrity": 0.0,
        "overall": 0.05,
    }


def _high_burn() -> Dict[str, float]:
    """Burn rate clearly above high-burn-rate threshold."""
    return {
        "completeness": 0.25,
        "timeliness": 0.25,
        "traceability": 0.25,
        "traceability_integrity": 0.25,
        "overall": 0.25,
    }


def _zero_burn() -> Dict[str, float]:
    return {
        "completeness": 0.0,
        "timeliness": 0.0,
        "traceability": 0.0,
        "traceability_integrity": 0.0,
        "overall": 0.0,
    }


# ---------------------------------------------------------------------------
# enforce_slo_policy
# ---------------------------------------------------------------------------

class TestEnforceSloPolicy:
    # --- healthy ---

    def test_healthy_zero_burn_allows(self):
        result = enforce_slo_policy("healthy", _zero_burn())
        assert result["action"] == ACTION_ALLOW

    def test_healthy_any_burn_allows(self):
        result = enforce_slo_policy("healthy", _high_burn())
        assert result["action"] == ACTION_ALLOW

    def test_healthy_reason_not_empty(self):
        result = enforce_slo_policy("healthy", _zero_burn())
        assert result.get("reason")

    # --- degraded ---

    def test_degraded_low_burn_warns(self):
        result = enforce_slo_policy("degraded", _low_burn())
        assert result["action"] == ACTION_WARN

    def test_degraded_high_burn_warns(self):
        result = enforce_slo_policy("degraded", _high_burn())
        assert result["action"] == ACTION_WARN

    def test_degraded_zero_burn_warns(self):
        result = enforce_slo_policy("degraded", _zero_burn())
        assert result["action"] == ACTION_WARN

    def test_degraded_reason_mentions_degraded(self):
        result = enforce_slo_policy("degraded", _high_burn())
        assert "degraded" in result["reason"].lower()

    def test_degraded_high_burn_reason_mentions_burn_rate(self):
        result = enforce_slo_policy("degraded", _high_burn())
        assert "burn" in result["reason"].lower()

    # --- breached ---

    def test_breached_blocks(self):
        result = enforce_slo_policy("breached", _zero_burn())
        assert result["action"] == ACTION_BLOCK

    def test_breached_high_burn_blocks(self):
        result = enforce_slo_policy("breached", _high_burn())
        assert result["action"] == ACTION_BLOCK

    def test_breached_reason_not_empty(self):
        result = enforce_slo_policy("breached", _zero_burn())
        assert result.get("reason")

    # --- enforcement transitions ---

    def test_healthy_to_degraded_transition(self):
        assert enforce_slo_policy("healthy", _zero_burn())["action"] == ACTION_ALLOW
        assert enforce_slo_policy("degraded", _zero_burn())["action"] == ACTION_WARN

    def test_degraded_to_breached_transition(self):
        assert enforce_slo_policy("degraded", _low_burn())["action"] == ACTION_WARN
        assert enforce_slo_policy("breached", _low_burn())["action"] == ACTION_BLOCK

    # --- output structure ---

    def test_result_has_action_and_reason(self):
        result = enforce_slo_policy("healthy", _zero_burn())
        assert "action" in result
        assert "reason" in result

    def test_action_is_one_of_three_values(self):
        for status in ("healthy", "degraded", "breached"):
            result = enforce_slo_policy(status, _zero_burn())
            assert result["action"] in (ACTION_ALLOW, ACTION_WARN, ACTION_BLOCK)

    # --- fail-closed behaviour ---

    def test_unknown_status_blocks(self):
        result = enforce_slo_policy("unknown_status", _zero_burn())
        assert result["action"] == ACTION_BLOCK

    def test_none_status_blocks(self):
        result = enforce_slo_policy(None, _zero_burn())  # type: ignore[arg-type]
        assert result["action"] == ACTION_BLOCK

    def test_non_dict_burn_rate_blocks(self):
        result = enforce_slo_policy("healthy", "bad")  # type: ignore[arg-type]
        assert result["action"] == ACTION_BLOCK

    def test_missing_overall_in_burn_rate_defaults_to_zero(self):
        """Missing 'overall' key should default to 0.0 (not crash)."""
        result = enforce_slo_policy("degraded", {"completeness": 0.5})
        assert result["action"] == ACTION_WARN

    def test_fail_closed_reason_not_empty(self):
        result = enforce_slo_policy(None, _zero_burn())  # type: ignore[arg-type]
        assert result.get("reason")

    # --- burn rate threshold boundary ---

    def test_burn_rate_exactly_at_threshold_is_not_high(self):
        """Overall burn rate equal to threshold is not considered high."""
        br = dict(_zero_burn())
        br["overall"] = _HIGH_BURN_RATE_THRESHOLD
        result = enforce_slo_policy("degraded", br)
        assert result["action"] == ACTION_WARN

    def test_burn_rate_just_above_threshold_is_high(self):
        br = dict(_zero_burn())
        br["overall"] = _HIGH_BURN_RATE_THRESHOLD + 0.001
        result = enforce_slo_policy("degraded", br)
        assert result["action"] == ACTION_WARN
        assert "burn" in result["reason"].lower()
