# Error Budget Policy

Error budgets translate reliability targets into actionable investment decisions. When budgets are healthy, feature expansion and capability development proceed. When budgets are exhausted, hardening takes priority — no exceptions.

This policy applies to all governed workflows. The meeting-minutes MVP is used as the illustrative example throughout.

---

## Error Budget Concept

An error budget is the allowed failure margin before a workflow's reliability degradation demands prioritized remediation.

If an SLO is set at 98% schema validation pass rate over a rolling 30-run window, the error budget is the 2% failure allowance. Consuming that budget faster than expected means the system is less reliable than designed. Exhausting it triggers the response actions defined below.

Error budgets are not targets to hit — they are guardrails that convert abstract reliability goals into concrete prioritization signals.

---

## Failure Categories

### 1. Extraction Failures
A run completes but one or more required fields in the output artifact are absent, null, or flagged `extraction_incomplete`. The output does not fully represent the input material.

**Example**: Action items are present in the transcript but the `action_items` array in the minutes artifact is empty.

### 2. Missing Required Fields
The output artifact is structurally present but does not satisfy the contract's required field list. Distinct from extraction failures — this is a schema non-conformance, not an extraction quality issue.

**Example**: The `meeting_date` field is absent from a `meeting_minutes` artifact.

### 3. Malformed Artifacts
The output artifact fails JSON Schema validation. The artifact cannot be safely consumed by downstream systems.

**Example**: `action_items` is typed as a string instead of an array.

### 4. Recommendation Quality Misses
The recommended follow-ups, ownership assignments, or operational signals are materially incorrect or incomplete relative to the source material. This is evaluated by the human reviewer at the review checkpoint and logged as a quality event when material errors are found.

**Example**: The suggested owner for a critical action item is absent from the meeting participant list.

### 5. Contract Non-Compliance
The artifact envelope or payload does not conform to the governing contract version in force at the time of the run. This may occur due to prompt drift, schema changes without version bumps, or engine misconfiguration.

**Example**: A `meeting_minutes` artifact references a deprecated contract version with a removed required field.

---

## Budget Thresholds and Measurement Windows

Thresholds are set per workflow and reviewed at each maturity promotion. Default initial targets for the meeting-minutes MVP:

| Failure Category | SLO Target | Error Budget | Measurement Window |
|---|---|---|---|
| Extraction failures | ≤ 5% of runs | 5 failures per 100 runs | Rolling 30-run window |
| Missing required fields | ≤ 2% of runs | 2 failures per 100 runs | Rolling 30-run window |
| Malformed artifacts | 0% tolerance | Hard gate — any failure triggers immediate review | Per-run |
| Recommendation quality misses (material) | ≤ 10% of reviewed runs | 10 misses per 100 reviewed runs | Rolling 20-reviewed-run window |
| Contract non-compliance | 0% tolerance | Hard gate — any failure triggers immediate review | Per-run |

Hard gates (0% tolerance) are non-negotiable. Any occurrence is an incident, not a budget event.

---

## Budget Exhaustion: Response Actions

When an error budget for a non-zero-tolerance category is exhausted:

### Immediate Actions
1. **Pause feature expansion** for the affected workflow. No new capabilities are added until the budget is restored.
2. **Open a hardening work item** in `governance/work-items/` with the failure category, affected SLO, and observed failure rate.
3. **Notify the workflow owner** (or equivalent accountability holder).

### Short-Term Remediation (within the next active sprint)
1. **Add or update fixtures** in the workflow's eval harness to cover the failure pattern.
2. **Add or update validation tests** that detect the failure before it reaches production runs.
3. **Review the prompt version** associated with the failure window; determine if prompt changes caused the regression.
4. **Update the evaluation manifest** to record the failure pattern as a known risk until resolved.

### Re-Evaluation Gate
Before resuming feature expansion:
1. Run the full fixture set and confirm the failure rate returns within budget.
2. Record evidence in `evaluation_results.json` for the remediation run.
3. Update the maturity tracker with the remediation evidence.
4. If budget exhaustion was caused by a schema or contract issue, update the relevant schema/contract and log a versioning decision.

---

## MVP Budget Application: Meeting Minutes Workflow

The meeting-minutes workflow (SYS-006) is the first workflow subject to this policy. Since it is the primary proving ground for the operating model, reliability standards here set the benchmark for all subsequent workflows.

### Current Target State
- Schema validation pass rate: ≥ 98% per rolling 30-run window
- Required field coverage: ≥ 95% per run
- Evidence bundle completeness: 100% (hard gate)
- Contract conformance: 100% (hard gate)

### Current Actual State
The workflow is at MVP stage (maturity Level ~4-5). Formal budget tracking is not yet fully automated. Current practice:
- Schema validation is enforced by `scripts/validate_evaluation_contract.py` in CI
- Human reviewers log material quality misses informally during review
- Formal rolling-window budget tracking is a near-term target (see `docs/operational-ai-systems-roadmap.md`)

### Path to Formal Budget Tracking
1. Emit structured `evaluation_results.json` with per-field extraction coverage on every run
2. Accumulate run results in a governed store (data lake)
3. Compute rolling-window SLI values against defined SLO targets
4. Surface budget status in the governance dashboard (target state)

Until formal tracking is operational, human review at the output checkpoint serves as the primary quality signal. Material failures found during review are logged and drive hardening work.

---

## Relationship to Other Policies

- **Incident response**: Hard-gate failures (malformed artifacts, contract non-compliance) are incidents. See `docs/incident_response.md` for triage and postmortem expectations.
- **Automation maturity**: Exhausting error budgets is evidence that a system has not yet earned advancement on the maturity ladder. See `docs/automation_maturity_model.md`.
- **SLI/SLO definitions**: Measurement methodology follows `docs/sre_principles.md`.
