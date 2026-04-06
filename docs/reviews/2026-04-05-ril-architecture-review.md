# RIL Architecture Review — 2026-04-05

## Review Metadata
- **review date:** 2026-04-05
- **scope:** RIL-01 through RIL-04 (parser → classifier → integration packet → projection adapter)
- **reviewer:** Codex
- **files/surfaces inspected:**
  - `spectrum_systems/modules/runtime/review_parsing_engine.py` (RIL-01 parser)
  - `spectrum_systems/modules/runtime/review_signal_classifier.py` (RIL-02 classifier)
  - `spectrum_systems/modules/runtime/review_signal_consumer.py` (RIL-03 integration packet consumer)
  - `spectrum_systems/modules/runtime/review_projection_adapter.py` (RIL-04 projection adapter)
  - `contracts/schemas/review_signal_artifact.schema.json`
  - `contracts/schemas/review_control_signal_artifact.schema.json`
  - `contracts/schemas/review_integration_packet_artifact.schema.json`
  - `contracts/schemas/roadmap_review_projection_artifact.schema.json`
  - `contracts/schemas/control_loop_review_intake_artifact.schema.json`
  - `contracts/schemas/readiness_review_projection_artifact.schema.json`
  - `contracts/schemas/review_projection_bundle_artifact.schema.json`
  - `contracts/examples/review_signal_artifact.json`
  - `contracts/examples/review_control_signal_artifact.json`
  - `contracts/examples/review_integration_packet_artifact.json`
  - `contracts/examples/roadmap_review_projection_artifact.json`
  - `contracts/examples/control_loop_review_intake_artifact.json`
  - `contracts/examples/readiness_review_projection_artifact.json`
  - `contracts/examples/review_projection_bundle_artifact.json`
  - `tests/test_review_parsing_engine.py`
  - `tests/test_review_signal_classifier.py`
  - `tests/test_review_signal_consumer.py`
  - `tests/test_review_projection_adapter.py`

## 1. Overall Assessment
**Call: conditionally sound**

RIL-01 through RIL-04 currently form a coherent deterministic review-intelligence spine with strong schema gating, explicit provenance fields, and replay-stable IDs/orderings. The subsystem is close to a safe downstream intake boundary.

However, three bounded risks remain before treating RIL as fully trusted intake authority:
1. **Classification policy leakage risk (RIL-02):** classification relies on keyword/heuristic semantics that can drift into hidden policy behavior if expanded without governance controls.
2. **Schema coupling weakness in bundle contract (RIL-04):** the top-level bundle schema does not strongly type nested projection objects, reducing fail-closed strength at the final aggregation boundary.
3. **Runtime contract gap in parser (RIL-01):** parser output is not schema-validated inside the parser before return, unlike RIL-02/03/04.

Net: safe enough for controlled downstream intake **if** consumers treat outputs as non-authoritative signals and the above hardening items are completed.

## 2. Critical Risks (Ranked)
1. **No current critical architecture break found.**

I did not find a direct write/enforcement mutation path in RIL-01..04, nor an immediate fail-open defect that turns malformed artifacts into accepted outputs in the reviewed golden path and fail-closed tests.

## 3. Structural Weaknesses
1. **RIL-02 classification semantics are partly heuristic and policy-adjacent.**
   - `_signal_rules_for_item()` uses lexical triggers (`"block"`, mentions of `tpa/pqx/control`, recovery token matching, reason-code checks) to emit classes like `enforcement_block` and `control_escalation`.
   - This is deterministic but is also a latent policy surface if not tightly versioned and governance-reviewed.

2. **RIL-04 bundle schema under-specifies nested projections.**
   - `review_projection_bundle_artifact` accepts nested projection fields as generic `object` rather than binding them to specific projection schemas.
   - Adapter currently validates nested projections before bundling, but contract-level fail-closed guarantees are weaker than they should be.

3. **RIL-01 parser does not self-validate against `review_signal_artifact` schema at runtime.**
   - RIL-02/03/04 all schema-validate their inputs/outputs internally.
   - RIL-01 depends on tests and downstream validation rather than enforcing output contract conformance before emitting artifact.

## 4. Read-Only Boundary Assessment
**Call: read-only boundary preserved (with semantic caution).**

- No reviewed RIL layer writes to governance state, mutates external policy, or emits enforcement commands.
- RIL-03 produces bounded routing inputs only; RIL-04 produces projections and bundle artifacts only.
- Artifacts are marked as coordination/projection surfaces with provenance passthrough.

Caution:
- Labels such as `enforcement_block`, `control_escalation`, and `blocker_related` are semantically strong and could be over-interpreted downstream as decisions.
- This is not currently an implementation enforcement breach, but a **consumer misuse hazard** if contract language does not explicitly enforce non-authoritative handling.

## 5. Provenance Continuity Assessment
**Call: strong continuity, end to end.**

Traceability chain is present and usable:
- RIL-01 emits per-item trace (`source_path`, `line_number`, `source_excerpt`) plus source content hashes.
- RIL-02 retains source item linkage (`source_item_id`) and passes trace refs into classified signals.
- RIL-03 maps each classified signal into deterministic intake inputs with `source_signal_id` and preserved trace refs.
- RIL-04 maps each projected item to `source_input_id`, preserves trace refs, and carries source packet/provenance hashes into each projection and bundle.

This is sufficient for reverse lineage from projection item back to classified signal and originating review/action row.

## 6. Layer Separation Assessment
**Call: mostly clean separation with one watchpoint.**

- **RIL-01 parsing:** review/action extraction and normalization.
- **RIL-02 classification:** mapping review items into bounded signal classes.
- **RIL-03 packaging/routing:** deterministic channel routing from class to integration inputs.
- **RIL-04 projection:** read-only projection shaping and aggregation.

Watchpoint:
- Some classification logic in RIL-02 embeds domain interpretation that may evolve into policy-like semantics (e.g., escalation inference from lexical cues). This is still in-scope for classification, but must remain constrained and versioned.

## 7. Determinism / Replay Assessment
**Call: good deterministic posture.**

Strengths:
- Stable deterministic IDs via deterministic payload-based seeds across RIL-02/03/04.
- Stable sorting before ID generation and output emission.
- `emitted_at` propagation from source artifacts avoids runtime-now drift.
- Tests explicitly assert deterministic replay for each layer.

Residual determinism caveat:
- RIL-01 hashes include source path along with content for provenance hash basis; identical content under different paths intentionally yields different identity. This is deterministic but path-sensitive and should be documented as intended behavior.

## 8. Projection Usefulness Assessment
**Call: projections are useful enough for intake boundary, with bounded hardening needs.**

- **Roadmap projection:** priority/severity/rationale/trace and summary fields are sufficient for backlog triage intake.
- **Control-loop intake projection:** queue-ready shape with intake type, priority, blocker flags, and trace refs is operationally usable.
- **Readiness projection:** aggregate counts plus per-item lineage and rationale support readiness dashboards.
- **Bundle artifact:** useful for single-object handoff across consumers.

Needed hardening:
- Strengthen bundle schema typing so intake consumers can rely on contract-level validation of nested projection shapes.

## 9. Hidden Authority Assessment
**Call: still bounded intelligence layer, not yet an authority surface.**

Current status:
- RIL does not execute enforcement or mutate policy.
- Routing and projection are bounded and deterministic.
- Provenance remains explicit.

Risk vector to monitor:
- If downstream systems start treating `enforcement_block` and `control_escalation` as direct gate decisions (without independent control authority checks), RIL can become de facto authority through coupling.
- The architecture today permits safe usage, but safety depends on non-authoritative consumption discipline.

## 10. Recommended Fixes (Rack and Stack)
### Fix now
1. **Schema-tighten `review_projection_bundle_artifact` nested projection fields** to reference concrete projection schemas (or `$defs` with equivalent strict structure) instead of generic `object`.
2. **Add runtime output schema validation in RIL-01 parser** before return to align fail-closed behavior with RIL-02/03/04.

### Fix next
3. **Add explicit classifier governance guardrails**: versioned classification-rules policy and change-review gate for `_signal_rules_for_item()` behavior changes.
4. **Add a non-authoritative consumption clause** in projection/intake contract notes to prevent treating RIL outputs as direct decisions.

### Monitor only
5. **Path-sensitive identity behavior** (source-path included in provenance hash basis): monitor for cross-environment replay confusion; retain if intentional.

## 11. What NOT to Change
- Do **not** collapse RIL-01..04 into a single module; current separation is clean and audit-friendly.
- Do **not** remove deterministic ID generation or stable sorting; this is core replay safety.
- Do **not** strip trace refs to “simplify” artifacts; provenance density is a key trust property.
- Do **not** move RIL into enforcement ownership; keep it read-only intelligence packaging.

## 12. Long-term Risk Register
### Top 3 unsafe evolution risks
1. **Classifier drift into policy engine:** expanding lexical heuristics into implicit decision logic without governance.
2. **Consumer authority inversion:** downstream gates treating RIL control labels as enforcement decisions.
3. **Contract loosening at bundle boundary:** generic object acceptance enabling malformed nested projections to pass intake checks.

### Top 3 bureaucracy/noise risks
1. **Signal-class proliferation** without bounded value tests, creating noisy intake queues.
2. **Over-enrichment of projection payloads** that duplicate upstream control-plane semantics.
3. **Too many routing variants** that increase operational interpretation burden without better outcomes.

### Top 3 silent trust-loss risks
1. **Unversioned classifier rule changes** causing behavior drift without visible governance signal.
2. **Trace quality degradation** (empty or low-value source excerpts) while artifacts remain schema-valid.
3. **Cross-environment identity surprises** from path-sensitive hashes/IDs being interpreted as semantic changes.
