# Plan — Canonical ID Standard (Refined) — 2026-03-18

## Prompt type
PLAN

## Roadmap item
Pre-M — Canonical ID Standard (refinement pass; resolves open decisions from `PLAN-CANONICAL-ID-STANDARD-2026-03-18.md`)

## Purpose

This document resolves the five open decisions from the prior PLAN and produces a concrete,
implementation-ready specification. The prior PLAN was directionally correct but left key choices
unresolved. This document makes those choices explicitly, produces the full canonical prefix table,
tightens the normalization rules, and assesses implementation readiness.

**This document does not implement anything.** It is the design authority that the subsequent BUILD
prompt must follow without ambiguity.

---

## Decision Summary

- **Bus/artifact ID decision:** Option A — the bus accepts typed artifact IDs directly. The
  `artifact_id` pattern in `schemas/artifact-bus-message.schema.json` is widened from `^ART-` to
  `^[A-Z][A-Z0-9._-]*$`. The `ART-` prefix is retired.

- **NBA/ACT decision:** `NBA-MEMO-` remains as the artifact-level prefix for the
  `next_best_action_memo` document. The sub-entity `action_id` field inside the `actions[]` array of
  that memo — and in every other schema — must use `ACT-`. The `NBA-` prefix for action entity IDs
  is a naming collision and is removed from the canonical model. `NBA` exists only at artifact scope.

- **Entity scope decision:** Artifact-scoped by default. Entity IDs (e.g., `DEC-001`) are unique
  within the artifact that defines them. Cross-artifact entity references must always pair the entity
  ID with a `source_artifact_id` field. No globally unique entity IDs are introduced.

---

## Decision Rationale

### 1 — Bus/artifact ID (Option A chosen)

**Why Option A:**

The artifact bus is a routing envelope; it does not own artifact identity. Every governed module
emits artifacts with type-specific IDs (e.g., `DECLOG-2026-001`, `CRM-001`). If the bus demands an
`ART-` prefix, either (a) modules must mint a second bus-level ID that has no meaning outside the
bus, or (b) the bus can never validate a real governed artifact. Both outcomes are worse than
widening the bus pattern.

Option B (wrapper/envelope ID) introduces a mapping layer with no observable benefit for a
single-repository platform of this size. Option A is simpler, traceability is preserved via
`artifact_type` and `lineage_ref`, and no new ID class is needed.

**What it changes:** `artifact_id` pattern in `schemas/artifact-bus-message.schema.json` from
`^ART-[A-Z0-9._-]+$` to `^[A-Z][A-Z0-9._-]*$`. The existing bus example
(`ART-MINUTES-2026-0317-001`) must be updated to a type-specific ID.

**What it preserves:** All governed artifact IDs pass through the bus without remapping. The
`message_id` field (prefix `MSG-`) continues to identify the bus envelope itself. `lineage_ref`
(`LIN-` prefix) continues to identify the lineage record. No new fields are added.

**What it avoids:** A second ID namespace that would require maintaining a mapping table between
`ART-` IDs and typed artifact IDs.

### 2 — NBA vs ACT (ACT- everywhere for entities; NBA-MEMO- artifact prefix kept)

**Precise ruling:**

- `NBA-MEMO-` is a valid artifact-type prefix identifying a `next_best_action_memo` document. It
  stays, because changing artifact-level prefixes requires updating every artifact and every
  downstream consumer that references the artifact type.
- `NBA-` used as an entity-level `action_id` prefix inside the `actions[]` array of that memo is a
  naming collision with the artifact prefix, not a distinct semantic. It is not an artifact type; it
  is an action entity. The canonical entity prefix for action items is `ACT-`.
- `NBA-` must not appear in the canonical model for any entity-level ID in any schema. The migration
  changes `^NBA-[A-Z0-9._-]+$` to `^ACT-[A-Z0-9._-]+$` in the `action` `$def` of
  `next_best_action_memo.schema.json`.

**NBA- is not a prefix for anything other than the artifact-level `NBA-MEMO-` pattern.** The
`NBA-001`, `NBA-002` action IDs in the existing example are non-conforming and will be updated to
`ACT-001`, `ACT-002` as part of Phase 3.

### 3 — Entity scope (artifact-scoped chosen)

**Why artifact-scoped:**

This repository's entities (decisions, risks, actions, gaps) do not have a demonstrated need for
global uniqueness today. Globally unique entity IDs would require a centralized ID registry or
compound keys (e.g., `DEC-PRG-SPEC-001-001`), adding operational complexity with no current
consumer that needs it. The working paper generator and knowledge graph reference entities by
`(source_artifact_id, entity_id)` pair — this satisfies all current cross-artifact traceability
requirements.

**How cross-artifact references work (one rule):**

Any schema field that references an entity from another artifact must declare a companion
`source_artifact_id` field at the same nesting level. See Normalization Rule N4.

**Exception path:** If the knowledge graph module or working paper generator demonstrates a concrete
need for global entity uniqueness in a future BUILD prompt, the compound key pattern
`<artifact_type>/<artifact_id>/<entity_id>` is the approved extension path. This does not require
a schema change to entity IDs themselves; it requires a cross-reference field.

---

## Canonical Prefix Table

| ID class | Canonical field name | Prefix | Scope | Regex | Example | Generated where | Notes |
|---|---|---|---|---|---|---|---|
| Run ID | `run_id` | `run-` | Repository-wide unique | `^run-[0-9]{8}T[0-9]{6}Z$` | `run-20260318T012735Z` | Orchestration layer at pipeline start | Only ID with a lowercase prefix. Strict timestamp body required. |
| Artifact ID (generic) | `artifact_id` | Type-specific (see table rows below) | Repository-wide unique | `^[A-Z][A-Z0-9._-]*$` | `DECLOG-2026-001` | Generating module at artifact creation | No generic `ART-` prefix. Always type-specific. |
| Provenance record ID | `record_id` | `REC-` | Repository-wide unique | `^REC-[A-Z0-9][A-Z0-9._-]*$` | `REC-DECLOG-2026-001` | Governed contract layer | Present on every governed contract at root level. |
| Decision ID | `decision_id` | `DEC-` | Artifact-scoped | `^DEC-[A-Z0-9][A-Z0-9._-]*$` | `DEC-001` | `decision_log`, `meeting_minutes_record` | Must match when cross-referenced; pair with `source_artifact_id`. |
| Action ID | `action_id` | `ACT-` | Artifact-scoped | `^ACT-[A-Z0-9][A-Z0-9._-]*$` | `ACT-001` | Any artifact with action items | Replaces `NBA-` for all action entities. Used in all schemas. |
| Risk ID | `risk_id` | `RISK-` | Artifact-scoped | `^RISK-[A-Z0-9][A-Z0-9._-]*$` | `RISK-001` | `risk_register`, `program_brief` | |
| Assumption ID | `assumption_id` | `ASM-` | Artifact-scoped | `^ASM-[A-Z0-9][A-Z0-9._-]*$` | `ASM-001` | `assumption_register` | |
| Gap ID | `gap_id` | `GAP-` | Artifact-scoped | `^GAP-[A-Z0-9][A-Z0-9._-]*$` | `GAP-001` | `slide_intelligence_packet`, `meeting_minutes_record` | |
| Question ID | `question_id` | `QST-` | Artifact-scoped | `^QST-[A-Z0-9][A-Z0-9._-]*$` | `QST-001` | `meeting_minutes_record` | |
| Finding ID | `finding_id` | `FND-` | Artifact-scoped | `^FND-[A-Z0-9][A-Z0-9._-]*$` | `FND-001` | `review-output` | |
| Comment ID | `comment_id` | `CMT-` | Artifact-scoped | `^CMT-[A-Z0-9][A-Z0-9._-]*$` | `CMT-001` | `reviewer_comment_set`, `comment_resolution_matrix` | |
| Follow-up ID | `followup_id` | `FUP-` | Artifact-scoped | `^FUP-[A-Z0-9][A-Z0-9._-]*$` | `FUP-001` | `meeting_minutes_record` | |
| Slide ID | `slide_id` | `SLD-` | Artifact-scoped | `^SLD-[A-Z0-9][A-Z0-9._-]*$` | `SLD-001` | `slide_intelligence_packet` | |
| Claim ID | `claim_id` | `CLM-` | Artifact-scoped | `^CLM-[A-Z0-9][A-Z0-9._-]*$` | `CLM-001` | `slide_intelligence_packet` | |
| Option ID | `option_id` | `OPT-` | Artifact-scoped | `^OPT-[A-Z0-9][A-Z0-9._-]*$` | `OPT-001` | `decision_log` | |
| Milestone ID | `milestone_id` | `MS-` | Artifact-scoped | `^MS-[A-Z0-9][A-Z0-9._-]*$` | `MS-001` | `milestone_plan` | |
| Gate ID | `gate_id` | `GATE-` | Artifact-scoped | `^GATE-[A-Z0-9][A-Z0-9._-]*$` | `GATE-001` | `study_readiness_assessment` | |
| Edge ID | `edge_id` | `EDG-` | Artifact-scoped | `^EDG-[A-Z0-9][A-Z0-9._-]*$` | `EDG-001` | `knowledge_graph_edge`, `slide_intelligence_packet` | |
| Entry ID | `entry_id` | `ENT-` | Artifact-scoped | `^ENT-[A-Z0-9][A-Z0-9._-]*$` | `ENT-001` | `comment_resolution_matrix` | Already enforced; listed for completeness. |
| Issue ID | `issue_id` | `ISS-` | Artifact-scoped | `^ISS-[A-Z0-9][A-Z0-9._-]*$` | `ISS-001` | `meeting_minutes_record` | Already enforced in `contracts/`. |
| Review ID | `review_id` | `REV-` | Repository-wide unique | `^REV-[A-Z0-9][A-Z0-9._-]*$` | `REV-2026-001` | Review artifact | `contracts/` convention governs. `schemas/review-artifact.schema.json` date-slug is legacy; must be aligned. |
| Message ID | `message_id` | `MSG-` | Repository-wide unique | `^MSG-[A-Z0-9][A-Z0-9._-]*$` | `MSG-MEET-001` | Orchestration layer (bus) | Bus envelope identifier; not an artifact ID. |
| Lineage ref | `lineage_ref` | `LIN-` | Repository-wide unique | `^LIN-[A-Z0-9][A-Z0-9._-]*$` | `LIN-001` | Orchestration/lineage layer | Already enforced in bus schema. |
| Bundle ID | `bundle_id` | `BND-` | Repository-wide unique | `^BND-[A-Z0-9][A-Z0-9._-]*$` | `BND-001` | Artifact bundle | |
| Program ID | `program_id` | `PRG-` | Cross-artifact | `^PRG-[A-Z0-9][A-Z0-9._-]*$` | `PRG-SPEC-001` | Program layer | Already enforced consistently. |

**Artifact-type prefixes (for `artifact_id` field):**

| Artifact type | Prefix | Example |
|---|---|---|
| Decision log | `DECLOG-` | `DECLOG-2026-001` |
| Risk register | `RISKREG-` | `RISKREG-2026-001` |
| Assumption register | `ASMREG-` | `ASMREG-2026-001` |
| Comment resolution matrix | `CRM-` | `CRM-2026-001` |
| Meeting minutes record | `MMR-` | `MMR-2026-0317-001` |
| Next best action memo | `NBA-MEMO-` | `NBA-MEMO-2026-001` |
| Study readiness assessment | `SRA-` | `SRA-2026-001` |
| Milestone plan | `MSPLAN-` | `MSPLAN-2026-001` |
| Program brief | `PB-` | `PB-2026-001` |
| Evaluation manifest | `EVAL-` | `EVAL-2026-001` |
| Provenance record | `PRV-` | `PRV-2026-001` |
| Standard | `STD-` | `STD-001` |
| Working paper | `WKP-` | `WKP-2026-001` |
| Reviewer comment set | `CSET-` | `CSET-2026-001` |
| Slide deck | `SLDK-` | `SLDK-2026-001` |
| Slide intelligence packet | `SIP-` | `SIP-2026-001` |
| DOCX injection contract | `DOCXINJ-` | `DOCXINJ-001` |
| External artifact manifest | `AG-` | `AG-2026-001` |
| Review output | `REV-` | `REV-2026-001` |

**Explicitly exempt ID classes (do not apply the canonical format rule):**

| Field | Pattern | Rationale |
|---|---|---|
| `module_id` | `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$` | Lowercase dotted reverse-domain; intentional code-namespace convention. |
| `work_item_id` | `^WI-[0-9]{4}$` (current); `^WI-[A-Z0-9._-]+$` (v2) | Current numeric format is enforced and stable. v2 migration is deferred. |
| `scope_id` (review manifests) | Slugified string | Local label; not cross-artifact; not queryable externally. |
| `flow_id` | `^FLOW-[A-Z0-9._-]+$` | Orchestration infrastructure; already consistent. |
| `manifest_id` | `^CMF-[A-Z0-9._-]+$` | Compiler manifest; already consistent. |
| `diagnostics_id` | `^DIA-[A-Z0-9._-]+$` | Diagnostics; already consistent. |
| `case_id` | `^PRC-[A-Z0-9._-]+$` | Precedent; already consistent. |
| Plain `"id"` in review action files | Local serial labels (e.g., `F-1`, `A-3`) | Human-authored; not cross-artifact; template update governs new files only. |

---

## Normalization Rules

These rules are numbered for direct reference in schema comments, test names, and validator messages.

1. **Plain `id` is prohibited at document root level.** Every root-level identifier field must use
   a typed field name (`artifact_id`, `record_id`, `run_id`, `program_id`, etc.). No exceptions for
   governed contract schemas.

2. **Plain `id` inside nested entities is a migration target, not a current blocker.** Existing
   nested `id` fields (e.g., in `provenance_record.schema.json` agent entries) must be renamed to
   their typed name (`agent_id`, `version_id`) in the next schema revision that touches those
   definitions. New schema definitions must use typed names.

3. **Entity IDs are artifact-scoped.** An entity ID (e.g., `DEC-001`) is locally unique within the
   artifact that defines it. There is no expectation of global uniqueness.

4. **Cross-artifact entity references must pair the entity ID with `source_artifact_id`.** Any
   schema field that references an entity from a different artifact must include a sibling field
   named `source_artifact_id` at the same nesting level. The `source_artifact_id` value must conform
   to the artifact ID pattern (`^[A-Z][A-Z0-9._-]*$`). `source_run_id` is optional; include it only
   when provenance correlation is explicitly required by the consuming module.

5. **`run_id` always uses the lowercase `run-` prefix with a compact UTC timestamp body.** The
   canonical pattern is `^run-[0-9]{8}T[0-9]{6}Z$`. Any schema using `^RUN-` is non-conforming
   and must be updated. This applies to all layers including infrastructure schemas.

6. **`record_id` always uses the `REC-` prefix.** Any schema using `^PRV-` for a field named
   `record_id` is non-conforming (that usage identifies a provenance artifact, not a record, and the
   field should be renamed `artifact_id`).

7. **`artifact_id` at document root always uses a type-specific prefix.** No schema may declare
   `artifact_id` with a generic `^[A-Z0-9._-]+$` pattern when the artifact type is known at
   schema-authoring time. The bus schema is the only caller exempt from having a fixed type prefix
   because it handles all artifact types; its pattern is the general `^[A-Z][A-Z0-9._-]*$`.

8. **`action_id` uses `ACT-` everywhere.** The `NBA-` entity prefix for action items is retired.
   The artifact-level `NBA-MEMO-` prefix for the memo artifact is unaffected.

9. **All entity ID fields must have a `pattern` constraint in the JSON Schema.** Entity fields with
   no pattern are a defect, not a deliberate choice. The patterns are defined in the canonical prefix
   table above. Adding a pattern is non-breaking for any instance that already uses a conforming
   value.

10. **Artifact-to-artifact links use the canonical field name of the source.** When schema B
    references an artifact produced by schema A, it uses the same field name as schema A defines
    (e.g., `working_paper_id`, not `wkp_id`). Aliases are not permitted in new schemas.

11. **Parent artifact links use `parent_artifact_id`.** When one artifact is derived from another,
    `parent_artifact_id` identifies the upstream source. It must conform to `^[A-Z][A-Z0-9._-]*$`.

12. **`source_artifact_id` is mandatory for cross-artifact entity references; `source_run_id` is
    optional.** A consumer may include `source_run_id` when strict provenance correlation is needed,
    but it is not required for the entity reference to be valid.

---

## Schema Impact Table

### Phase 1 — Pattern addition (non-breaking)

| Schema/file path | Current field(s) | Problem | Change required | Breaking? | Fixture/test update? | Migration phase |
|---|---|---|---|---|---|---|
| `contracts/schemas/meeting_minutes_record.schema.json` | `decision_id` (no pattern) | Prevents reliable cross-artifact linkage to `decision_log` | Add `^DEC-[A-Z0-9][A-Z0-9._-]*$` pattern | No | Y — add positive + negative examples | Phase 1 |
| `contracts/schemas/meeting_minutes_record.schema.json` | `action_id` (no pattern) | No validation at source; corrupt IDs propagate | Add `^ACT-[A-Z0-9][A-Z0-9._-]*$` pattern | No | Y — add positive + negative examples | Phase 1 |
| `contracts/schemas/meeting_minutes_record.schema.json` | `question_id` (no pattern) | Unvalidatable question links | Add `^QST-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/meeting_minutes_record.schema.json` | `gap_id` (no pattern) | Unvalidatable gap links | Add `^GAP-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/meeting_minutes_record.schema.json` | `followup_id` (no pattern) | Unvalidatable follow-up links | Add `^FUP-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/study_readiness_assessment.schema.json` | `action_id` (no pattern) | No validation at source | Add `^ACT-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/study_readiness_assessment.schema.json` | `gate_id` (no pattern) | Unvalidatable gate links | Add `^GATE-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/slide_intelligence_packet.schema.json` | `gap_id` (no pattern) | Working paper traceability gap | Add `^GAP-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/slide_intelligence_packet.schema.json` | `slide_id` (no pattern) | Unvalidatable slide references | Add `^SLD-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/slide_intelligence_packet.schema.json` | `claim_id` (no pattern) | Unvalidatable claim references | Add `^CLM-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/slide_intelligence_packet.schema.json` | `edge_id` (no pattern) | Unvalidatable edge references | Add `^EDG-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/knowledge_graph_edge.schema.json` | `edge_id` (no pattern) | Unvalidatable edge identity | Add `^EDG-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/milestone_plan.schema.json` | `milestone_id` (no pattern) | Unvalidatable milestone references | Add `^MS-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/decision_log.schema.json` | `option_id` (no pattern) | Unvalidatable option references | Add `^OPT-[A-Z0-9][A-Z0-9._-]*$` pattern | No | N | Phase 1 |
| `contracts/schemas/artifact_envelope.schema.json` | `meeting_id`, `review_cycle_id` (no pattern) | Inconsistent identifiers on shared envelope | Add `^[A-Z][A-Z0-9._-]*$` pattern to both | No | N | Phase 1 |
| `contracts/schemas/slide_deck.schema.json` | `study_id` (no pattern) | Inconsistent study identifiers | Add `^[A-Z][A-Z0-9._-]*$` pattern | No | N | Phase 1 |

### Phase 2 — Infrastructure alignment (breaking)

| Schema/file path | Current field(s) | Problem | Change required | Breaking? | Fixture/test update? | Migration phase |
|---|---|---|---|---|---|---|
| `schemas/artifact-bus-message.schema.json` | `run_id: ^RUN-[A-Z0-9._-]+$` | Uppercase `RUN-` conflicts with every governed contract's `run-` prefix; bus cannot correlate runs | Change pattern to `^run-[0-9]{8}T[0-9]{6}Z$` | **Yes** — existing bus fixtures use `RUN-` format | **Y** — update `docs/examples/artifact-bus-message.example.json` and bus test fixtures in `tests/test_orchestration_boundaries.py` | Phase 2 |
| `schemas/artifact-bus-message.schema.json` | `artifact_id: ^ART-[A-Z0-9._-]+$` | `ART-` prefix matches no governed artifact; bus can never carry a real typed artifact | Change pattern to `^[A-Z][A-Z0-9._-]*$` | **Yes** — existing bus example uses `ART-MINUTES-...` format | **Y** — update `docs/examples/artifact-bus-message.example.json` to a real typed artifact ID (e.g., `MMR-2026-0317-001`) and update tests | Phase 2 |
| `docs/examples/artifact-bus-message.example.json` | `artifact_id: "ART-MINUTES-2026-0317-001"`, `run_id: "RUN-MEET-EVAL-2026-0317-001"` | Non-conforming to canonical standard after Phase 2 schema change | Update to `"MMR-2026-0317-001"` and `"run-20260317T140000Z"` respectively | **Yes** | N (this is the fixture itself) | Phase 2 |
| `tests/test_orchestration_boundaries.py` | `_minimal_valid_bus_message()` — `artifact_id: "ART-TEST-001"`, `run_id: "RUN-TEST-001"` | Test helper will fail schema validation after Phase 2 | Update helper to use `"MMR-TEST-001"` and `"run-20260318T000000Z"` | **Yes** | N (tests are being updated, not added) | Phase 2 |

### Phase 3 — Action ID normalization and legacy cleanup (breaking)

| Schema/file path | Current field(s) | Problem | Change required | Breaking? | Fixture/test update? | Migration phase |
|---|---|---|---|---|---|---|
| `contracts/schemas/next_best_action_memo.schema.json` | `action_id: ^NBA-[A-Z0-9._-]+$` in `$defs.action` | `NBA-` entity prefix collides with `NBA-MEMO-` artifact prefix; action entities must use `ACT-` | Change pattern to `^ACT-[A-Z0-9][A-Z0-9._-]*$` | **Yes** — existing NBA memo examples use `NBA-001`, `NBA-002` | **Y** — update `contracts/examples/next_best_action_memo.json` | Phase 3 |
| `contracts/examples/next_best_action_memo.json` | `action_id: "NBA-001"`, `"NBA-002"` | Non-conforming under new `ACT-` rule | Change to `"ACT-001"`, `"ACT-002"` | **Yes** | N (this is the fixture itself) | Phase 3 |
| `schemas/provenance-schema.json` | `record_id: ^PRV-[A-Z0-9._-]+$` | Field named `record_id` uses `PRV-` prefix, which conflicts with the governed `record_id: ^REC-` convention; the `PRV-` value is actually an artifact ID for a provenance document; this schema pre-dates the governed contracts layer and duplicates `contracts/schemas/provenance_record.schema.json` | **Deprecate** this schema: add a `deprecated` notice to its `description` and a top-level `"x-deprecated": "Use contracts/schemas/provenance_record.schema.json"` annotation. Do not rename the field; the schema is being retired, not corrected. All consumers must be migrated to the governed schema before the file is removed. | **Yes** (consumers must migrate) | Y — audit all consumers of `schemas/provenance-schema.json` before deprecation notice is added; list consumers in the BUILD prompt | Phase 3 |
| `schemas/review-artifact.schema.json` | `review_id: ^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$` | Date-based slug format conflicts with `contracts/` `^REV-[A-Z0-9._-]+$` convention | Change to `^REV-[A-Z0-9][A-Z0-9._-]*$` or deprecate in favour of `contracts/review-output.schema.json` | **Yes** | Y — update any examples or tests using date-slug review IDs | Phase 3 |
| `docs/review-actions/action-tracker-template.md` | Plain `"id"` labels (`F-1`, `A-1`, etc.) | New review action files should use typed field names (`finding_id`, `action_id`) to enable programmatic consumption | Update template to use typed field names for new files; do not retroactively migrate existing files | No (template only; new files onward) | N | Phase 3 |

---

## Enforcement Spine

### Schemas
- Add `pattern` constraints to all 16 entity ID fields listed in Phase 1. This is the primary
  enforcement mechanism. No other change is needed for Phase 1 correctness.
- Update `schemas/artifact-bus-message.schema.json` for Phase 2 (two pattern changes).
- Update `contracts/schemas/next_best_action_memo.schema.json` for Phase 3 (one pattern change).

### Validators
- No new validator infrastructure is required for Phase 1 or 2. The existing JSON Schema validation
  (jsonschema library, used in `tests/test_orchestration_boundaries.py` and related tests) covers
  all pattern enforcement automatically once schemas are updated.
- For Phase 3 and beyond: a single Python script `scripts/validate_id_patterns.py` that scans
  `contracts/examples/` and validates all `*_id`-named fields against their schema-declared patterns
  provides a standing drift-detection check. This script is useful before any checkpoint bundle but
  is not required to unblock Phase 1 or 2.

### Tests
- **Phase 2 required test updates** (not additions; updates to existing tests):
  - `tests/test_orchestration_boundaries.py`: update `_minimal_valid_bus_message()` to use a
    typed artifact ID and canonical run ID format. Update any negative test that uses `RUN-bad` to
    use a format that is genuinely invalid under the new `^run-[0-9]{8}T[0-9]{6}Z$` pattern
    (e.g., `run-bad` which lacks the timestamp body).
- **Phase 1 optional test additions** (recommended, not blocking):
  - Add negative schema validation tests for at least `decision_id` and `action_id` in
    `meeting_minutes_record` to confirm the new patterns reject non-conforming values.

### Registry and review surfaces
- No new registry infrastructure is required. The existing `contracts/artifact-class-registry.json`
  does not need to change for ID format enforcement.
- Review manifests (`scope_id` slugs) are explicitly exempt and do not need to be updated.
- The `docs/review-actions/action-tracker-template.md` update is the only review surface change,
  and it applies only to new files created after the template is updated.

### Utilities
- One utility script: `scripts/validate_id_patterns.py` (Phase 3 target; not required for Phases
  1 or 2). Scans example JSON files in `contracts/examples/`, loads the corresponding schema, and
  validates all `*_id` fields against their declared `pattern`. Emits a machine-readable JSON
  report with any violations. This script must not be written before Phase 2 is complete, to avoid
  testing against not-yet-updated schemas.

---

## Remaining Risks

1. **`schemas/provenance-schema.json` consumer audit is not yet complete.** Before renaming
   `record_id` to `artifact_id` in that schema (Phase 3), every consumer of that schema must be
   identified. If `shared/` Python modules or pipeline scripts reference `record_id` by name,
   renaming the field will cause silent runtime failures. This is the highest-risk single change in
   the plan. Mitigation: run a grep for `record_id` across all `.py`, `.json`, and `.yaml` files
   before applying Phase 3.

2. **Bus example and test fixtures use non-conforming IDs that must be coordinated.** The
   `docs/examples/artifact-bus-message.example.json` file, the `_minimal_valid_bus_message()`
   helper in `tests/test_orchestration_boundaries.py`, and the schema itself all need to change
   together in Phase 2. If any one of these is updated without the others, tests will fail. The
   three-file change must be atomic within a single commit.

3. **`work_item_id` numeric format is not addressed in this plan.** The `^WI-[0-9]{4}$` pattern
   limits the namespace and diverges from all other entity IDs, but changing it would invalidate
   existing work items. This is deferred to a future v2 migration. If the work item count
   approaches 9999 before that migration, the constraint becomes urgent.

---

## Implementation Readiness

- **Verdict:** READY FOR BUILD WITH 2 NAMED PRECONDITIONS

- **Preconditions:**

  1. **Phase 3 only — consumer audit required before applying.** Before any Phase 3 schema change
     (NBA → ACT rename, `provenance-schema.json` `record_id` rename, `review-artifact.schema.json`
     review_id change), run a repository-wide grep to identify all consumers of those specific
     fields. Document the consumer list as a comment in the BUILD prompt. Phase 1 and Phase 2 may
     proceed without this audit.

  2. **Phase 2 only — atomic bus change required.** The three files that must change together in
     Phase 2 (`schemas/artifact-bus-message.schema.json`, `docs/examples/artifact-bus-message.example.json`,
     `tests/test_orchestration_boundaries.py`) must be updated in a single commit. The BUILD prompt
     for Phase 2 must declare all three files explicitly in its declared-files list.

- **Phase 1 has no preconditions and may proceed immediately.** All 16 pattern additions in Phase
  1 are non-breaking and do not affect any existing valid example or test.
