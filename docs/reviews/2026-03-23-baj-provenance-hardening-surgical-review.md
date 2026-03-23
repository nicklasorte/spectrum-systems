# BAJ Provenance Hardening — Surgical Implementation Review

- **Date:** 2026-03-23
- **Reviewer:** Codex (GPT-5.2-Codex)
- **Decision:** **FAIL**
- **Scope reviewed:**
  - `spectrum_systems/modules/**/provenance*.py`
  - `spectrum_systems/modules/**/artifact*.py`
  - `spectrum_systems/modules/runtime/`
  - `spectrum_systems/modules/strategic_knowledge/`
  - `contracts/schemas/provenance*.json`
  - tests relevant to provenance emission, artifact creation, replay, and runtime outputs

---

## Critical Findings

### 1) No canonical provenance source-of-truth path is enforced

**What is wrong**
- Provenance is constructed ad hoc across multiple module paths:
  - `strategic_knowledge.provenance.build_provenance`
  - runtime `enforcement_result` builder
  - runtime `replay_result` builder
  - runtime `drift_result` builder
  - runtime normalized run result provenance assembly
- `contracts/schemas/provenance_record.schema.json` exists as a shared contract but is not the universally enforced emitter path.

**Why dangerous**
- Produces multiple provenance dialects that are each locally schema-valid but globally incompatible.
- Breaks deterministic cross-artifact lineage joins and weakens audit/replay trust.

**Location**
- `spectrum_systems/modules/strategic_knowledge/provenance.py`
- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/drift_detection_engine.py`
- `spectrum_systems/modules/runtime/run_output_evaluation.py`
- `contracts/schemas/provenance_record.schema.json`

**Realistic failure scenario**
- An audit reconstructs a replay decision chain and cannot align provenance keys across enforcement/replay/SK artifacts without custom mapping logic, causing ambiguous lineage and non-reproducible governance evidence.

---

### 2) Required provenance field completeness is not consistent across emitters

**What is wrong**
- Provenance payload requirements vary significantly and omit key fields from the hardening objective (e.g., missing `span_id`, parent lineage refs, policy metadata, generator identity/version in many emitted provenance blocks).
- Runtime/replay/drift provenance contracts only require narrow subsets; SK provenance requires only `extraction_run_id` and `extractor_version`.

**Why dangerous**
- Artifacts pass validation while still being semantically weak for chain-of-custody, policy accountability, and generator attribution.

**Location**
- `contracts/schemas/enforcement_result.schema.json`
- `contracts/schemas/replay_result.schema.json`
- `contracts/schemas/drift_result.schema.json`
- `contracts/schemas/story_bank_entry.schema.json` (and SK family peers)
- `spectrum_systems/modules/strategic_knowledge/provenance.py`

**Realistic failure scenario**
- Compliance review asks for policy-version trace and parent lineage for a replay decision; data is missing despite all artifacts being “valid”.

---

### 3) Runtime ↔ replay provenance parity is shape-incompatible

**What is wrong**
- `enforcement_result.provenance` and `replay_result.provenance` use source-artifact pair fields; nested `drift_result.provenance` uses `trace_id/run_id` shape.
- No canonical parity contract guarantees equivalent provenance semantics between runtime and replay outputs.

**Why dangerous**
- Runtime and replay outputs can both validate but remain provenance-incompatible for deterministic comparison and trust scoring.

**Location**
- `contracts/schemas/enforcement_result.schema.json`
- `contracts/schemas/replay_result.schema.json`
- `contracts/schemas/drift_result.schema.json`
- `spectrum_systems/modules/runtime/replay_engine.py`

**Realistic failure scenario**
- Replay says “match/no drift,” but downstream provenance integrity job cannot correlate runtime and replay records due to divergent provenance key shapes.

---

### 4) Strategic Knowledge path is not strictly fail-closed on provenance/trace context

**What is wrong**
- SK validator synthesizes `trace_id` and `span_id` UUIDs when absent rather than hard-failing.
- Missing provenance in SK artifact does not block decision emission; it routes to `require_rebuild` (per current behavior/tests).

**Why dangerous**
- Synthetic trace/span values can sever real lineage continuity.
- Incomplete provenance can continue through system via non-blocking decision artifacts.

**Location**
- `spectrum_systems/modules/strategic_knowledge/validator.py`
- `tests/test_strategic_knowledge_validator.py`

**Realistic failure scenario**
- An ingestion batch loses trace context upstream; SK gate still emits decision records with generated IDs that appear legitimate but cannot be connected to original operational trace.

---

### 5) Legacy enforcement path can emit non-governed artifacts without canonical provenance

**What is wrong**
- `enforce_budget_decision` returns a legacy artifact shape with permissive defaults (`unknown-trace`) and no governed provenance block/schema validation equivalent to canonical `enforcement_result`.

**Why dangerous**
- If called by allowlisted paths, this bypasses canonical provenance guarantees and introduces audit blind spots.

**Location**
- `spectrum_systems/modules/runtime/enforcement_engine.py`

**Realistic failure scenario**
- A legacy caller emits enforcement artifacts during replay/control execution; downstream systems treat them as authoritative despite degraded provenance fidelity.

---

## Required Fixes (minimal, surgical)

1. Introduce one canonical provenance builder/validator utility and route all reviewed emitters through it.
2. Raise provenance minimums in relevant contracts to include at least run/trace/span context, generator identity/version, timestamp, and source/parent references where applicable.
3. Remove SK synthetic trace/span fallback; missing trace context must fail-closed.
4. Gate/retire legacy `enforce_budget_decision` emission unless it emits canonical governed provenance and passes schema validation.
5. Add explicit runtime↔replay provenance parity tests asserting canonical key-level compatibility.

## Optional Improvements

- Add CI check that all provenance-bearing schemas reference a canonical provenance shape or shared definition.
- Add an audit fixture that joins runtime enforcement + replay + drift + SK decisions and fails if provenance key mapping requires ad hoc translation.

## Trust Assessment

**NO**

## Failure Mode Summary

Worst realistic failure: artifacts remain schema-valid while provenance is cross-path incompatible or synthetic, resulting in non-reproducible audit trails and degraded replay trust during incident review.
