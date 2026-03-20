# Architecture Review Action Tracker

- **Source Review:** `docs/reviews/2026-03-20-reliability-control-loop-review.md`
- **Review ID:** 2026-03-20-reliability-control-loop-review
- **Owner:** Spectrum Systems Engineering
- **Last Updated:** 2026-03-20

## Critical Items

| ID | Action Item | Owner | Status | Target Repo | Blocking Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- |
| CR-1 | Define `override_artifact.schema.json` with required governance fields: `override_id`, `decision_id`, `approved_by`, `approved_at`, `justification`, `expiry_at` | Governance (spectrum-systems) | Open | spectrum-systems | None | Schema file added at `contracts/schemas/override_artifact.schema.json`; validates via Draft 2020-12; referenced in BU documentation |
| CR-2 | Update BU `_resolve_allow_to_proceed` to validate override artifact against schema, verify `decision_id` match, check `expiry_at`, and log artifact at INFO | Implementation (spectrum-runtime-engine or equivalent) | Open | implementation repo | CR-1 complete | Presence-only check removed; invalid override raises `EnforcementBridgeError`; valid override is fully logged |
| CR-3 | Fix BQ fail-open defaults: replace `"allow"` fallback for unknown replay statuses with `"fail"` or raise `ReplayDecisionError` | Implementation | Open | implementation repo | None | Unknown step status and unknown overall replay status raise rather than silently returning `allow`; tests cover both paths |
| CR-4 | Create `scripts/run_enforcement_bridge.py` CLI for BU | Implementation | Open | implementation repo | None | CLI accepts `--input`, `--override-artifact`, `--enforcement-scope`, `--output-dir`; exit 0=allowed, exit 1=blocked, exit 2=error; artifact written to output dir |

## High-Priority Items

| ID | Action Item | Owner | Status | Target Repo | Blocking Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- |
| HI-1 | Separate `require_review` exit code from `allow_with_warning` in BT CLI: assign exit 2 to `require_review`/blocking responses, exit 1 to `allow_with_warning` only | Implementation | Open | implementation repo | None | `require_review` returns exit ≥ 2; CI/CD pipelines halt on `require_review`; docstring exit code table updated |
| HI-2 | Define BQ→BS integration contract: extend `evaluation_monitor_record.schema.json` with optional `replay_analysis_summary` field (`reproducibility_score`, `drift_type`, `analysis_id`) | Governance (spectrum-systems) | Open | spectrum-systems | CR-3 complete | Schema updated; `build_monitor_record` accepts optional replay analysis; reproducibility surfaced in `sli_snapshot` |

## Medium-Priority Items

| ID | Action Item | Owner | Status | Target Repo | Blocking Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- |
| MI-1 | Add optional `applied_thresholds` field to `evaluation_budget_decision.schema.json`; BT populates when non-default thresholds are used | Governance (spectrum-systems) | Open | spectrum-systems | None | Schema updated; BT populates field on non-default input; artifact passes schema validation; field not required for default runs |
| MI-2 | Resolve BS `recommended_action` semantic ambiguity: rename to `monitor_signal` with non-authority annotation, or remove from schema entirely | Governance (spectrum-systems) | Open | spectrum-systems | None | No field with `freeze_changes` vocabulary exists at advisory level without clear authority labeling; BT remains sole authority for governed responses |

## Low-Priority Items

| ID | Action Item | Owner | Status | Target Repo | Blocking Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- |
| LI-1 | Type and validate the BU `context` dict interface; consider introducing a `EnforcementContext` typed dict or dataclass | Implementation | Open | implementation repo | CR-2 complete | BU interface has documented, validated context contract; unknown context keys raise or warn |
| LI-2 | Add `trace_id` propagation from regression runs into monitor records (requires upstream harness change) | Implementation | Open | implementation repo | HI-2 complete | `evaluation_monitor_record` includes trace IDs for evaluated runs; traceability from budget decision to specific traces is resolvable from artifacts alone |

## Blocking Items

- **CR-1 and CR-2 block pipeline expansion to production-grade gating.** Any new `require_review` trigger path added before CR-2 is deployed creates an unvalidated bypass route.
- **CR-4 (BU CLI) blocks operational readiness.** The enforcement bridge cannot be invoked as a governed pipeline step until the CLI exists.
- **CR-3 (BQ fail-open fix) blocks BQ integration into BS (HI-2).** Integrating BQ into the monitoring chain while fail-open defaults exist would propagate misleading `allow` signals into budget decisions.

## Deferred Items

- **BQ→BS integration implementation code** (implementation side of HI-2): Deferred until CR-3 is complete and tests pass. Trigger: CR-3 merged.
- **BQ `INDETERMINATE` policy threshold**: Deferred until HI-2 (BQ→BS integration) is complete. At that point, add an indeterminate-rate threshold to BS alert policy and BT budget status logic. Trigger: HI-2 complete.
- **BU context dict typing (LI-1)**: Deferred; low severity. Trigger: next governance review of BU interface contracts, or first external consumer of BU context documented.
