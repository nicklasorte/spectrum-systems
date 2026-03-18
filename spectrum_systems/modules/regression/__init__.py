"""
Regression module — spectrum_systems/modules/regression/__init__.py

Public exports for the regression harness package.
"""
from spectrum_systems.modules.regression.harness import (
    RegressionHarness,
    RegressionPolicy,
    RegressionReport,
)
from spectrum_systems.modules.regression.baselines import BaselineManager
from spectrum_systems.modules.regression.gates import evaluate_dimension_gate, evaluate_policy_gates
from spectrum_systems.modules.regression.attribution import attribute_regressions_to_passes
from spectrum_systems.modules.regression.recommendations import generate_recommendations

__all__ = [
    "RegressionHarness",
    "RegressionPolicy",
    "RegressionReport",
    "BaselineManager",
    "evaluate_dimension_gate",
    "evaluate_policy_gates",
    "attribute_regressions_to_passes",
    "generate_recommendations",
]
