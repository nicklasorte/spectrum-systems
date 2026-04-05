---
module: fre
review_type: architecture_governance_review
review_date: 2026-04-05
reviewer: Codex
decision: FAIL
trust_assessment: NO
status: open
related_plan: docs/review-actions/PLAN-BATCH-FRE-03-2026-04-05.md
---

# FRE Recovery System Review — 2026-04-05

## Review Metadata
- **review date:** 2026-04-05
- **scope:** FRE-01 through FRE-03 (failure diagnosis → repair prompt → bounded recovery orchestration)
- **reviewer:** Codex
- **files/surfaces inspected:**
  - `contracts/schemas/failure_diagnosis_artifact.schema.json`
  - `contracts/schemas/repair_prompt_artifact.schema.json`
  - `contracts/schemas/recovery_result_artifact.schema.json`
  - `contracts/examples/failure_diagnosis_artifact.json`
  - `contracts/examples/repair_prompt_artifact.json`
  - `contracts/examples/recovery_result_artifact.json`
  - `contracts/standards-manifest.json`
  - `spectrum_systems/modules/runtime/failure_diagnosis_engine.py`
  - `spectrum_systems/modules/runtime/repair_prompt_generator.py`
  - `spectrum_systems/modules/runtime/recovery_orchestrator.py`
  - `scripts/build_failure_diagnosis_artifact.py`
  - `tests/test_failure_diagnosis_engine.py`
  - `tests/test_repair_prompt_generator.py`
  - `tests/test_recovery_orchestrator.py`
  - `docs/review-actions/PLAN-BATCH-FRE-01-2026-04-05.md`
  - `docs/review-actions/PLAN-BATCH-FRE-02-2026-04-05.md`
  - `docs/review-actions/PLAN-BATCH-FRE-03-2026-04-05.md`

## 1. Overall Assessment
**Verdict: conditionally sound.**

FRE has the right architectural spine (artifact-first, deterministic transforms, schema validation, explicit statuses), but it is **not yet safe enough to declare canonical recovery spine without caveats**.

What is strong:
- FRE-01 is deterministic and fail-closed on missing machine-readable intake evidence.
- FRE-02 keeps generation bounded to diagnosis-linked templates, constraints, and explicit validation commands.
- FRE-03 enforces one-attempt-per-call semantics and explicit retry budgeting via `recovery_attempt_number` + `max_attempts`.

What blocks full trust:
- FRE-03 cannot emit a valid blocked artifact when retry budget is exhausted because generated payload shape violates its own schema requirements.
- FRE-02 template coverage does not span all diagnosis root causes emitted by FRE-01, creating a hard fail-closed stall for several classes.
- Governance subordination remains largely by convention/integration (execution runner contract) rather than a strongly asserted runtime gate inside FRE-03.

## 2. Critical Risks (Ranked)
1. **Retry-budget exhaustion path is structurally broken (P0).**
   When `recovery_attempt_number > max_attempts`, FRE-03 builds empty `execution_artifact_refs` and empty `validation_results`, then validates against schema requiring non-empty arrays. Result: fail-fast exception instead of a canonical `blocked` recovery artifact. This breaks bounded recovery loop closure and replay continuity at exactly the key stop condition.

2. **Diagnosis→repair bridge is incomplete for legal FRE-01 outputs (P0).**
   FRE-01 can emit root causes such as `fixture_gap`, `certification_surface_gap`, `source_authority_anchor_gap`, `policy_composition_gap`, and `unknown_failure_class`; FRE-02 has no templates for these and hard-fails generation. This is fail-closed (good) but operationally creates deterministic dead-ends in the canonical loop.

3. **Governance gate reliance is externalized (P1).**
   FRE-03 delegates recovery execution authority to caller-provided `execution_runner` and does not independently require control/preflight/certification gate evidence before execution. This keeps FRE modular, but it leaves a path where weak integration can make FRE appear governed while actually under-enforced.

## 3. Structural Weaknesses
- **Conditional determinism via implicit timestamp defaults.** If callers do not pin `emitted_at`, artifacts include dynamic wall-clock timestamps (`_utc_now()`), so byte-for-byte replay equality is not guaranteed by default.
- **Status evidence granularity is coarse on unresolved outcomes.** `remaining_failure_classes` collapses unresolved state to primary root cause only, which is deterministic but can be too lossy for precise next-cycle triage in multi-symptom failures.
- **FRE runtime entrypoints are asymmetric.** FRE-01 has a dedicated CLI (`build_failure_diagnosis_artifact.py`), while FRE-02/FRE-03 do not expose equivalent thin CLIs in this slice, reducing operational consistency for governed invocation.

## 4. Boundedness Assessment
**Partially bounded.**

Strong controls:
- Single-attempt orchestration per invocation.
- Explicit attempt counters and stop condition semantics.
- Retry recommendation limited to `failed | partially_recovered` and disabled when attempt budget is exhausted.

Gap:
- The budget-exhaustion branch cannot produce a valid terminal artifact due to schema conflict. This undermines bounded-loop closure evidence.

## 5. Separation-of-Concerns Assessment
**Mostly clean separation.**

- FRE-01 remains diagnosis-only; no repair execution behavior.
- FRE-02 remains prompt-generation-only; no mutation/execution authority.
- FRE-03 remains orchestration + classification; no hidden diagnosis logic.

Noted coupling pressure:
- FRE-03 auto-generates repair prompts if absent, which is useful but increases runtime coupling between FRE-02 and FRE-03 failure domains.

## 6. Recovery Status Integrity
**Trustworthy in normal paths, but incomplete at the retry ceiling edge.**

- Status transitions are explicit and deterministic based on execution status + validation summary.
- `recovered/partially_recovered/blocked/failed` mapping is mechanically clear.
- Missing/malformed inputs are rejected fail-closed.

Integrity break:
- Retry-budget exhaustion cannot be represented as a valid persisted artifact because of schema/implementation mismatch in required evidence arrays.

## 7. Determinism / Replay Assessment
**Strong with pinned timestamps; conditional otherwise.**

Deterministic properties present:
- Stable sorting and canonical hashing for IDs.
- Explicit rule precedence in diagnosis.
- Fixed status classifier semantics in orchestration.

Replay caveats:
- Unpinned `emitted_at` introduces time variance.
- Absence of full template coverage makes some valid diagnosis inputs unreplayable through the complete FRE loop.

## 8. Governance Boundary Assessment
**Subordinate by design intent, not fully self-enforcing in FRE-03 runtime contract.**

Positive:
- Contracts and notes explicitly position FRE as governed and non-authoritative.
- Fail-closed schema validation is pervasive.

Concern:
- FRE-03 accepts any execution runner contractually returning allowed fields/statuses; it does not require explicit proof that control/preflight/certification gates were evaluated before execution.

## 9. Recommended Fixes (Rack and Stack)
### Fix now
1. **Repair FRE-03 retry-budget-exhausted artifact path.** Ensure blocked terminal artifacts always satisfy schema (non-empty execution evidence strategy + validation evidence semantics aligned with schema).
2. **Close FRE-02 root-cause template gaps or define explicit governed fallback contract.** Every FRE-01 `primary_root_cause` must map to a deterministic FRE-02 outcome (template or structured manual-triage artifact).
3. **Add governance-evidence requirement to FRE-03 execution contract.** Require execution runner output to include explicit gate evidence references (preflight/control/certification) when execution is attempted.

### Fix next
1. Add richer unresolved-state encoding beyond primary-only `remaining_failure_classes` where validation shows mixed unresolved symptoms.
2. Add thin governed CLI entrypoints for FRE-02 and FRE-03 for operational parity with FRE-01.
3. Add explicit tests for retry-budget exhaustion artifact emission and re-entry artifact sufficiency.

### Monitor only
1. Distribution of FRE-01 root causes that currently lack FRE-02 templates.
2. Ratio of `blocked` outcomes caused by governance vs validation to detect policy friction drift.
3. Frequency of runs using implicit timestamps vs pinned emitted timestamps.

## 10. What NOT to Change
- Do **not** remove fail-closed behavior on missing diagnosis evidence in FRE-01.
- Do **not** loosen schema constraints to make malformed recovery artifacts pass.
- Do **not** replace deterministic rule precedence with heuristic/LLM-only classification.
- Do **not** turn FRE-02 into free-form autonomous repair planning.
- Do **not** collapse diagnosis/prompt/orchestration layers into one mixed subsystem.
- Do **not** let FRE become a parallel authority that bypasses control surfaces.

## 11. Long-term Risk Register (Requested)

### Top 3 ways FRE could become unsafe
1. Governance evidence becomes optional at execution handoff, allowing “governed-looking” but ungoverned repairs.
2. Template drift causes over-broad prompts that mutate beyond diagnosis boundaries.
3. Retry loops are optimized for throughput and start skipping explicit blocked/failed artifact emission.

### Top 3 ways FRE could become bureaucratic and slow
1. Excessive mandatory validation command sets grow per template without prioritization.
2. Recovery status taxonomy expands without decision simplification, increasing operator ambiguity.
3. Additional gate artifacts are required without automation for generation/collection.

### Top 3 ways FRE could silently fail while appearing present
1. Retry-budget branch throws and no terminal artifact is persisted, hiding stop-condition outcomes.
2. FRE-02 rejects unsupported root causes, and upstream systems treat absence of prompt as transient noise.
3. Validation runner returns superficially valid statuses while lacking substantive evidence references.
