# RTX-WPG-01

## Scope
Red-team round 1 for WPG pipeline.

## Attacks and findings
1. Hallucinated consensus: mitigated by preserving per-agency `agency_views` and explicit `sources` in `faq_artifact`.
2. Suppressed conflict: mitigated by `faq_conflict_artifact` with unresolved contradiction count and control escalation.
3. Fake traceability: mitigated by segment-level source references (`segment_ref`, `speaker`, `agency`).
4. Weak clustering: mitigated by deterministic theme assignment with unknown capture fallback.
5. Missing eval bypass: mitigated by stage-level `eval_case`, `eval_result`, `eval_summary`, and control decision output.

## Mandatory fixes applied
- Added enforced conflict artifact generation and unresolved contradiction count wiring.
- Added confidence score artifact with low-confidence accounting.
- Added control-loop decision object (`ALLOW/WARN/BLOCK/FREEZE`) per stage.
