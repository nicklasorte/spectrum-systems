"""
Working Paper Engine — spectrum_systems/modules/working_paper_engine/__init__.py

Public API for the working_paper_engine module.

This module implements a 4-stage pipeline (OBSERVE → INTERPRET → SYNTHESIZE → VALIDATE)
for generating federal spectrum-study working papers with full traceability,
explicit uncertainty, and governed JSON output bundles.

Public surface
--------------
WorkingPaperEngine
    Top-level orchestrator. Import from service.py.
run_pipeline
    Convenience function to run the full pipeline from inputs to bundle.
"""

from spectrum_systems.modules.working_paper_engine.service import (
    WorkingPaperEngine,
    run_pipeline,
)

__all__ = [
    "WorkingPaperEngine",
    "run_pipeline",
]
