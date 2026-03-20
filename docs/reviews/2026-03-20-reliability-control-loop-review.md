# Reliability Control Loop Architecture Review

## 1. Review Metadata

| Field | Value |
|---|---|
| Review Date | 2026-03-20 |
| Repository | spectrum-systems |
| Reviewer / Agent | Claude (Principal Systems Architect — Sonnet 4.6) |
| Review ID | 2026-03-20-reliability-control-loop-review |
| Prior Review | None (first targeted review of this subsystem) |
| Inputs Consulted | `spectrum_systems/modules/runtime/trace_store.py`, `replay_engine.py`, `replay_decision_engine.py`, `evaluation_monitor.py`, `evaluation_budget_governor.py`, `evaluation_enforcement_bridge.py`; CLI scripts `run_evaluation_budget_governor.py`, `run_replay_decision_analysis.py`; schemas `evaluation_budget_decision.schema.json`, `evaluation_enforcement_action.schema.json`, `evaluation_monitor_record.schema.json`, `evaluation_monitor_summary.schema.json` |

---

## 2. Scope

**In-bounds:**
- BN–BP: Trace persistence (`trace_store.py`) and replay plane (`replay_engine.py`)
- BQ: Replay Decision Integrity Engine (`replay_decision_engine.py`)
- BS: Continuous Evaluation Monitor (`evaluation_monitor.py`)
- BT: Evaluation Budget Governor (`evaluation_budget_governor.py`)
- BU: Governor Enforcement Bridge (`evaluation_enforcement_bridge.py`)
- Associated CLI scripts and JSON Schema contracts

**Review questions addressed:** Control-loop ID linkage; fail-closed behavior; semantic consistency; enforcement strength; override/bypass risk; BT policy soundness; overall architecture verdict.

**Out-of-bounds:** Upstream SLO enforcement engine (BK–BM); downstream workflow consumers of enforcement actions; regression harness; CI/CD integration; implementation repos.

---

## 3. Executive Summary

- The control loop is architecturally coherent end-to-end and uses schema-governed artifacts at every stage — this is a strong foundation.
- BN–BU correctly implement fail-closed error handling in almost all paths, with one material exception in BQ's replay-to-decision mapping.
- **One critical override risk exists:** BU's `require_review` gate is bypassed by any truthy value in `context["override_artifact"]` — there is no governed override artifact schema, no required fields, and no audit logging of the override content. This is a structural security gap.
- The BQ replay plane and the BS→BT→BU evaluation pipeline are architecturally isolated: BQ's reproducibility scores and `analysis_id`s are never consumed downstream, making them observational rather than controlling.
- BS's `recommended_action` field is computed by the monitor but never read by BT; this dead-end signal wastes schema surface area and could mislead operators.
- BU has no standalone CLI script, preventing pipeline integration without a custom wrapper.
- The pipeline must not expand before the override artifact governance gap and the BQ→BS integration gap are resolved.

---

## 4. Maturity Assessment

**Current maturity: Level 3 (Governed — partial)**

Evidence of Level 3 maturity:
- All artifacts are schema-validated with `additionalProperties: false` (Draft 2020-12).
- Deterministic multi-signal policy logic in BT.
- Fail-closed error handling at module boundaries.
- Atomic writes in BN; trace_id threaded through BQ.
- Explicit audit trail: `triggered_thresholds` and `reasons` in every decision artifact.

Unmet criteria blocking Level 4 (Enforced):
- No governed override artifact schema — override gate is unenforced.
- No CLI for BU — the enforcement bridge cannot be run as a governed pipeline step.
- BQ outputs are not consumed by BS/BT/BU — reproducibility signal is not controlling.
- Exit-code ambiguity in BT's CLI conflates `require_review` with `allow_with_warning`.
- BT does not record the threshold values used in the decision artifact — custom thresholds are not auditable.

---

## 5. Strengths

**S-1: Schema-governed artifacts throughout.** Every artifact (trace envelope, replay result, monitor record, monitor summary, budget decision, enforcement action) is validated against a JSON Schema contract before return. `additionalProperties: false` prevents field injection across all schemas.

**S-2: Fail-closed error handling in BS, BT, and BU.** Invalid inputs raise typed exceptions rather than silently returning partial results. Schema validation failures propagate to callers as hard errors.

**S-3: BT multi-signal policy is genuine.** `evaluate_budget_status` combines five independent signal categories (drift rate, failure rate, burn rate, trend direction, critical alert count). Blocked status requires two signals together (e.g., critical_alerts AND critical_failure_rate), preventing single-signal false positives.

**S-4: `freeze_changes` and `block_release` are unconditionally enforced.** In BU's `_resolve_allow_to_proceed`, blocking responses always return `False` with no override path. This is correct and strong for the highest-severity states.

**S-5: `unknown system_response` is fail-closed in BT and BU.** BT's `determine_system_response` maps unknown statuses to `block_release`. BU's `_resolve_allow_to_proceed` maps unknown responses to `False`.

**S-6: Atomic writes in BN.** The `_atomic_write` helper uses `tempfile.mkstemp` + `os.replace` to prevent partial trace files from being observable by readers.

**S-7: `triggered_thresholds` and `reasons` provide per-decision auditability.** Every budget decision artifact records which named thresholds fired and human-readable explanations including actual metric values.

**S-8: BU double-validates the decision artifact.** `enforce_budget_decision` re-validates the `evaluation_budget_decision` against its schema before enforcement — ensuring schema integrity even when called programmatically outside `run_enforcement_bridge`.

---

## 6. Structural Gaps

**SG-1: BQ is an isolated observation plane — its outputs are not consumed by BS, BT, or BU.**
The replay decision analysis artifacts (`analysis_id`, `replay_result_id`, reproducibility score) are not carried into `evaluation_monitor_record` or `evaluation_monitor_summary`. The BQ→BS integration is architecturally absent. Reproducibility is measured but never governs the budget.

**SG-2: BS's `recommended_action` is a dead-end signal.**
The `summarize_monitor_records` function computes `recommended_action` (values: `rollback_candidate`, `freeze_changes`, `watch`, `none`) and includes it in the summary schema. BT does not read it. It is computed but silently discarded. `rollback_candidate` has no counterpart in any downstream artifact.

**SG-3: BU has no standalone CLI script.**
`run_enforcement_bridge.py` does not exist. The BU enforcement bridge cannot be executed as a governed pipeline step. Any operational use requires an undocumented custom wrapper.

**SG-4: No governed override artifact schema.**
The `require_review` gate in BU accepts any truthy value in `context["override_artifact"]`. There is no schema for what a valid override artifact must contain. No required fields (approver identity, timestamp, decision_id reference, expiry). No audit logging of the override content or who provided it.

**SG-5: BT decision artifact does not record threshold values.**
When custom thresholds are passed to `run_budget_governor`, the resulting `evaluation_budget_decision` records only threshold names (e.g., `"drift_rate_warning"`) but not the actual numeric values used. Custom threshold configurations are not auditable from the artifact alone.

**SG-6: `trace_id`s are not propagated from regression runs into monitor records.**
`evaluation_monitor_record` carries `source_run_id` and `source_suite_id` but not the individual trace IDs evaluated in that run. Traceability from a budget decision back to specific traces requires out-of-band lookup.

---

## 7. Risk Areas

**R-1 [Critical]: Override is presence-based, not validation-based (BU).**
`_resolve_allow_to_proceed` in `evaluation_enforcement_bridge.py` checks `context.get("override_artifact")` for truthiness only. Passing `{"override_artifact": True}`, `{"override_artifact": {"arbitrary": "data"}}`, or any dict with that key bypasses the `require_review` enforcement gate. No validation is performed on the override content. This means the gate is effectively a single-layer check with no governance. Any caller who constructs the context dict can bypass it.

*Severity: Critical. Likelihood: Moderate (requires knowing the key name, but the key name is a visible module constant).*

**R-2 [High]: BQ fail-open defaults on unknown/missing replay statuses.**
In `recompute_decision_from_replay` (`replay_decision_engine.py`):
- Line 334: `status_map.get(step_status, "allow")` — unknown step statuses default to `allow`.
- Line 350: `overall_status_map.get(status or "", "allow")` — unknown or None overall replay status defaults to `allow`.

An unexpected status value (e.g., from a new replay engine version, a corrupted artifact, or an injected field) silently produces `allow`, masking the deviation. This should default to `fail` or raise.

*Severity: High. Likelihood: Low-moderate (triggered by version mismatch or artifact corruption).*

**R-3 [High]: BT CLI conflates `require_review` and `allow_with_warning` at exit code level.**
Both responses return exit code 1 (`EXIT_CAUTION`) in `run_evaluation_budget_governor.py`. In CI/CD pipelines that gate on exit codes, `require_review` (which means `allowed_to_proceed=False` in BU) is treated identically to `allow_with_warning` (which means `allowed_to_proceed=True`). A pipeline that checks only exit code 1 without reading the artifact will proceed when it should halt.

*Severity: High. Likelihood: High (exit codes are the natural CI/CD integration point).*

**R-4 [Medium]: BS `recommended_action` semantic ambiguity.**
BS emits `freeze_changes` as a `recommended_action`, and BT independently emits `freeze_changes` as a `system_response`. These are computed from overlapping but distinct logic paths. If downstream consumers read the summary's `recommended_action` (expecting BT-governed enforcement) rather than the actual enforcement action from BU, they may act on an ungoverned recommendation. The co-existence of two `freeze_changes` signals with different authority levels is a semantic hazard.

*Severity: Medium. Likelihood: Low (requires consumer confusion), but consequence is acting on wrong authority.*

**R-5 [Medium]: BQ `CONSISTENCY_INDETERMINATE` produces score 0.5 — operationally ambiguous.**
When comparison is indeterminate (e.g., missing enforcement data in replay), the reproducibility score is 0.5. This is neither clearly healthy nor clearly failing, and there is no policy threshold that triggers on indeterminate outcomes. An operator monitoring reproducibility scores would see 0.5 and have no governed response. This gap grows when BQ is eventually integrated with BS.

*Severity: Medium. Likelihood: Medium (indeterminate outcomes are expected at low frequency).*

**R-6 [Low]: BU context dict is untyped and unvalidated.**
The `context` parameter in `enforce_budget_decision` and `run_enforcement_bridge` accepts any dict. Malformed or injected context fields (beyond `enforcement_scope` and `override_artifact`) are silently ignored. While this does not currently create exploitable paths, it weakens the governed contract around BU's interface.

---

## 8. Recommendations

**REC-1 [Critical] — Introduce a governed `override_artifact` schema and validation in BU.**
Define an `override_artifact.schema.json` with required fields: `override_id`, `decision_id` (must match the decision being overridden), `approved_by`, `approved_at`, `justification`, `expiry_at`. Replace the presence check in `_resolve_allow_to_proceed` with schema validation, decision_id match verification, and expiry check. Log the override artifact content at INFO level.
- *Related gap: SG-4*
- *Expected outcome: Override gate becomes governance-enforced rather than presence-based.*

**REC-2 [Critical] — Change BQ fail-open defaults to fail-closed.**
In `recompute_decision_from_replay`, replace `status_map.get(step_status, "allow")` and `overall_status_map.get(status or "", "allow")` with `status_map.get(step_status, "fail")` and `raise ReplayDecisionError(...)` for unknown overall status. Unknown states must never resolve to `allow`.
- *Related risk: R-2*
- *Expected outcome: BQ raises on unexpected input rather than producing a misleading allow decision.*

**REC-3 [Critical] — Create `run_enforcement_bridge.py` CLI.**
BU is the terminal enforcement gate in the pipeline. Without a CLI, it cannot be integrated into any governed pipeline step. The CLI should accept `--input <decision.json>`, optionally `--override-artifact <override.json>`, `--enforcement-scope <scope>`, and `--output-dir`. Exit codes should be: 0 = allowed, 1 = blocked (all blocking responses), 2 = error/failure.
- *Related gap: SG-3*
- *Expected outcome: BU is operationally executable as a pipeline step.*

**REC-4 [High] — Assign `require_review` its own exit code in BT CLI.**
Separate `require_review` from `allow_with_warning` in the BT CLI exit code table. Proposed: 0 = allow, 1 = allow_with_warning, 2 = require_review or freeze/block, 3 = hard error. This ensures CI/CD pipelines can distinguish advisory warnings from enforced halts without artifact inspection.
- *Related risk: R-3*
- *Expected outcome: CI/CD pipelines halt correctly on `require_review` without requiring artifact parsing.*

**REC-5 [High] — Integrate BQ reproducibility scores into BS monitor records.**
The `build_monitor_record` function should accept an optional `replay_analysis` dict carrying `reproducibility_score` and `drift_type` from the corresponding BQ artifact. When present, surface these in `sli_snapshot` and factor the reproducibility trend into `compute_alert_recommendation`. This closes the BQ→BS architectural gap.
- *Related gap: SG-1*
- *Expected outcome: Reproducibility becomes a governing SLI, not just an observation.*

**REC-6 [Medium] — Record active threshold values in the budget decision artifact.**
Add an optional `applied_thresholds` field to `evaluation_budget_decision.schema.json` (a dict of threshold name → value). BT should populate this when thresholds are non-default. This makes custom threshold configurations auditable from the artifact alone.
- *Related gap: SG-5*
- *Expected outcome: Every decision is reproducible and auditable from the artifact without external configuration context.*

**REC-7 [Medium] — Retire or govern BS `recommended_action`.**
Either (a) remove `recommended_action` from `evaluation_monitor_summary` schema and BS logic since BT governs the authoritative response, or (b) rename it `monitor_signal` and add a schema annotation clarifying it is non-authoritative. Document explicitly that BT's `system_response` is the only governing field. Prevent consumer confusion about authority levels.
- *Related risk: R-4, gap SG-2*
- *Expected outcome: No two ungoverned fields with overlapping vocabulary exist in the pipeline.*

---

## 9. Priority Classification

| ID | Finding | Priority | Rationale |
|---|---|---|---|
| R-1 / SG-4 | Override is presence-based — no governed override schema | **Critical** | Direct security bypass of the require_review gate |
| R-2 | BQ fail-open defaults on unknown status | **Critical** | Masks replay failures with false allow signal |
| SG-3 | No BU CLI script | **Critical** | BU cannot be run as a pipeline step — pipeline is incomplete |
| R-3 | BT CLI conflates require_review with allow_with_warning | **High** | CI/CD pipelines will pass when they should halt |
| SG-1 | BQ not integrated with BS | **High** | Reproducibility is unmeasured in governance chain |
| SG-5 | Threshold values not recorded in budget decision | **Medium** | Custom threshold configurations are not auditable |
| R-4 / SG-2 | BS `recommended_action` is a dead-end signal | **Medium** | Semantic hazard; consumer confusion risk |
| R-5 | INDETERMINATE score (0.5) has no policy response | **Medium** | Gap in BQ→BS policy coverage |
| R-6 | BU context dict untyped | **Low** | Interface weakness; no current exploit path |
| SG-6 | Trace IDs not propagated into monitor records | **Low** | Traceability gap; addressed by BQ integration |

---

## 10. Extracted Action Items

**A-1 [Critical]** — Define `override_artifact.schema.json` with required governance fields (`override_id`, `decision_id`, `approved_by`, `approved_at`, `justification`, `expiry_at`). Owner: governance repo (spectrum-systems). Artifact: `contracts/schemas/override_artifact.schema.json`. Acceptance: Schema added, validated by Draft 2020-12, referenced in BU documentation.

**A-2 [Critical]** — Update `_resolve_allow_to_proceed` in BU to validate the override artifact against the schema, verify `decision_id` matches the active decision, check `expiry_at`, and log the artifact at INFO. Owner: implementation repo. Artifact: Updated `evaluation_enforcement_bridge.py` + tests. Acceptance: Presence-only check removed; invalid override artifact raises `EnforcementBridgeError`; valid override is logged with artifact content.

**A-3 [Critical]** — Fix BQ fail-open defaults: replace `"allow"` fallbacks for unknown statuses with `"fail"` or raise `ReplayDecisionError`. Owner: implementation repo. Artifact: Updated `replay_decision_engine.py` + tests for unknown status paths. Acceptance: Unknown step status and unknown overall status raise rather than silently returning `allow`.

**A-4 [Critical]** — Create `scripts/run_enforcement_bridge.py` CLI for BU. Owner: implementation repo. Artifact: `scripts/run_enforcement_bridge.py`. Acceptance: CLI accepts `--input`, `--override-artifact`, `--enforcement-scope`, `--output-dir`; exit 0 = allowed, exit 1 = blocked, exit 2 = error; output written to `--output-dir`.

**A-5 [High]** — Separate `require_review` exit code in BT CLI. Assign exit 2 to `require_review` and `freeze_changes`/`block_release`; reserve exit 1 for `allow_with_warning` only. Owner: implementation repo. Artifact: Updated `run_evaluation_budget_governor.py` + updated docstring/exit code table. Acceptance: `require_review` returns exit ≥ 2; CI/CD pipelines halt on `require_review`.

**A-6 [High]** — Define the BQ→BS integration contract: extend `evaluation_monitor_record.schema.json` with an optional `replay_analysis_summary` field (`reproducibility_score`, `drift_type`, `analysis_id`). Owner: governance repo (spectrum-systems). Artifact: Updated `evaluation_monitor_record.schema.json`. Acceptance: Schema updated; `build_monitor_record` accepts optional replay analysis and surfaces reproducibility in `sli_snapshot`.

**A-7 [Medium]** — Add optional `applied_thresholds` field to `evaluation_budget_decision.schema.json`. Owner: governance repo. Artifact: Updated schema. Acceptance: Schema updated; BT populates field when thresholds are non-default; field passes schema validation.

**A-8 [Medium]** — Resolve BS `recommended_action` semantic ambiguity: either remove from schema or rename to `monitor_signal` with non-authority annotation. Owner: governance repo. Artifact: Updated `evaluation_monitor_summary.schema.json` + BS documentation. Acceptance: No field with `freeze_changes` vocabulary exists at advisory level without clear authority labeling.

---

## 11. Blocking Items

- **A-1 and A-2 block pipeline expansion.** The pipeline must not be extended to production-grade gating workflows until the override artifact is governed. Any new `require_review` trigger path added before A-2 is deployed creates an unvalidated bypass route.
- **A-4 (BU CLI) blocks operational readiness.** The enforcement bridge cannot be invoked as a pipeline step until a CLI exists. Any pipeline wiring that skips BU is missing the terminal enforcement gate.
- **A-3 (BQ fail-open fix) blocks BQ integration into BS.** Integrating BQ into the monitoring chain while fail-open defaults exist would propagate misleading `allow` signals into budget decisions.

---

## 12. Deferred Items

- **BQ→BS integration implementation (A-6 schema + code):** Deferred until A-3 (fail-open fix) is complete. Trigger: A-3 merged and tests passing.
- **BQ `INDETERMINATE` policy threshold (R-5):** Deferred until BQ is integrated into BS. At that point, a threshold on indeterminate rate should be added to BS and BT. Trigger: BQ→BS integration complete.
- **BU context dict typing and validation (R-6):** Deferred; low severity. Trigger: next scheduled governance review of BU interface contracts, or when first external consumer of BU context is documented.

---

## Suggested Next Prompt

> Review and finalize the `override_artifact` governance contract design: define the required fields for a governed override artifact schema, specify the validation steps BU must perform (schema check, decision_id match, expiry enforcement, audit logging), and produce the schema file at `contracts/schemas/override_artifact.schema.json`. Also produce a companion ADR documenting why freeze_changes and block_release are permanently non-overridable while require_review permits governed override.
