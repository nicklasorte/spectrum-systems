"""Tests for Phase 4.4: SignalDefinitions."""

import pytest

from spectrum_systems.signals.signal_definitions import (
    SIGNAL_DEFINITIONS,
    SignalDefinition,
    get_signal_definition,
    get_signal_interpretation,
)


# ---------------------------------------------------------------------------
# test_signal_definitions_defined
# ---------------------------------------------------------------------------
def test_signal_definitions_defined():
    required = {"eval_pass_rate", "signal_latency", "drift_rate", "lineage_completeness"}
    assert required.issubset(SIGNAL_DEFINITIONS.keys())


# ---------------------------------------------------------------------------
# test_signal_interpretation_clear
# ---------------------------------------------------------------------------
def test_signal_interpretation_clear():
    for name, defn in SIGNAL_DEFINITIONS.items():
        interp = get_signal_interpretation(name)
        assert isinstance(interp, str)
        assert len(interp) > 20, f"Interpretation for '{name}' is too short"


# ---------------------------------------------------------------------------
# test_acceptable_ranges_documented
# ---------------------------------------------------------------------------
def test_acceptable_ranges_documented():
    for name, defn in SIGNAL_DEFINITIONS.items():
        lo, hi = defn.acceptable_range
        assert lo <= hi, f"Range for '{name}' inverted"
        assert lo <= defn.target <= hi, f"Target for '{name}' outside acceptable range"


# ---------------------------------------------------------------------------
# test_unknown_signal_raises
# ---------------------------------------------------------------------------
def test_unknown_signal_raises():
    with pytest.raises(ValueError, match="Unknown signal"):
        get_signal_definition("nonexistent_signal")


# ---------------------------------------------------------------------------
# test_signal_to_dict
# ---------------------------------------------------------------------------
def test_signal_to_dict():
    defn = SIGNAL_DEFINITIONS["eval_pass_rate"]
    d = defn.to_dict()
    assert set(d.keys()) == {"name", "unit", "target", "acceptable_range", "interpretation"}
    assert d["unit"] == "%"


# ---------------------------------------------------------------------------
# test_is_in_range
# ---------------------------------------------------------------------------
def test_is_in_range():
    defn = SIGNAL_DEFINITIONS["signal_latency"]
    assert defn.is_in_range(50.0) is True
    assert defn.is_in_range(199.9) is True
    assert defn.is_in_range(200.1) is False
    assert defn.is_in_range(-1.0) is False
