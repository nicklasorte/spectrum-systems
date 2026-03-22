## BAJ Audit Report — Secondary Paths

### Metadata
- review_date: 2026-03-22
- reviewer: Codex
- scope: BAJ Provenance Audit — Secondary Paths

### Summary
- total_emission_paths: 9
- non_compliant_emission_paths: 7
- mutation_paths_without_revalidation: 3
- replay_parity_issues: 4
- policy_inconsistencies: 4
- trace_continuity_issues: 5

### Findings (Ranked)

1. **severity: P1**
   - **file + function:** `spectrum_systems/modules/strategic_knowledge/provenance.py::build_provenance`
   - **description:** Strategic knowledge provenance is emitted as `{extraction_run_id, extractor_version, notes?}` and does not use `create_provenance_record(...)` or `schemas/provenance-schema.json` validation.
   - **why it breaks BAJ guarantees:** This path emits provenance outside the authoritative baseline and omits `policy_id`, `trace_id`, `span_id`, and `generated_by_version`, making artifacts non-auditable and non-parity with runtime provenance.
   - **minimal fix (1–2 lines):** Replace this builder with a thin wrapper around `shared/adapters/artifact_emitter.create_provenance_record(...)` and hard-fail on schema validation errors.

2. **severity: P1**
   - **file + function:** `spectrum_systems/modules/runtime/replay_engine.py::run_replay` and replay execution path around replay trace normalization
   - **description:** Replay uses fallback trace identifiers (`"unknown-trace"` and UUIDv5 from invalid trace strings) when trace context is missing or malformed.
   - **why it breaks BAJ guarantees:** Replay/rehydration must preserve runtime trace lineage exactly; synthesizing trace IDs severs trace continuity and produces forensic drift that appears valid.
   - **minimal fix (1–2 lines):** Remove synthetic trace fallbacks and fail-closed when `trace_id` is absent/invalid; require UUID-valid trace propagation from source decision and replay validation artifacts.

3. **severity: P1**
   - **file + function:** `spectrum_systems/modules/runtime/enforcement_engine.py::enforce_budget_decision`
   - **description:** Legacy enforcement emits `decision_id` and `trace_id` defaults (`"unknown-decision"`, `"unknown-trace"`) and returns an artifact without shared-emitter provenance enforcement.
   - **why it breaks BAJ guarantees:** Defaulting silently masks missing lineage and allows downstream artifacts to appear complete while losing source identity.
   - **minimal fix (1–2 lines):** Replace default placeholders with explicit `EnforcementError` raises and require validated source `decision_id`/`trace_id` before emission.

4. **severity: P2**
   - **file + function:** `spectrum_systems/modules/runtime/evaluation_monitor.py::build_validation_monitor_record` and `spectrum_systems/modules/runtime/evaluation_control.py::build_evaluation_control_decision`
   - **description:** Both modules emit governed artifacts with fallback `trace_id` values (`"unknown-trace"`) on malformed inputs.
   - **why it breaks BAJ guarantees:** Trace continuity integrity is weakened; malformed upstream artifacts should be blocked, not rewritten with synthetic identifiers.
   - **minimal fix (1–2 lines):** Enforce required non-empty `trace_id` input even for fail-closed decision artifacts; if absent, raise hard error instead of emitting placeholder IDs.

5. **severity: P2**
   - **file + function:** `spectrum_systems/study_runner/artifact_writer.py::write_outputs` (secondary emitted artifacts)
   - **description:** `results.json`, `study_summary.json`, and KML map outputs are written outside shared emitter records and only partial outputs carry provenance; no post-write schema re-validation occurs after enrichment.
   - **why it breaks BAJ guarantees:** Secondary artifacts can be mutated or consumed without canonical provenance guarantees, creating parity gaps between primary and secondary outputs.
   - **minimal fix (1–2 lines):** Emit canonical metadata/provenance records per output artifact via shared emitter and validate enriched payloads after mutation before final write.

6. **severity: P2**
   - **file + function:** `spectrum_systems/modules/runtime/run_output_evaluation.py::build_normalized_run_result`
   - **description:** Provenance for normalized artifacts is reconstructed ad hoc from manifest fragments and file paths, not from authoritative provenance schema builders.
   - **why it breaks BAJ guarantees:** Policy identity and trace/span integrity are not enforced in this emission path, so replay provenance parity with runtime records is incomplete.
   - **minimal fix (1–2 lines):** Introduce required policy/trace/span inputs and compose a canonical provenance record through shared emitter validation before attaching to normalized output.

7. **severity: P3**
   - **file + function:** CLI writers (`scripts/run_evaluation_monitor.py`, `scripts/run_evaluation_budget_governor.py`, `scripts/run_regression_suite.py`)
   - **description:** Tooling persists artifacts directly to JSON files without attaching or verifying canonical provenance metadata at write boundary.
   - **why it breaks BAJ guarantees:** Operational tooling can emit governed artifacts outside governed persistence guarantees, creating blind spots in audit trails.
   - **minimal fix (1–2 lines):** Add a shared write helper that enforces provenance presence and schema validation before disk writes for governed artifact types.

### Top 5 Fixes
1. Migrate strategic knowledge provenance emission to `create_provenance_record(...)` with schema validation and required policy/trace/span fields.
2. Remove all replay trace fallbacks/synthetic trace generation and enforce strict trace continuity for replay + rehydration.
3. Hard-fail legacy enforcement emission when `decision_id` or `trace_id` is missing; eliminate `unknown-*` placeholders.
4. Enforce trace fail-closed behavior in evaluation control/monitor artifacts (no `unknown-trace` output paths).
5. Bring secondary study outputs and runtime tooling writes under shared emitter + post-mutation re-validation.
