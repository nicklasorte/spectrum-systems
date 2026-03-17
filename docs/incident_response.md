# Operational Incident Response Framework

An incident in this ecosystem is any event that materially degrades the reliability, correctness, or governance integrity of a governed workflow or its outputs. This document defines what constitutes an incident, how to classify and respond to it, and what postmortem expectations apply.

The framework is blameless and system-oriented. The goal is to understand what failed and why, fix it durably, and prevent recurrence — not to assign personal fault.

---

## What Constitutes an Incident

### Category 1: Broken Pipeline
A governed workflow cannot complete execution. Ingestion, transformation, or packaging steps fail and do not produce an output artifact.

**Examples**:
- The meeting-minutes engine fails to parse a conformant input and exits without output
- A required dependency (schema file, prompt version, context document) is missing at run time
- The pipeline engine cannot route a completed artifact to the next stage

### Category 2: Invalid Output
A workflow completes but the output artifact is malformed, fails schema validation, or is structurally incomplete in a way that would cause downstream consumers to fail or produce incorrect results.

**Examples**:
- A `meeting_minutes` artifact is produced with an `action_items` field typed as a string instead of an array
- Required fields are absent from the output artifact
- The evidence bundle is emitted with mismatched `run_id` values across files

### Category 3: Governance Violation
A workflow, artifact, or process step violates a governing rule, contract constraint, or policy boundary.

**Examples**:
- An output artifact is published to the operational record without passing through the required human review checkpoint
- A prompt version is promoted without re-running the evaluation harness
- An artifact envelope references a deprecated contract version

### Category 4: Contract Drift
A contract, schema, or interface has changed in a way that breaks compatibility with dependent systems, without following the versioning and deprecation rules in `CONTRACT_VERSIONING.md`.

**Examples**:
- A required field is removed from a schema without a version bump
- A downstream engine is broken because an upstream contract changed without notice
- The standards manifest (`contracts/standards-manifest.json`) is out of sync with the live schema files

### Category 5: Materially Wrong Structured Extraction
A workflow completes and produces a schema-valid artifact, but the extracted content is materially incorrect relative to the source material in a way that would mislead downstream consumers or human reviewers.

**Examples**:
- Action items are attributed to the wrong owner across the entire artifact
- A decision that was explicitly made in the meeting is absent from the `decisions` array
- Risk items are extracted from the wrong document section and reflect a prior meeting's content

---

## Severity Levels

| Severity | Criteria | Response Time |
|---|---|---|
| **SEV-1** | Complete workflow failure; no output produced; governance violation blocking downstream operations | Immediate — within the current working session |
| **SEV-2** | Malformed or schema-invalid output; contract drift affecting a dependent system; material extraction error discovered before artifact is accepted | Same day |
| **SEV-3** | Incomplete output (some required fields missing) but core artifact is usable; extraction quality miss found during review; isolated governance warning | Within the current sprint |
| **SEV-4** | Minor field-level gap; non-blocking warning in validation output; documentation drift | Tracked as a work item; resolved in normal backlog flow |

---

## Triage Flow

1. **Detect**: Incident is surfaced via CI validation failure, human review finding, or governance scan
2. **Classify**: Assign a severity level and incident category using the definitions above
3. **Contain**: Stop the affected workflow from producing further invalid outputs; quarantine any invalid artifacts already produced
4. **Notify**: Record the incident in `governance/work-items/` with the affected system, failure category, severity, and initial description
5. **Investigate**: Identify root cause — was it a prompt change, schema change, missing input, contract drift, or engine logic?
6. **Remediate**: Apply a targeted fix; do not apply broad changes that obscure the root cause
7. **Verify**: Re-run the affected workflow on a fixture that triggers the failure; confirm the fix resolves it
8. **Postmortem**: Write a postmortem (see below) for SEV-1 and SEV-2 incidents

---

## Containment Rules

- **Invalid artifacts are not accepted** into the operational record. If an invalid artifact has already been accepted, it must be retracted and the downstream record updated.
- **Broken pipelines halt execution** until the root cause is resolved. Do not patch around a broken step without understanding why it broke.
- **Governance violations require explicit resolution**, not just a fix of the symptom. If a review checkpoint was bypassed, the artifact must go back through the checkpoint — even if its content is correct.

---

## Remediation Expectations

| Incident Category | Remediation Standard |
|---|---|
| Broken pipeline | Root cause identified; fix deployed; re-run on failing input confirms resolution; fixture added to prevent regression |
| Invalid output | Schema or prompt fix applied; fixture added for the failing case; schema validation added to CI if not already present |
| Governance violation | Process gap identified and documented; governance rule or check updated to prevent recurrence |
| Contract drift | Contract versioned correctly; dependents updated; `standards-manifest.json` updated; `CONTRACT_VERSIONING.md` followed |
| Material extraction error | Prompt or rule updated; fixture added for the failure pattern; evaluation re-run confirms improvement; human reviewer sign-off on fix |

---

## Postmortem Expectations

Postmortems are required for SEV-1 and SEV-2 incidents. They are written to capture:

1. **Summary**: What failed, when it was detected, and what the impact was
2. **Timeline**: Key events from failure onset to resolution
3. **Root cause**: What actually caused the failure — not the symptom, the cause
4. **Contributing factors**: What made the failure possible (missing validation, unclear contract, untested prompt change)
5. **Action items**: Specific, trackable changes to prevent recurrence — with owners and target dates
6. **What went well**: Detection, response, or containment steps that worked as intended

Postmortems are filed in `governance/work-items/` or a designated incident log. They are not confidential and should be shared with the team.

---

## Example Incident: Meeting Minutes Extraction Failure

**System**: meeting-minutes-engine (SYS-006)  
**Category**: Materially Wrong Structured Extraction (Category 5)  
**Severity**: SEV-2

**What happened**: A new prompt version was promoted to the meeting-minutes engine without re-running the evaluation fixture set. The first production run on a real transcript produced a valid schema artifact, but the `action_items` array was empty — the updated prompt had inadvertently dropped the action-item extraction instruction. The human reviewer caught the omission during the review checkpoint.

**Containment**: The artifact was withheld from the operational record. The engine was reverted to the previous prompt version.

**Root cause**: Prompt promotion was not gated on re-running the fixture set. The CI check validated schema structure but not extraction quality against known-good fixtures.

**Remediation**:
1. Added a CI gate requiring fixture-set re-run before any prompt version promotion
2. Added a fixture specifically covering meetings with explicit action-item discussions
3. Updated `docs/sre_principles.md` to note extraction quality as a distinct SLI from schema validation

**Postmortem filed**: Yes — in `governance/work-items/incident-YYYY-MM-DD-description.md` (use this naming pattern; placeholder only)

---

## Relationship to Other Policies

- **Error budgets**: Hard-gate failures (malformed artifacts, contract non-compliance) are always SEV-1 or SEV-2 incidents. See `docs/error_budget_policy.md`.
- **Reliability principles**: Incident categories map directly to the reliability dimensions in `docs/sre_principles.md`.
- **Governance conformance**: Governance violations may also require compliance scan updates. See `docs/governance-conformance-checklist.md`.
