# Toil Elimination Framework

Toil is repeated manual operational work that is automatable, produces no enduring structural value, and scales with volume rather than complexity. Eliminating toil is not about comfort — it is about redirecting expert time toward work that requires judgment, and about making governed workflows reliable enough to run without human shepherding.

---

## Definition of Toil in This Ecosystem

Toil in Spectrum Systems has the following properties:

- **Manual**: requires a human to initiate or execute each time
- **Repetitive**: the same steps recur across meetings, studies, reviews, or cycles
- **Automatable**: could be handled by a governed engine given well-defined inputs and outputs
- **Low enduring value**: the act of doing the work produces no lasting artifact beyond the immediate output; it does not build institutional memory or improve future decisions
- **Scales with volume**: as more meetings, papers, or reviews occur, the burden grows linearly unless the work is automated

Work that requires genuine expert judgment, novel synthesis, or governance accountability is **not toil** — it is high-value human work that should be protected, not eliminated.

---

## Categories of Toil

### Engineering Toil
- Manually reformatting outputs to match schema expectations
- Copying data between systems without provenance
- Re-running failed pipeline steps by hand without root-cause resolution
- Maintaining ad hoc scripts that duplicate governed workflow logic

### Analysis Toil
- Manually transcribing or summarizing meeting content
- Re-extracting action items from documents that have already been processed
- Repackaging simulation outputs into delivery formats by hand
- Re-reading prior decisions because no structured decision log exists

### Documentation Toil
- Writing boilerplate sections of meeting minutes that follow a fixed structure
- Re-generating status summaries from information already captured in structured form
- Manually syncing artifact status across registers and registries that should stay aligned automatically

### Coordination Toil
- Tracking action item ownership in unstructured threads rather than governed registers
- Manually routing review comments to the correct resolver
- Assembling readiness assessments from scattered notes rather than from governed artifact bundles

### Review Toil
- Re-checking schema conformance by hand when validation scripts exist
- Re-reading unstructured documents to extract decisions that should have been captured at creation time
- Manually escalating governance violations that CI should detect and flag

---

## Prioritization Rubric

Automation investment is prioritized using these criteria, evaluated in order:

| Criterion | Weight |
|---|---|
| **Recurrence frequency** — how often does this work occur? | High |
| **Volume scaling** — does burden grow linearly with activity volume? | High |
| **Error risk** — does manual execution introduce meaningful error rates? | High |
| **Blocking effect** — does the toil delay downstream work or governance gates? | Medium |
| **Expert time consumed** — does the work consume time better spent on judgment work? | Medium |
| **Automation readiness** — are inputs and outputs well-defined enough to govern now? | Determines feasibility |

Work that scores high on recurrence, volume scaling, and error risk — and where inputs and outputs are already schema-defined — is automated first.

Work that lacks defined schemas or contracts is blocked on design work, not implementation.

---

## Meeting Minutes Pipeline: From Manual Toil to Governed Automation

The meeting-minutes workflow (SYS-006) is the first concrete proof point of toil elimination in this ecosystem.

### Prior State (Manual Toil)
- A program participant manually listened to or re-read transcripts after each meeting
- Meeting notes were written in free-form prose with no consistent structure
- Action items were extracted informally and tracked in email threads or informal lists
- Decisions were rarely documented with rationale
- Follow-up coordination was ad hoc and frequently lost context

### Characteristics of Prior Toil
- Recurred after every meeting
- Scaled linearly with meeting frequency
- High error rate: actions missed, owners unassigned, decisions undocumented
- Blocked downstream work: advisors and reviewers lacked reliable operational signals
- Consumed expert time on transcription and reformatting rather than analysis

### Governed Automation (Current MVP)
The meeting-minutes engine replaces this pattern with a governed workflow:

1. **Observe**: Transcript, context, and roster are ingested as schema-validated inputs
2. **Interpret**: The engine extracts meeting facts, action items, decisions, risks, and metadata according to the `meeting_minutes` contract
3. **Recommend**: Structured follow-ups, ownership assignments, and operational signals are generated as governed, reviewable outputs

The output is a deterministic, schema-conformant artifact — not a free-form summary. It enters the artifact chain with provenance metadata and a `run_id`. Humans review and accept the output; they do not produce it from scratch.

### Residual Human Work (Intentional)
- Review of extracted action items for accuracy and completeness
- Acceptance or override of suggested ownership assignments
- Governance sign-off before minutes are published as authoritative

This is not toil. It is accountable human judgment applied to a governed AI-produced artifact.

---

## Automation Decision Gate

Before automating a toil category, these gates must be satisfied:

1. **Schema exists** — inputs and outputs are schema-defined in `schemas/` or `contracts/schemas/`
2. **Contract exists** — the output artifact type has a governing contract
3. **Evaluation plan exists** — there is a defined harness and fixture set to verify output quality
4. **Failure mode is documented** — `docs/system-failure-modes.md` or the system's interface doc records how failures surface
5. **Human review checkpoint is defined** — the boundary of AI authority and human review is explicit

If any gate is not satisfied, address the gap before implementing automation. Implementing automation against undefined contracts creates ungoverned toil of a different kind.
