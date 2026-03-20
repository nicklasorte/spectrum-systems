"""
Working Paper Engine — service.py

Top-level pipeline orchestrator for the working_paper_engine module.

Implements the 4-stage pipeline:
  OBSERVE → INTERPRET → SYNTHESIZE → VALIDATE

and assembles the final governed JSON output bundle.

Public API
----------
WorkingPaperEngine
    Class-based orchestrator supporting step-by-step execution.
run_pipeline
    Convenience function to run the full pipeline from EngineInputs to bundle.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from spectrum_systems.modules.working_paper_engine.artifacts import (
    assemble_bundle,
    validate_bundle_schema,
)
from spectrum_systems.modules.working_paper_engine.interpret import (
    extract_gap_items,
    run_interpret,
)
from spectrum_systems.modules.working_paper_engine.models import (
    EngineInputs,
    InterpretResult,
    ObserveResult,
    ProvenanceMode,
    SourceDocumentExcerpt,
    SourceType,
    StudyPlanExcerpt,
    SynthesizeResult,
    TranscriptExcerpt,
    ValidateResult,
)
from spectrum_systems.modules.working_paper_engine.observe import run_observe
from spectrum_systems.modules.working_paper_engine.synthesize import run_synthesize
from spectrum_systems.modules.working_paper_engine.validate import run_validate


class WorkingPaperEngine:
    """Orchestrates the 4-stage working paper generation pipeline.

    Usage
    -----
    engine = WorkingPaperEngine(inputs)
    bundle = engine.run()

    Or step by step:
    engine.observe()
    engine.interpret()
    engine.synthesize()
    engine.validate()
    bundle = engine.assemble()
    """

    def __init__(
        self,
        inputs: EngineInputs,
        quantitative_results_available: bool = False,
        provenance_mode: ProvenanceMode = ProvenanceMode.BEST_EFFORT,
    ) -> None:
        self.inputs = inputs
        self.quantitative_results_available = quantitative_results_available
        self.provenance_mode = provenance_mode

        self._observe_result: Optional[ObserveResult] = None
        self._interpret_result: Optional[InterpretResult] = None
        self._synth_result: Optional[SynthesizeResult] = None
        self._validate_result: Optional[ValidateResult] = None

    def observe(self) -> ObserveResult:
        """Stage 1: Extract raw facts, questions, constraints, assumptions."""
        self._observe_result = run_observe(self.inputs)
        return self._observe_result

    def interpret(self) -> InterpretResult:
        """Stage 2: Map observations to structural buckets, identify gaps."""
        if self._observe_result is None:
            self.observe()
        assert self._observe_result is not None
        self._interpret_result = run_interpret(self._observe_result)
        return self._interpret_result

    def synthesize(self) -> SynthesizeResult:
        """Stage 3: Generate Sections 1–7, FAQ, and gap register."""
        if self._interpret_result is None:
            self.interpret()
        assert self._interpret_result is not None
        gap_items = extract_gap_items(self._interpret_result)
        self._synth_result = run_synthesize(
            inputs=self.inputs,
            interpret_result=self._interpret_result,
            gap_items=gap_items,
            quantitative_results_available=self.quantitative_results_available,
        )
        return self._synth_result

    def validate(self) -> ValidateResult:
        """Stage 4: Run validation checks across the synthesized output."""
        if self._synth_result is None:
            self.synthesize()
        assert self._synth_result is not None
        self._validate_result = run_validate(self._synth_result)
        return self._validate_result

    def assemble(self) -> Dict[str, Any]:
        """Assemble the final governed JSON output bundle."""
        if self._validate_result is None:
            self.validate()
        assert self._synth_result is not None
        assert self._validate_result is not None
        return assemble_bundle(
            inputs=self.inputs,
            synth_result=self._synth_result,
            validate_result=self._validate_result,
            provenance_mode=self.provenance_mode,
        )

    def run(self) -> Dict[str, Any]:
        """Run the full pipeline and return the governed output bundle."""
        self.observe()
        self.interpret()
        self.synthesize()
        self.validate()
        return self.assemble()


def run_pipeline(
    inputs: EngineInputs,
    quantitative_results_available: bool = False,
    provenance_mode: ProvenanceMode = ProvenanceMode.BEST_EFFORT,
) -> Dict[str, Any]:
    """Run the full working paper engine pipeline.

    Parameters
    ----------
    inputs:
        Aggregated engine inputs (source documents, transcripts, study plans).
    quantitative_results_available:
        Set True only if verified quantitative results are present in inputs.
    provenance_mode:
        Provenance tracking mode.

    Returns
    -------
    dict
        The governed output bundle.
    """
    engine = WorkingPaperEngine(
        inputs=inputs,
        quantitative_results_available=quantitative_results_available,
        provenance_mode=provenance_mode,
    )
    return engine.run()
