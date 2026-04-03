# Plan — BATCH-R — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-R — RVW + RPT governed Claude review system

## Objective
Implement one governed review subsystem that deterministically triggers typed reviews, captures machine-readable review artifacts, bridges review findings into eval/control, hardens required-review gates, and emits observability/learning artifacts without introducing a second control authority.

## Intent
- Add strict contract support for typed review requests and review observability artifacts.
- Enforce deterministic review-trigger policy for surgical/failure/batch_architecture/hard_gate/strategic reviews.
- Harden review→eval→control wiring to fail closed when required review is missing/unsatisfied.
- Expand review-failure derived eval generation with deterministic recurrence tracking and priority marking.
- Produce design-only judgment bridge artifact and review-eval hardening report.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-R-2026-04-03.md | CREATE | Required plan-first artifact for this batch. |
| PLANS.md | MODIFY | Register active BATCH-R plan entry. |
| contracts/schemas/review_request.schema.json | CREATE | New typed review request contract. |
| contracts/schemas/prompt_queue_review_trigger.schema.json | MODIFY | Add governed review request payload and type enums to trigger artifact. |
| contracts/schemas/review_control_signal.schema.json | MODIFY | Tighten review type taxonomy and trace linkage for governed review artifacts. |
| contracts/schemas/review_failure_summary.schema.json | CREATE | Observability artifact contract for review failure summary. |
| contracts/schemas/review_hotspot_report.schema.json | CREATE | Observability artifact contract for recurrence hotspots. |
| contracts/schemas/review_eval_generation_report.schema.json | CREATE | Observability artifact contract for review-derived eval generation metrics. |
| contracts/examples/prompt_queue_review_trigger.json | MODIFY | Keep trigger example valid with governed review request payload. |
| contracts/examples/review_control_signal.json | MODIFY | Keep review control signal example valid with tightened contract. |
| contracts/examples/review_request.json | CREATE | Golden-path typed review request example. |
| contracts/examples/review_failure_summary.json | CREATE | Golden-path observability example. |
| contracts/examples/review_hotspot_report.json | CREATE | Golden-path observability example. |
| contracts/examples/review_eval_generation_report.json | CREATE | Golden-path observability example. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and bump updated schema versions. |
| spectrum_systems/modules/prompt_queue/review_trigger_policy.py | MODIFY | Deterministic review type trigger policy and review request emission. |
| spectrum_systems/modules/runtime/review_signal_extractor.py | MODIFY | Support governed JSON review artifact ingestion and strict type validation. |
| spectrum_systems/modules/runtime/review_eval_bridge.py | MODIFY | Add deterministic review observability report generation and stronger canonicalization. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Required-review enforcement hardening and review pass/fail precedence guarantees. |
| spectrum_systems/modules/runtime/evaluation_auto_generation.py | MODIFY | Deterministic recurrence tracking + high-priority tagging for review failure→eval expansion. |
| docs/reviews/review_eval_hardening_report.md | CREATE | Required hardening report with findings, severity, and fix references. |
| docs/architecture/review_judgment_bridge_design.md | CREATE | Design-only review→judgment bridge specification. |
| docs/architecture/review_system_flow.md | CREATE | End-to-end review trigger→artifact→eval→control process flow documentation. |
| tests/test_prompt_queue_review_trigger.py | MODIFY | Expand trigger-policy tests for typed review classes. |
| tests/test_review_signal_extractor.py | MODIFY | Add governed review artifact extraction and taxonomy fail-closed tests. |
| tests/test_review_eval_bridge.py | MODIFY | Verify deterministic observability report outputs and canonical ordering. |
| tests/test_evaluation_control.py | MODIFY | Add required-review gating and precedence tests. |
| tests/test_evaluation_auto_generation.py | MODIFY | Add recurrence threshold/high-priority deterministic expansion tests. |
| tests/test_review_trigger_policy.py | CREATE | Dedicated typed review trigger policy tests required by batch. |
| tests/test_review_required_gating.py | CREATE | Dedicated required-review block behavior tests required by batch. |

## Contracts touched
- NEW: `review_request` (1.0.0)
- UPDATED: `prompt_queue_review_trigger` (1.1.0)
- UPDATED: `review_control_signal` (1.1.0)
- NEW: `review_failure_summary` (1.0.0)
- NEW: `review_hotspot_report` (1.0.0)
- NEW: `review_eval_generation_report` (1.0.0)
- Standards manifest version bump and contract registry updates.

## Invariants to preserve
- Control authority remains single-path (`evaluation_control_decision` is final authority).
- Review artifacts inform eval/control but never directly allow/block runtime execution.
- Fail-closed behavior for malformed, missing, or ambiguous review artifacts/signals.
- Deterministic IDs, canonical JSON hashing, stable ordering for dedupe keys and summaries.
- No ad hoc parallel review path outside governed artifacts/contracts.

## Risks
- Schema tightening can break existing fixtures/examples if not migrated in lockstep.
- Added review-type enums may reject legacy freeform review types.
- Required-review enforcement can increase block frequency if integration points omit review payloads.
- Manifest update errors can break contract enforcement script.

## Acceptance criteria
- Typed review request emitted deterministically with one of required review types.
- Required-review missing/unsatisfied states produce block/deny (never warn/allow).
- Review FAIL blocks when required; review PASS does not override existing stronger blocks.
- Review-failure derived eval case generation supports deterministic recurrence + dedupe and high-priority threshold tagging.
- New observability artifacts validate against strict schemas with deterministic outputs.
- Hardening and architecture docs describe review->eval/control flow and judgment bridge (design only).

## Test plan
1. `pytest tests/test_review_signal_extractor.py`
2. `pytest tests/test_review_eval_bridge.py`
3. `pytest tests/test_evaluation_control.py`
4. `pytest tests/test_evaluation_auto_generation.py`
5. `pytest tests/test_review_trigger_policy.py`
6. `pytest tests/test_review_required_gating.py`
7. `pytest tests/test_contracts.py`
8. `pytest tests/test_contract_enforcement.py`
9. `python scripts/run_contract_enforcement.py`

## Non-goals
- No implementation of judgment decision execution logic in control path.
- No direct Claude review authorization behavior.
- No new repository/module split for review subsystem.
- No heuristic or non-deterministic trigger selection.

## Dependencies
- Existing review trigger, review parser, review eval bridge, and evaluation control modules on `main`.
- Existing contract loader and contract enforcement pipeline.
