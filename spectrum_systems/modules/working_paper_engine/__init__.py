"""
Working Paper Engine — spectrum_systems/modules/working_paper_engine

A 4-stage deterministic pipeline for generating federal spectrum-study
working papers with governed, traceable outputs.

Stages: OBSERVE → INTERPRET → SYNTHESIZE → VALIDATE

Public entry-point: service.run_pipeline(inputs) → WorkingPaperBundle
"""

from .service import run_pipeline
from .models import (
    WorkingPaperInputs,
    WorkingPaperBundle,
)

__all__ = [
    "run_pipeline",
    "WorkingPaperInputs",
    "WorkingPaperBundle",
]
