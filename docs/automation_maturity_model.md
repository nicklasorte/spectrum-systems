# Automation Maturity Model

This model describes the progression from fully manual work to governed, AI-assisted, and eventually adaptive operations. It is distinct from the ecosystem-level Level 0-20 maturity ladder (`docs/system-maturity-model.md`), which tracks governed capability and platform development. This model tracks the operational automation posture of individual workflows and systems.

---

## The Six Levels

### Level 1 — Manual

**Description**: Work is performed by hand each time. No scripts, no structured outputs, no repeatable process.

**Characteristics**:
- Outputs are ad hoc documents or informal notes
- No schema constraints on inputs or outputs
- No evaluation of output quality
- Knowledge and methods exist only in the practitioner's memory

**Example**: Meeting notes written in a personal document after each session; action items tracked in email threads.

---

### Level 2 — Scripted

**Description**: Common steps are scripted to reduce manual effort, but the scripts are informal, not governed, and not composable.

**Characteristics**:
- Scripts exist but are not versioned, tested, or maintained as governed artifacts
- Outputs may still be unstructured or inconsistently formatted
- Failures may be silent; no validation of output quality
- Scripts are personal tools, not team-owned systems

**Example**: A Python script that extracts named participants from a transcript, but with no schema for its output and no test coverage.

---

### Level 3 — Automated

**Description**: The workflow runs reliably without manual intervention. Inputs, outputs, and steps are defined. Failures are explicit.

**Characteristics**:
- Inputs and outputs are schema-defined
- Steps are sequenced and documented
- Failures produce clear error signals rather than silent bad outputs
- The workflow can be re-run by anyone with access to the inputs

**Example**: A pipeline that ingests a transcript, runs extraction, and writes a structured output file — with schema validation at each boundary.

---

### Level 4 — Governed

**Description**: Automated workflows operate under explicit contracts, versioning, provenance, and evaluation standards. Governance compliance is enforced.

**Characteristics**:
- Inputs and outputs conform to versioned artifact contracts
- Provenance metadata is attached to every artifact
- CI enforces contract conformance, schema validation, and evaluation gates
- Changes to prompts, schemas, or workflows require versioning and evidence re-runs
- The human review checkpoint is explicit and tracked

**Example**: The meeting-minutes engine (SYS-006) at current MVP maturity — schema-conformant outputs, evidence bundles, CI-enforced validation, human review gate before operational record entry.

**This is the current target level for the meeting-minutes MVP.** The workflow is in transition from Level 3 to Level 4: the governance artifacts, contracts, and CI gates are defined, and formal SLI tracking is the remaining gap for full Level 4 qualification.

---

### Level 5 — AI-Assisted

**Description**: AI generates structured artifacts within governed boundaries. Humans review, accept, or override. The AI's role is bounded and auditable.

**Characteristics**:
- AI produces schema-conformant artifacts from governed inputs
- Prompt versions are managed, evaluated, and promoted through evidence gates
- Human overrides are logged and feed back into improvement cycles
- Recommendation quality is measured and tracked against SLOs
- Error budgets govern when AI-assisted expansion pauses for hardening

**Example**: A mature meeting-minutes engine where extraction quality is measured per-run, overrides are logged, and prompt improvements are evidence-driven — not ad hoc.

**The meeting-minutes MVP is on the path to this level. Current state is between Levels 3 and 4.**

---

### Level 6 — Adaptive / Self-Healing

**Description**: The system detects and responds to quality degradation, failure patterns, and changing conditions without requiring human-initiated remediation for routine deviations.

**Characteristics**:
- Quality signals are monitored continuously
- The system can flag and route failing artifacts for remediation without manual triage
- Prompt or configuration adjustments can be proposed by the system and confirmed by a human operator
- Cross-workflow learning improves components based on signals from related workflows
- Human oversight is at the policy level, not the per-artifact level

**This level is target state. It is not operational in the current ecosystem. See below.**

---

## What Level 6 Means Here

Level 6 is not magic. It does not mean the system runs without human oversight. It means the system's routine quality management is reliable enough that human attention is reserved for exceptions, policy changes, and novel situations — not for shepherding every run.

Concretely, Level 6 in this ecosystem means:

- **Quality monitoring is automated**: Rolling SLI values are computed and surfaced without manual log review
- **Budget exhaustion triggers automated work items**: When an SLO budget is consumed, a governed work item is automatically created and routed — no human needs to notice the failure and manually create the ticket
- **Prompt improvement proposals are generated from override signals**: When reviewers consistently override the same extraction pattern, the system surfaces a prompt improvement candidate for human review and acceptance
- **Fixture regression sets expand automatically**: New failure patterns detected in production automatically generate fixture candidates for the eval harness (with human review before acceptance)
- **Cross-workflow signal sharing is operational**: A pattern learned in the meeting-minutes workflow (e.g., a recurring action-item attribution problem) can inform prompt constraints in related workflows

Level 6 does **not** mean:
- The system deploys prompt changes autonomously
- Artifacts enter the operational record without human sign-off
- Governance rules are relaxed because the system is "smart enough"

---

## Advancement Criteria

| From → To | Gate Requirements |
|---|---|
| Level 1 → 2 | At least one repeatable script exists; outputs are consistent enough to build on |
| Level 2 → 3 | Inputs and outputs are schema-defined; failures are explicit; anyone with inputs can run the workflow |
| Level 3 → 4 | Artifact contracts defined and versioned; provenance attached; CI validates contracts; human review checkpoint explicit and enforced |
| Level 4 → 5 | AI extraction is in production; prompt versions are managed and evaluated; quality is measured per-run; override logging is operational |
| Level 5 → 6 | Quality monitoring is automated; budget exhaustion triggers governed responses without manual initiation; cross-workflow learning mechanism operational |

Promotion across any level boundary requires evidence recorded in the maturity tracker (`ecosystem/maturity-tracker.json`). Claims without evidence are rejected.

---

## Current Ecosystem Placement

| System | Current Level | Notes |
|---|---|---|
| meeting-minutes-engine (SYS-006) | ~3-4 | First end-to-end governed workflow; CI validation in place; human review gate defined; formal SLI tracking not yet operational |
| working-paper-review-engine | ~3-4 | Review artifacts under contract; evaluation evolving |
| spectrum-pipeline-engine | ~3 | Orchestration operational; full governance instrumentation in progress |
| spectrum-program-advisor | ~3 | Advisory outputs defined; quality measurement nascent |
| spectrum-systems (this repo) | ~4 | Governance contracts and schemas well-defined; CI enforcement active |

These placements are honest estimates, not claims of completion. The maturity tracker records evidence and gaps per system.

---

## First Proof Point: Meeting Minutes Flow

The meeting-minutes workflow is the anchor for proving this maturity model works in practice. The path from Level 1 (manual notes) to Level 4 (governed AI extraction with CI enforcement) is documented in `docs/toil_elimination_framework.md` and the meeting-minutes system interface. Achieving stable Level 4 operation — with consistent SLI measurement and a clean error budget record — is the prerequisite before any workflow targets Level 5.
