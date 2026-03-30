# Spectrum Systems — System Roadmap (Operational Compatibility Mirror)

**Compatibility status:** REQUIRED OPERATIONAL MIRROR

- Active editorial roadmap authority: `docs/roadmaps/system_roadmap.md`
- This file remains required for backward-compatible operational parsing and test/runtime compatibility until PQX consumers migrate off `docs/roadmap/system_roadmap.md`.
- If content diverges, the editorial source of truth is `docs/roadmaps/system_roadmap.md`; this mirror must be updated in lockstep to remain parseable.
- Bridge metadata (B2): PQX execution authority resolution is declared in `docs/roadmaps/roadmap_authority.md`; this file is the resolved machine-executable roadmap surface during migration.

## PQX Execution Contract Standard

Roadmap rows are expected to follow:
`docs/roadmap/roadmap_step_contract.md`

Slice specs live under:
`docs/roadmap/slices/`

## Compatibility Roadmap Table

| Step ID | Step Name | What It Builds | Why It Matters | Source Basis | Existing Repo Seams | Implementation Mode | Contracts / Schemas | Artifact Outputs | Integration Points | Control Loop Coverage | Dependencies | Definition of Done | Prompt Class | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AI-01 | AI request/response boundary | Governed model IO boundary + prompt registry enforcement | Prevents free-form model calls on governed paths | SOURCE + REPO | `spectrum_systems/modules/runtime/model_adapter.py`, `spectrum_systems/modules/runtime/prompt_registry.py` | MODIFY EXISTING | `ai_model_request`, `ai_model_response` | `ai_model_request`, `ai_model_response` | runtime adapter | O / I | — | All governed model calls use schema-valid request/response and registry controls | runtime | VALID |
| AI-02 | Context bundle system | Deterministic, provenance-bound context input boundary | Ensures grounded and replayable execution | SOURCE + REPO | `spectrum_systems/modules/runtime/context_bundle.py` | MODIFY EXISTING | `context_bundle.schema.json` | `context_bundle` | runtime input layer | O / I | AI-01 | Context bundles validate and fail closed on missing required context | schema | VALID |
| TRUST-01 | Context admission gate | Pre-execution fail-closed admission decision | Blocks invalid or unsafe context before execution | SOURCE + REPO | `spectrum_systems/modules/runtime/context_admission.py` | MODIFY EXISTING | `context_admission_decision.schema.json` | `context_admission_decision` | pre-execution gate | O / I / D / E | AI-02 | Invalid context is blocked with governed admission artifact | governance | VALID |
| SRE-03 | Replay engine | Deterministic replay and replay-governed decision seam | Preserves reproducibility and trust debugging | SOURCE + REPO | `spectrum_systems/modules/runtime/replay_engine.py`, `replay_governance.py` | MODIFY EXISTING | `replay_result.schema.json` | `replay_result`, `replay_execution_record` | runtime + PQX seams | O / I / D / L | TRUST-01 | Replay outcomes are deterministic for same governed inputs | runtime | VALID |
| GOV-10 | Certification gate | Governed done/trust certification boundary | Prevents false completion claims | SOURCE + REPO | `contracts/schemas/done_certification_record.schema.json`, prompt queue certification seams | MODIFY EXISTING | `done_certification_record`, `prompt_queue_certification_record` | certification records | promotion + queue completion gates | I / D / E | SRE-03 | Completion/trust requires certification artifact | governance | VALID |
| CTRL-LOOP-01 | Autonomous execution loop foundation | Cycle manifest + runner + review/fix/cert seams | Establishes deterministic artifact-first control-plane progression with fail-closed gates | SOURCE + REPO | `spectrum_systems/orchestration/cycle_runner.py`, `spectrum_systems/fix_engine/generate_fix_roadmap.py`, `contracts/schemas/cycle_manifest.schema.json` | ADD NEW + MODIFY EXISTING | `cycle_manifest`, `roadmap_review_artifact`, `execution_report_artifact`, `implementation_review_artifact`, `fix_roadmap_artifact` | cycle manifest, roadmap review, implementation reviews, fix roadmap, certification handoff request | orchestration + PQX seam + GOV-10 seam | O / I / D / E / L | GOV-10 | Runner blocks on missing artifacts; roadmap approval required before execution; certification artifact required for done | governance | VALID |
