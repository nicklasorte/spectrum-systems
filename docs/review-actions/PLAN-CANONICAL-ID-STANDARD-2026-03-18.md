# Plan — Canonical ID Standard — 2026-03-18

## Prompt type
PLAN

## Roadmap item
Pre-M — Canonical ID Standard (prerequisite to Layer 2 module expansion)

---

## Current ID Landscape

### Summary

The repository uses typed, prefixed identifiers extensively across contracts and schemas, with a mostly consistent
convention of `PREFIX-[A-Z0-9._-]+` for artifact and entity IDs. However, meaningful inconsistencies
exist across naming, format patterns, and enforcement coverage that creates cross-artifact traceability risk.

### Identifier inventory by location

**`contracts/schemas/` — top-level artifact IDs (enforced with patterns)**

| Field | Pattern | Schemas that use it |
|---|---|---|
| `artifact_id` | Varies by type: `^ASMREG-`, `^DECLOG-`, `^PRV-`, `^SRA-`, `^MSPLAN-`, `^PB-`, `^STD-`, `^CRM-`, `^MMR-`, `^NBA-MEMO-`, `^EVAL-`, `^RISKREG-`; generic `^[A-Z0-9._-]+$` in others | All artifact-producing schemas |
| `record_id` | `^REC-[A-Z0-9._-]+$` | All governed contracts |
| `run_id` | `^run-[A-Za-z0-9._-]+$` | All governed contracts (lowercase `run-`) |
| `program_id` | `^PRG-[A-Z0-9._-]+$` | program_brief, decision_log, risk_register, assumption_register, milestone_plan, study_readiness_assessment, next_best_action_memo |
| `working_paper_id` | `^WKP-[A-Z0-9._-]+$` | comment_resolution_matrix, reviewer_comment_set, working_paper_input |
| `comment_set_id` | `^CSET-[A-Z0-9._-]+$` | comment_resolution_matrix, reviewer_comment_set |
| `matrix_id` | `^CRM-[A-Z0-9._-]+$` | comment_resolution_matrix |
| `review_id` | `^REV-[A-Z0-9._-]+$` | review-output.schema.json |
| `meeting_id` | no pattern | artifact_envelope, meeting_minutes_record |
| `study_id` | `^[A-Z0-9._-]+$` or no pattern | artifact_envelope, slide_deck, external_artifact_manifest |
| `review_cycle_id` | no pattern | artifact_envelope |
| `contract_id` | `^DOCXINJ-[A-Z0-9._-]+$` | pdf_anchored_docx_comment_injection_contract |
| `entity_id` | no pattern | provenance_record |
| `system_id` | no pattern | evaluation_manifest |
| `parent_artifact_id` | no pattern | external_artifact_manifest |
| `linked_work_item_id` | no pattern | evaluation_manifest |
| `provenance_record_id` | `^PRV-[A-Z0-9._-]+$` | working_paper_input |

**`contracts/schemas/` — nested entity IDs (inside array definitions)**

| Field | Pattern | Schemas that use it |
|---|---|---|
| `assumption_id` | `^ASM-[A-Z0-9._-]+$` | assumption_register |
| `decision_id` | `^DEC-[A-Z0-9._-]+$` | decision_log, program_brief; **no pattern** in meeting_minutes_record |
| `action_id` | `^ACT-[A-Z0-9._-]+$` | comment_resolution_matrix, review-output, meeting-minutes; `^NBA-[A-Z0-9._-]+$` in next_best_action_memo; **no pattern** in meeting_minutes_record, study_readiness_assessment |
| `risk_id` | `^RISK-[A-Z0-9._-]+$` | risk_register, program_brief |
| `entry_id` | `^ENT-[A-Z0-9._-]+$` | comment_resolution_matrix |
| `comment_id` | `^CMT-[A-Z0-9._-]+$` | reviewer_comment_set, comment_resolution_matrix |
| `finding_id` | `^FND-[A-Z0-9._-]+$` | review-output |
| `issue_id` | `^ISS-[A-Z0-9._-]+$` | meeting-minutes.schema.json |
| `provenance_id` | `^PRV-[A-Z0-9._-]+$` | reviewer_comment_set; **no pattern** in source_reference defs |
| `option_id` | no pattern | decision_log (options_considered) |
| `ref_id` | no pattern | source_reference defs (assumption_register, decision_log, risk_register, next_best_action_memo) |
| `gap_id` | no pattern | slide_intelligence_packet, meeting_minutes_record |
| `slide_id` | no pattern | slide_intelligence_packet |
| `claim_id` | no pattern | slide_intelligence_packet |
| `gate_id` | no pattern | study_readiness_assessment |
| `followup_id` | no pattern | meeting_minutes_record |
| `question_id` | no pattern | meeting_minutes_record |
| `source_id` | no pattern | meeting_minutes_record (followup), work-item.schema.json |
| `agent_id` | no pattern | provenance_record (agent entries) |
| `version_id` | no pattern | provenance_record (version history) |
| `milestone_id` | no pattern | milestone_plan (inferred from examples) |
| `edge_id` | no pattern | knowledge_graph_edge, slide_intelligence_packet |

**`schemas/` — legacy/infrastructure IDs (separate from contracts/)**

| Field | Pattern | Schema |
|---|---|---|
| `message_id` | `^MSG-[A-Z0-9._-]+$` | artifact-bus-message |
| `artifact_id` | `^ART-[A-Z0-9._-]+$` | artifact-bus-message, study-output-schema |
| `run_id` | `^RUN-[A-Z0-9._-]+$` | artifact-bus-message (**uppercase RUN-**, conflicts with contracts/) |
| `flow_id` | `^FLOW-[A-Z0-9._-]+$` | orchestration-flow |
| `stage_id` | no pattern | orchestration-flow |
| `bundle_id` | `^BND-[A-Z0-9._-]+$` | artifact-bundle |
| `manifest_id` | `^CMF-[A-Z0-9._-]+$` | compiler-manifest |
| `module_id` | `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$` | module-manifest (**lowercase dotted**, different convention) |
| `issue_id` | `^ISS-[A-Z0-9._-]+$` | issue-schema |
| `assumption_id` | `^ASM-[A-Z0-9._-]+$` | assumption-schema |
| `comment_id` | `^[A-Za-z0-9._-]+$` (no prefix) | comment-schema |
| `case_id` | `^PRC-[A-Z0-9._-]+$` | precedent-schema |
| `diagnostics_id` | `^DIA-[A-Z0-9._-]+$` | diagnostics |
| `work_item_id` | `^WI-[0-9]{4}$` | work-item (**numeric-only suffix**, different convention) |
| `review_id` | `^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$` | review-artifact (**date-based format**, different convention) |
| `record_id` | `^PRV-[A-Z0-9._-]+$` | provenance-schema (**PRV prefix**, conflicts with contracts/ `^REC-`) |
| `finding_id` | no pattern | work-item |

**Review action files (docs/review-actions/)**

These use a plain `"id"` field with locally scoped serial labels:
- `"F-1"` through `"F-12"` — findings
- `"A-1"` through `"A-7"` — actions
- `"G1"` through `"G7"` — gaps
- `"R1"` through `"R5"` — risks or recommendations
- `"REC-1"` through `"REC-7"` — recommendations
- `"RC-1"` etc. — review comments

These do not use typed field names (`finding_id`, `action_id`) and have no cross-artifact scope.

**Review manifests and failure mode registries**

- Review manifest scope IDs (`scope_id`) are slugified strings: `"p_gap_detection"`.
- Failure mode IDs are plain `"id"` slugs: `"poor_pdf_extraction"`, `"false_alignment"`.

### Key inconsistencies

1. **`run_id` format conflict** — `contracts/schemas/` uses `^run-[A-Za-z0-9._-]+$` (lowercase prefix),
   but `schemas/artifact-bus-message.schema.json` uses `^RUN-[A-Z0-9._-]+$` (uppercase prefix). Any bus
   message carrying a run ID from a governed contract will fail schema validation.

2. **`record_id` vs `provenance-schema` conflict** — Governed contracts define `record_id` as `^REC-[A-Z0-9._-]+$`.
   `schemas/provenance-schema.json` defines `record_id` as `^PRV-[A-Z0-9._-]+$`. These are different semantic
   objects named identically.

3. **`artifact_id` prefix inconsistency** — Some governed contracts require a type-specific prefix (e.g.,
   `^EVAL-`, `^DECLOG-`), while others accept any uppercase alphanumeric string (`^[A-Z0-9._-]+$`). The
   infrastructure `schemas/artifact-bus-message.schema.json` expects `^ART-` prefix for all artifact IDs,
   which conflicts with type-specific prefixes.

4. **`action_id` split between NBA- and ACT-** — The next_best_action_memo uses `^NBA-[A-Z0-9._-]+$` for
   its top-level `action_id`, while comment_resolution_matrix, review-output, and meeting-minutes use
   `^ACT-[A-Z0-9._-]+$` for nested action items. These represent different semantic layers (artifact vs entity)
   but the naming collision creates confusion when actions are referenced cross-artifact.

5. **`decision_id` unenforced in meeting minutes** — `contracts/schemas/meeting_minutes_record.schema.json`
   defines `decision_id` with no pattern, while `contracts/decision_log.schema.json` enforces `^DEC-[A-Z0-9._-]+$`.
   Meeting decisions are upstream sources for decision log entries; format mismatch prevents reliable linkage.

6. **Entity IDs with no patterns** — `gap_id`, `question_id`, `followup_id`, `slide_id`, `claim_id`,
   `gate_id`, `option_id`, `ref_id`, `stage_id`, `edge_id`, `agent_id`, `version_id`, `milestone_id` have no
   format constraints. These create unvalidatable links in downstream consumers.

7. **`review_id` format conflict** — `contracts/review-output.schema.json` uses `^REV-[A-Z0-9._-]+$`,
   while `schemas/review-artifact.schema.json` uses a date-based slug `^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$`.

8. **Plain `"id"` in review action files and failure mode registry** — These use a generic `"id"` field with
   local serial numbers. If these artifacts are ever consumed programmatically, the lack of typed field names
   prevents reliable field-level queries.

9. **`module_id` uses a different casing convention** — All other IDs are uppercase-prefix alphanumeric. Module
   IDs are lowercase dotted reverse-domain style. This is intentional and correct for its domain but needs to
   be explicitly exempted from the standard.

10. **`work_item_id` uses numeric-only suffix** — `^WI-[0-9]{4}$` limits the namespace and pads to 4 digits,
    which diverges from the alphanumeric suffix convention in all other schemas.

### Highest-risk areas

- **`run_id` conflict** (artifact-bus-message vs governed contracts) — breaks bus-level correlation.
- **`artifact_id` bus vs type-specific prefix conflict** — ART- prefix will not match any type-specific
  artifact ID emitted by a governed module.
- **Unpatterned entity IDs** in meeting_minutes_record (decision_id, action_id, question_id, gap_id) — these
  are high-volume entities that flow into downstream working paper generation. No validation at source
  means corrupt IDs can propagate silently.
- **`provenance_record_id` / `record_id` semantic overlap** — two fields with different prefixes that both
  represent "the provenance record for this artifact" across different schema layers.

---

## Canonical ID Model

### ID classes

Four ID classes are sufficient for this repository:

| Class | Definition | Scope |
|---|---|---|
| **Artifact ID** | Identifies a complete artifact document or package (a file, a bundle, a manifest). | Repository-wide unique |
| **Entity ID** | Identifies a typed sub-artifact item within an artifact (a decision, action, gap, risk, assumption, comment, finding, question). | Artifact-scoped; may be promoted to cross-artifact when referenced externally |
| **Run ID** | Identifies a single pipeline execution or provenance creation event. | Repository-wide unique |
| **Registry/Infrastructure ID** | Identifies an operational component: a module, a workflow flow, a bus message, a work item, a review scope. | Repository-wide unique; purpose-specific conventions allowed |

A fifth class — **Record ID** — wraps the provenance record for a given artifact creation event. It is a
sub-type of Artifact ID in practice, but treated separately because it currently has its own prefix (`REC-`)
and is present on nearly every governed artifact.

### Field names

| Class | Canonical field name | Notes |
|---|---|---|
| Artifact ID | `artifact_id` | Always used at document root level |
| Record ID | `record_id` | Provenance record for this artifact creation event; always `REC-` prefix |
| Entity ID | `<type>_id` | Named per entity type: `decision_id`, `action_id`, `risk_id`, `assumption_id`, `gap_id`, `question_id`, `finding_id`, `comment_id`, `option_id`, `milestone_id`, `gate_id`, `claim_id`, `slide_id`, `edge_id`, `followup_id`, `ref_id`, `agent_id`, `version_id` |
| Run ID | `run_id` | Always at document root level |
| Program ID | `program_id` | Cross-study/program scope; top-level field |
| Module ID | `module_id` | Infrastructure; lowercase dotted convention exempt from uppercase rule |
| Message ID | `message_id` | Bus infrastructure |
| Work Item ID | `work_item_id` | Operational tracking |
| Review ID | `review_id` | Review artifact identifier |
| Flow ID | `flow_id` | Orchestration infrastructure |
| Bundle ID | `bundle_id` | Artifact bundle |

### Format rules

**Rule 1 — Artifact IDs**

Artifact IDs use a type-specific uppercase prefix followed by a human-readable alphanumeric body:

```
^<TYPE-PREFIX>-[A-Z0-9][A-Z0-9._-]*$
```

The prefix identifies the artifact type (e.g., `EVAL`, `DECLOG`, `CRM`, `PRV`, `ASMREG`, `RISKREG`, `MMR`,
`SRA`, `MSPLAN`, `PB`, `STD`, `NBA-MEMO`, `WKP`, `CSET`, `DOCXINJ`, `AG`).

Schemas that currently accept `^[A-Z0-9._-]+$` (no prefix requirement) must be tightened to require the
type-specific prefix when that artifact type is identifiable at schema-authoring time.

**Rule 2 — Record IDs**

Record IDs always use the `REC-` prefix:

```
^REC-[A-Z0-9][A-Z0-9._-]*$
```

The semantic content after `REC-` should include the artifact type and a timestamp or sequence for
human debuggability, e.g. `REC-DECLOG-001`, `REC-EVAL-2026-001`.

**Rule 3 — Run IDs**

Run IDs always use the lowercase `run-` prefix followed by a compact ISO 8601 UTC timestamp:

```
^run-[0-9]{8}T[0-9]{6}Z$
```

Example: `run-20260318T012735Z`

This is the governing pattern. The `RUN-` uppercase variant in `schemas/artifact-bus-message.schema.json`
is a deviation that must be corrected (see Migration Strategy).

**Rule 4 — Entity IDs**

Entity IDs use an uppercase prefix matching the entity type, followed by an alphanumeric body:

```
^<ENTITY-PREFIX>-[A-Z0-9][A-Z0-9._-]*$
```

Canonical entity prefixes:

| Entity | Prefix | Example |
|---|---|---|
| Decision | `DEC` | `DEC-001` |
| Action item | `ACT` | `ACT-001` |
| Risk | `RISK` | `RISK-001` |
| Assumption | `ASM` | `ASM-001` |
| Gap | `GAP` | `GAP-001` |
| Question | `QST` | `QST-001` |
| Finding | `FND` | `FND-001` |
| Comment | `CMT` | `CMT-001` |
| Option | `OPT` | `OPT-001` |
| Milestone | `MS` | `MS-001` |
| Gate | `GATE` | `GATE-001` |
| Claim | `CLM` | `CLM-001` |
| Slide (unit) | `SLD` | `SLD-001` |
| Edge | `EDG` | `EDG-001` |
| Follow-up | `FUP` | `FUP-001` |
| Agent | `AGT` | `AGT-001` |
| Version | `VER` | `VER-001` |
| Reference | `REF` | `REF-001` |

**Rule 5 — Program IDs**

Program IDs use the `PRG-` prefix: `^PRG-[A-Z0-9][A-Z0-9._-]*$`. This is already enforced consistently.

**Rule 6 — Provenance Record ID (`record_id` in `schemas/provenance-schema.json`)**

This schema uses `^PRV-[A-Z0-9._-]+$` for its `record_id`, which conflicts with the `REC-` convention used
in governed contracts. The `schemas/provenance-schema.json` record represents a different artifact type
(a provenance record), and its identifier is already correctly typed as `artifact_id: ^PRV-[A-Z0-9._-]+$`
in `contracts/schemas/provenance_record.schema.json`. The `schemas/provenance-schema.json` is a legacy
schema; its `record_id` field name is misleading. See Migration Strategy.

**Rule 7 — Infrastructure / Registry IDs (exempt classes)**

These follow their own defined conventions and are not subject to the type-prefix rule for artifact IDs,
but they must still use a defined prefix pattern:

| Field | Pattern | Rationale |
|---|---|---|
| `module_id` | `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$` | Lowercase dotted; intentional for code namespace use |
| `work_item_id` | `^WI-[0-9]{4}$` | Existing enforcement; acceptable; migrate to `^WI-[A-Z0-9._-]+$` in v2 |
| `message_id` | `^MSG-[A-Z0-9._-]+$` | Bus infrastructure |
| `flow_id` | `^FLOW-[A-Z0-9._-]+$` | Orchestration |
| `bundle_id` | `^BND-[A-Z0-9._-]+$` | Artifact bundles |
| `manifest_id` | `^CMF-[A-Z0-9._-]+$` | Compiler manifest |
| `diagnostics_id` | `^DIA-[A-Z0-9._-]+$` | Diagnostics |
| `case_id` | `^PRC-[A-Z0-9._-]+$` | Precedent |
| `scope_id` | slugified string (review manifests) | Local-only; not cross-artifact |

### Examples

| ID class | Field | Value |
|---|---|---|
| Artifact ID | `artifact_id` | `DECLOG-2026-001` |
| Record ID | `record_id` | `REC-DECLOG-2026-001` |
| Run ID | `run_id` | `run-20260318T012735Z` |
| Entity — decision | `decision_id` | `DEC-001` |
| Entity — action | `action_id` | `ACT-001` |
| Entity — gap | `gap_id` | `GAP-001` |
| Entity — question | `question_id` | `QST-001` |
| Entity — finding | `finding_id` | `FND-001` |
| Entity — comment | `comment_id` | `CMT-001` |
| Entity — risk | `risk_id` | `RISK-001` |
| Entity — assumption | `assumption_id` | `ASM-001` |
| Entity — slide | `slide_id` | `SLD-001` |
| Entity — claim | `claim_id` | `CLM-001` |
| Program | `program_id` | `PRG-SPEC-001` |
| Module | `module_id` | `meeting_intelligence` |
| Work item | `work_item_id` | `WI-0001` |

---

## Normalization Rules

### Naming and scoping rules

**N1 — Plain `id` is prohibited at document root level.**
All document-root identifier fields must use a typed field name (`artifact_id`, `record_id`, `run_id`,
`program_id`, etc.). Plain `"id"` is only permitted inside review action output files and failure mode
registries where the field is used as a local label, not a cross-artifact identifier.

**N2 — Plain `id` in nested entities is a migration target.**
The `provenance_record.schema.json` agent entry and the `review-artifact.schema.json` nested items
use plain `"id"`. These should be migrated to typed names (`agent_id`, `finding_id`) in the next schema
version that modifies those definitions.

**N3 — Entity IDs are artifact-scoped unless externally referenced.**
An entity ID (e.g. `DEC-001`) is locally unique within the artifact that defines it. When a downstream
artifact references the entity cross-artifact, the consuming schema must also include the `artifact_id`
of the source artifact to disambiguate. The pattern is: `"source_artifact_id": "DECLOG-...", "decision_id": "DEC-001"`.

**N4 — `decision_id` in meeting_minutes_record must match the `DEC-` prefix.**
Meeting-recorded decisions are primary sources for the decision log. For cross-artifact linkage to work,
their `decision_id` values must conform to `^DEC-[A-Z0-9._-]+$` at creation time.

**N5 — `action_id` for top-level NBA memo vs nested action items.**
The `NBA-MEMO-` prefix identifies the artifact (the next_best_action_memo document). The `action_id` field
inside the `actions[]` array of that memo, and in all other schemas (comment_resolution_matrix,
review-output, meeting-minutes), should use `ACT-` to identify action items as entities. The memo artifact ID
prefix `NBA-MEMO-` should remain as-is; only the sub-entity action IDs change. The `action_id` field in
`next_best_action_memo.schema.json`'s `recommended_actions` array should be updated from `^NBA-[A-Z0-9._-]+$`
to `^ACT-[A-Z0-9._-]+$` when that schema is next revised.

**N6 — `run_id` is always lowercase `run-` prefix.**
Any schema or validator using `^RUN-[A-Z0-9._-]+$` is non-conforming and must be updated.

**N7 — `record_id` always uses `REC-` prefix.**
`schemas/provenance-schema.json` uses `^PRV-` for its `record_id`, which is a legacy deviation. When that
schema is revised, its `record_id` should be renamed `artifact_id` (it identifies a provenance artifact,
not a generic record) or migrated to `^REC-` if the field represents the creation record.

**N8 — Cross-schema references use the canonical field name of the source.**
When schema B references an artifact produced by schema A, it uses the same field name as schema A defines
for that identifier. For example, a working paper input references `working_paper_id` (not `wkp_id` or
`wp_id`) because that is the canonical field name in the working_paper contract.

### Linking rules

**L1 — Artifact-to-artifact links use `<type>_id` pair fields.**
Any cross-artifact reference includes both the type-appropriate identifier field and, when needed for
disambiguation, `artifact_type` or `artifact_id` of the source artifact.

**L2 — Parent artifact links use `parent_artifact_id`.**
When one artifact is derived from another (e.g., an external manifest derived from a study output), the
`parent_artifact_id` field identifies the upstream artifact. This field requires the same uppercase prefix
convention as `artifact_id`.

**L3 — Entity-to-entity links within an artifact use local `_id` references.**
`related_claim_ids`, `related_assumption_ids`, etc. may use the short entity ID format (`CLM-001`) when
the reference is known to be within the same artifact scope.

**L4 — Entity cross-artifact links include the source artifact ID.**
Any entity ID reference that crosses artifact boundaries must be accompanied by a `source_artifact_id`
field identifying which artifact document the entity ID is scoped to.

---

## Migration Strategy

### Immediate changes (no compatibility risk)

These changes add or tighten patterns on fields that currently have no pattern. Adding a pattern is a
non-breaking tightening — it only affects future instances and does not invalidate existing examples that
already use the correct format.

1. **Add `^DEC-[A-Z0-9._-]+$` pattern to `decision_id` in `meeting_minutes_record.schema.json`**
   Priority: High. These decisions are upstream sources for the decision log.

2. **Add `^ACT-[A-Z0-9._-]+$` pattern to `action_id` in `meeting_minutes_record.schema.json` and
   `study_readiness_assessment.schema.json`**
   Priority: High. Needed for reliable cross-artifact action tracking.

3. **Add `^QST-[A-Z0-9._-]+$` pattern to `question_id` in `meeting_minutes_record.schema.json`**
   Priority: Medium.

4. **Add `^GAP-[A-Z0-9._-]+$` pattern to `gap_id` in `slide_intelligence_packet.schema.json` and
   `meeting_minutes_record.schema.json`**
   Priority: Medium. Required for working paper traceability.

5. **Add `^OPT-[A-Z0-9._-]+$` pattern to `option_id` in `decision_log.schema.json`**
   Priority: Low.

6. **Add `^MS-[A-Z0-9._-]+$` pattern to `milestone_id` in `milestone_plan.schema.json`**
   Priority: Low.

7. **Add `^GATE-[A-Z0-9._-]+$` pattern to `gate_id` in `study_readiness_assessment.schema.json`**
   Priority: Low.

8. **Add `^SLD-[A-Z0-9._-]+$` pattern to `slide_id` in `slide_intelligence_packet.schema.json`**
   Priority: Low.

9. **Add `^CLM-[A-Z0-9._-]+$` pattern to `claim_id` in `slide_intelligence_packet.schema.json`**
   Priority: Low.

10. **Add `^EDG-[A-Z0-9._-]+$` pattern to `edge_id` in `knowledge_graph_edge.schema.json` and
    `slide_intelligence_packet.schema.json`**
    Priority: Low.

11. **Add `^[A-Z0-9._-]+$` pattern to `meeting_id` in `artifact_envelope.schema.json` and
    `meeting_minutes_record.schema.json`**
    Priority: Medium. Meeting IDs appear in multiple artifact types.

12. **Add `^[A-Z0-9._-]+$` pattern to `study_id` in `slide_deck.schema.json`**
    Priority: Medium.

### Compatibility-sensitive changes (require coordination)

These changes rename fields, alter existing patterns, or affect already-emitted examples.

13. **Fix `run_id` conflict in `schemas/artifact-bus-message.schema.json`**
    Current: `^RUN-[A-Z0-9._-]+$`
    Target: `^run-[A-Za-z0-9._-]+$`
    Risk: Any existing bus messages or tests using `RUN-` format will fail. The test
    `test_artifact_bus_invalid_run_id_pattern_fails_schema` tests that non-matching run IDs fail; changing the
    pattern will cause that test to need an updated negative example. Existing tests using `RUN-format` in
    fixtures also need updates.

14. **Align `artifact_id` pattern in `schemas/artifact-bus-message.schema.json`**
    Current: `^ART-[A-Z0-9._-]+$`
    Target: The bus schema should accept any valid artifact ID, not just `ART-` prefixed ones. Change to
    `^[A-Z0-9._-]+$` or a looser pattern that accepts all type-specific prefixes.
    Risk: Existing test fixtures use `ART-` prefix. Update fixtures alongside the schema.

15. **Fix `next_best_action_memo.schema.json` sub-entity `action_id` from NBA- to ACT-**
    Current: `^NBA-[A-Z0-9._-]+$` for `action_id` in `recommended_actions[]`
    Target: `^ACT-[A-Z0-9._-]+$`
    Risk: Existing examples and downstream consumers that generate NBA- action IDs need updating.

16. **Resolve `schemas/provenance-schema.json` `record_id` field naming**
    Current: `record_id: ^PRV-[A-Z0-9._-]+$`
    Target: rename to `artifact_id` (it identifies a provenance artifact) with `^PRV-[A-Z0-9._-]+$` pattern
    Risk: Any consumer of `schemas/provenance-schema.json` using `record_id` field name will break.

### Phased rollout order

**Phase 1 — Pattern addition (no renames, no format changes)**
Items 1–12 above. Pure additive enforcement. Does not break any existing valid examples.
Target: before any new Layer 2 module implementation.

**Phase 2 — Infrastructure schema alignment**
Items 13–14: fix `run_id` and `artifact_id` patterns in artifact-bus-message. Update bus message fixtures
and tests. This is the highest-risk change but also the most important for bus correlation.
Target: as part of the next infrastructure contract revision.

**Phase 3 — Action ID normalization and provenance schema cleanup**
Items 15–16: normalize NBA- action IDs to ACT-, resolve provenance-schema record_id naming.
Target: after Phase 2 is validated. Requires example file updates.

---

## Enforcement Plan

### Schema updates (Phase 1, immediate)
Add `pattern` constraints to all entity ID fields listed in the "Immediate changes" section.
No new schemas needed; this is purely additive constraint enforcement.

### Schema updates (Phase 2, infrastructure)
Update `schemas/artifact-bus-message.schema.json`:
- `run_id` pattern from `^RUN-` to `^run-`
- `artifact_id` pattern from `^ART-` to `^[A-Z0-9._-]+$`

### Validator updates
`shared/adapters/artifact_emitter.py` currently validates artifact_id, artifact_type, module_origin,
contract_version, and lifecycle_state. Add a lightweight validation helper:

```python
def validate_id_pattern(field_name: str, value: str, pattern: str) -> None:
    """Raise ValueError if value does not match the canonical pattern."""
```

This can be called by `create_artifact_metadata` and other helpers to enforce canonical ID format
at generation time, not just at schema validation time.

### Test updates
- `tests/test_orchestration_boundaries.py` includes tests for message_id and run_id patterns. When
  `artifact-bus-message.schema.json` is updated (Phase 2), update the negative test fixture from `RUN-bad`
  to a format that is actually invalid under the new pattern.
- Add negative tests for entity ID patterns (decision_id, action_id, gap_id, question_id) in the
  contract schema test suite when Phase 1 pattern additions land.

### Registry checks
No new registry check infrastructure is required for Phase 1 and 2. The existing pytest-based schema
validation in `tests/test_contracts.py` (if present) or the golden-path fixture checks will cover
enforcement once patterns are added to schemas.

For Phase 3 and beyond, a lightweight ID-consistency linter (a single Python script in `scripts/`) that
scans all example JSON files and validates every `_id`-named field against its schema-defined pattern
would provide a standing enforcement check. This is useful but not required to unblock Layer 2.

### Utility needs
One utility function is sufficient:
- `scripts/validate_id_patterns.py` — scans `contracts/examples/` and `contracts/` example JSON files,
  loads the corresponding schema, and validates all `_id` fields against their declared patterns.
  Emits a machine-readable report. This script does not need to be written before Layer 2 begins, but
  should exist before any checkpoint that bundles review artifacts.

---

## Open Decisions

1. **Should `artifact_id` in the artifact bus accept all type-specific prefixes, or should bus messages
   use their own ART- namespace?**
   The current ART- prefix in the bus schema creates a disconnect from type-specific artifact IDs. Options:
   (a) loosen the bus schema to `^[A-Z0-9._-]+$`, accepting all prefixes; (b) keep ART- as the bus-level
   alias and map back to the originating artifact ID in payload; (c) remove the pattern constraint from
   the bus schema entirely and rely on payload validation. Option (a) is recommended for simplicity but
   requires a decision before Phase 2.

2. **Should entity IDs be made globally unique (artifact-scoped prefix) or remain locally scoped?**
   Currently `DEC-001` is only meaningful within the decision log that contains it. If entities need to
   be referenced cross-artifact without always carrying the parent `artifact_id`, then entity IDs should
   include a study- or program-scoped qualifier (e.g., `DEC-PRG-SPEC-001-001`). This would be a more
   significant breaking change. Recommendation: keep entity IDs artifact-scoped for now and rely on the
   L3/L4 linking rules above. Re-evaluate when the knowledge graph or working paper generator demonstrates
   a concrete need for globally unique entity IDs.

3. **What is the correct resolution for `schemas/provenance-schema.json` vs
   `contracts/schemas/provenance_record.schema.json`?**
   These are two different schemas describing overlapping provenance concepts. `schemas/provenance-schema.json`
   appears to be a legacy schema pre-dating the governed contracts layer. The options are: (a) deprecate
   `schemas/provenance-schema.json` and route all consumers to `contracts/schemas/provenance_record.schema.json`;
   (b) keep both and document the distinction explicitly; (c) merge them into a single canonical schema.
   Option (a) is recommended but requires auditing all consumers of the legacy schema first.

4. **Should review action files (`docs/review-actions/*.json`) be migrated to use typed field names
   (`finding_id`, `action_id`, `recommendation_id`) instead of plain `"id"`?**
   These files are currently human-authored review artifacts with local serial labels. Migrating them to
   typed field names would allow programmatic consumption (e.g., work item generation from review findings).
   The cost is non-trivial: all existing review action JSON files would need restructuring. Recommendation:
   apply only to new review action files going forward; define a standard template update that uses typed
   field names; do not retroactively migrate existing files.

5. **Should `work_item_id` be changed from `^WI-[0-9]{4}$` to `^WI-[A-Z0-9._-]+$`?**
   The current numeric-only, zero-padded format limits namespace and diverges from all other entity ID
   conventions. However, changing it now will invalidate existing work items (WI-0001 through WI-NNNN)
   unless a compatibility shim is provided. Recommendation: keep the current format for work_item_id in
   this schema version; define a planned v2 transition to `^WI-[A-Z0-9._-]+$` when work items are next
   extended.

---

## Recommendation

The simplest viable canonical ID approach for this repository is:

**One format rule, applied consistently across all artifact and entity IDs:**
```
^<PREFIX>-[A-Z0-9][A-Z0-9._-]*$
```
where `PREFIX` is a short uppercase string identifying the type, and the body is human-readable and
debuggable. This rule already covers the vast majority of governed schemas. The primary work is:

1. Adding the missing `pattern` constraints to the ~15 entity ID fields that currently lack them.
2. Fixing the `run_id` and `artifact_id` format conflicts in `schemas/artifact-bus-message.schema.json`.
3. Deciding the five open questions above before any further schema work.

Do not introduce a new ID generation library, a UUID-based system, or a globally unique key scheme.
The current prefix-based human-readable format is debuggable, already mostly consistent, and well-suited
to the artifact sizes and pipeline stages in this repository. The goal is enforcement of the existing
pattern, not replacement of it.

**Migrate in three phases:**
- Phase 1: Pattern additions (no breaking changes) — do this before any new module implementation.
- Phase 2: Infrastructure schema alignment (artifact-bus run_id / artifact_id) — do this in the next
  infrastructure contract revision.
- Phase 3: Action ID normalization and legacy schema cleanup — after Phase 2.

---

## Files to be changed (Phase 1)

| File | Change |
|---|---|
| `contracts/schemas/meeting_minutes_record.schema.json` | Add patterns to `decision_id`, `action_id`, `question_id`, `gap_id`, `followup_id`, `meeting_id` |
| `contracts/schemas/study_readiness_assessment.schema.json` | Add pattern to `action_id`, `gate_id` |
| `contracts/schemas/slide_intelligence_packet.schema.json` | Add patterns to `gap_id`, `slide_id`, `claim_id`, `edge_id` |
| `contracts/schemas/knowledge_graph_edge.schema.json` | Add pattern to `edge_id` |
| `contracts/schemas/milestone_plan.schema.json` | Add pattern to `milestone_id` (in milestone definitions) |
| `contracts/schemas/decision_log.schema.json` | Add pattern to `option_id` |
| `contracts/schemas/artifact_envelope.schema.json` | Add pattern to `meeting_id`, `study_id`, `review_cycle_id` |
| `contracts/schemas/slide_deck.schema.json` | Add pattern to `artifact_id`, `meeting_id`, `study_id` |

## Files to be changed (Phase 2)

| File | Change |
|---|---|
| `schemas/artifact-bus-message.schema.json` | Change `run_id` pattern from `^RUN-` to `^run-`; change `artifact_id` pattern from `^ART-` to `^[A-Z0-9._-]+$` |
| `tests/test_orchestration_boundaries.py` | Update bus message negative test fixtures for `run_id` |

## Files to be changed (Phase 3)

| File | Change |
|---|---|
| `contracts/schemas/next_best_action_memo.schema.json` | Change sub-entity `action_id` from `^NBA-` to `^ACT-` |
| `contracts/examples/next_best_action_memo.json` | Update action_id values from NBA- to ACT- format |
| `schemas/provenance-schema.json` | Rename `record_id` to `artifact_id` or deprecate in favour of `contracts/schemas/provenance_record.schema.json` |
| `docs/review-actions/action-tracker-template.md` | Update to use typed field names (`finding_id`, `action_id`, `recommendation_id`) for new files |
