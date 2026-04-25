"""
Orchestration module — spectrum_systems/modules/orchestration/

TLC (Top-Level Conductor) is the sole orchestration authority.
Execution steps pass through the bounded step harness in this package.

This package provides:
- pqx_step_harness: bounded, traced execution wrapper
- tlc_router: artifact-type routing for the transcript pipeline
"""
