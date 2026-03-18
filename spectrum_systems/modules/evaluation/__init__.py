"""
Evaluation Framework — spectrum_systems/modules/evaluation/

Provides governed evaluation infrastructure for the full
meeting-minutes → working-paper pipeline.

Sub-modules
-----------
golden_dataset
    Loads and validates curated golden test cases from data/golden_cases/.
grounding
    Claim-level grounding verification against upstream pass artifacts.
comparison
    Structural and semantic comparison of expected vs actual outputs.
error_taxonomy
    Classification of evaluation failures into typed error categories.
regression
    Baseline storage and regression detection across evaluation runs.
eval_runner
    End-to-end evaluation orchestrator: runs golden cases, captures metrics,
    produces structured EvalResult records.
"""
