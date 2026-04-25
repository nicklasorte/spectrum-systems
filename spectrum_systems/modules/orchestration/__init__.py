"""
Orchestration module — spectrum_systems/modules/orchestration/

TLC (Top-Level Conductor) is the sole orchestration authority.
PQX is the sole execution authority.

This package provides:
- pqx_step_harness: bounded, traced execution wrapper
- tlc_router: artifact-type routing for the transcript pipeline
"""
