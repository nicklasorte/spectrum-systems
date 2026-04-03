# Plan — TOP8-CHATGPT-CAPABILITY-STACK — 2026-04-03

## Prompt type
PLAN

## Roadmap item
TOP8-BATCH-E (repo-native capability integration pass)

## Objective
Implement schema-bound, fail-closed, trace-linked module surfaces and tests for the top 8 ChatGPT-derived capability areas without redesigning repository architecture.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-TOP8-CHATGPT-CAPABILITY-STACK-2026-04-03.md | CREATE | Required PLAN artifact before multi-file BUILD work |
| docs/reviews/top8_chatgpt_capability_stack_review.md | CREATE | Required review artifact with residual risks |
| contracts/schemas/eval_registry_entry.schema.json | CREATE | Eval expansion contract |
| contracts/schemas/eval_dataset_record.schema.json | CREATE | Eval expansion contract |
| contracts/schemas/eval_slice_definition.schema.json | CREATE | Eval expansion contract |
| contracts/schemas/eval_regression_report.schema.json | CREATE | Eval expansion contract |
| contracts/schemas/model_route_comparison_record.schema.json | CREATE | Eval/routing comparison contract |
| contracts/schemas/drift_signal_record.schema.json | CREATE | Pulse intelligence contract |
| contracts/schemas/override_hotspot_report.schema.json | CREATE | Pulse intelligence contract |
| contracts/schemas/evidence_gap_hotspot_report.schema.json | CREATE | Pulse intelligence contract |
| contracts/schemas/trust_posture_snapshot.schema.json | CREATE | Pulse intelligence contract |
| contracts/schemas/improvement_recommendation_record.schema.json | CREATE | Pulse intelligence contract |
| contracts/schemas/trend_report_artifact.schema.json | CREATE | Pulse intelligence contract |
| contracts/schemas/context_bundle_record.schema.json | CREATE | Context governance contract |
| contracts/schemas/context_source_admission_record.schema.json | CREATE | Context governance contract |
| contracts/schemas/context_conflict_record.schema.json | CREATE | Context governance contract |
| contracts/schemas/context_recipe_spec.schema.json | CREATE | Context governance contract |
| contracts/schemas/routing_policy.schema.json | MODIFY | Routing policy hardening for deterministic policy/version/budgets |
| contracts/examples/routing_policy.json | MODIFY | Align canonical example with routing_policy schema v1.1.0 additions |
| contracts/schemas/routing_decision_record.schema.json | CREATE | Routing decision artifact contract |
| contracts/schemas/route_candidate_set.schema.json | CREATE | Routing candidate set contract |
| contracts/schemas/trace_diff_report.schema.json | CREATE | Tracing/replay explainability contract |
| contracts/schemas/explain_run_report.schema.json | CREATE | Tracing intelligence explain-run contract |
| contracts/standards-manifest.json | MODIFY | Canonical contract registry version/pins update |
| spectrum_systems/eval/__init__.py | CREATE | New eval package surface |
| spectrum_systems/eval/registry/__init__.py | CREATE | Eval registry package |
| spectrum_systems/eval/registry/registry.py | CREATE | Required-eval enforcement + registry logic |
| spectrum_systems/eval/datasets/__init__.py | CREATE | Eval dataset package |
| spectrum_systems/eval/datasets/datasets.py | CREATE | Dataset record support |
| spectrum_systems/eval/runners/__init__.py | CREATE | Eval runner package |
| spectrum_systems/eval/runners/judge_runner.py | CREATE | Judge runner with strict structured output |
| spectrum_systems/eval/runners/pairwise.py | CREATE | Pairwise eval support |
| spectrum_systems/eval/runners/slice_summary.py | CREATE | Slice summary generation |
| spectrum_systems/eval/runners/regression.py | CREATE | Regression report generation |
| spectrum_systems/intelligence/__init__.py | CREATE | Intelligence package surface |
| spectrum_systems/intelligence/pulse.py | CREATE | Pulse signal aggregation |
| spectrum_systems/intelligence/jobs/__init__.py | CREATE | Pulse jobs package |
| spectrum_systems/intelligence/jobs/drift_monitor.py | CREATE | Drift monitor job |
| spectrum_systems/intelligence/jobs/eval_gap_detector.py | CREATE | Eval gap detector job |
| spectrum_systems/intelligence/jobs/override_hotspot_detector.py | CREATE | Override hotspot detector job |
| spectrum_systems/intelligence/jobs/evidence_gap_hotspot_detector.py | CREATE | Evidence gap hotspot detector job |
| spectrum_systems/intelligence/jobs/trust_posture_builder.py | CREATE | Trust posture builder job |
| spectrum_systems/ai_adapter/__init__.py | CREATE | AI adapter package surface |
| spectrum_systems/ai_adapter/structured_client.py | CREATE | Structured output hardening + artifact emission |
| spectrum_systems/artifacts/registry/__init__.py | CREATE | Artifact registry helpers |
| spectrum_systems/artifacts/registry/model_records.py | CREATE | ai_model_request/response artifact builders |
| spectrum_systems/pqx/__init__.py | CREATE | PQX package extension |
| spectrum_systems/pqx/steps/__init__.py | CREATE | PQX steps package |
| spectrum_systems/pqx/steps/multi_pass_pipeline.py | CREATE | Extract/critique/contradiction/gap/synthesis pipeline |
| spectrum_systems/context/__init__.py | CREATE | Context package |
| spectrum_systems/context/bundles.py | CREATE | Deterministic governed context bundle builder |
| spectrum_systems/routing/__init__.py | CREATE | Routing package |
| spectrum_systems/routing/policy.py | CREATE | Deterministic route selection + artifacts |
| spectrum_systems/judgment/__init__.py | CREATE | Judgment package |
| spectrum_systems/judgment/engine.py | CREATE | Judgment capture/reuse + policy application |
| spectrum_systems/judgment/evals/__init__.py | CREATE | Judgment eval namespace |
| spectrum_systems/judgment/longitudinal/__init__.py | CREATE | Longitudinal namespace |
| spectrum_systems/tracing/__init__.py | CREATE | Tracing package |
| spectrum_systems/tracing/explain_runs.py | CREATE | Explain-run helper |
| spectrum_systems/replay/__init__.py | CREATE | Replay package |
| spectrum_systems/replay/trace_diff.py | CREATE | Run-vs-run trace diff support |
| tests/test_top8_capability_stack.py | CREATE | Capability + fail-closed + schema tests |

## Contracts touched
New contracts introduced in `contracts/schemas/` listed above and one routing contract update (`routing_policy`). Standards manifest pins will be updated accordingly.

## Tests that must pass after execution
1. `pytest tests/test_top8_capability_stack.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `pytest tests/test_module_architecture.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/golden-path-check/run.sh eval_dataset`
6. `.codex/skills/contract-boundary-audit/run.sh`
7. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign existing runtime/control-loop module architecture.
- Do not remove or disable any existing tests.
- Do not introduce network-bound test behavior.
- Do not create new repositories.

## Dependencies
- Existing contract loader + validation framework remains authoritative.
- Existing deterministic ID utility remains canonical for artifact identity.
