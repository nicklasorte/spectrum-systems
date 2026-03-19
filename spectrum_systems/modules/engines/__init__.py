"""
Engines — spectrum_systems/modules/engines/__init__.py

Reasoning engine adapters for the evaluation and operationalization pipeline.

Available adapters
------------------
DecisionExtractionAdapter
    Narrow real-engine adapter for decision extraction.
    Uses deterministic pattern matching; labelled ``execution_mode =
    "deterministic_pattern"`` to be explicit about the absence of a live model.
"""
from spectrum_systems.modules.engines.decision_extraction_adapter import DecisionExtractionAdapter

__all__ = ["DecisionExtractionAdapter"]
