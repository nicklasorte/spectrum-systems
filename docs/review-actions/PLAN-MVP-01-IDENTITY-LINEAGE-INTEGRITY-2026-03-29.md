# Plan — MVP-01 Identity & Lineage Integrity — 2026-03-29

## Prompt type
PLAN

## Roadmap item
MVP-01 runtime trust hardening slice (identity + lineage integrity)

## Objective
All artifacts emitted by the MVP-01 agent golden path carry canonical run_id/trace_id and are fully represented in a complete artifact lineage graph rooted at context.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-MVP-01-IDENTITY-LINEAGE-INTEGRITY-2026-03-29.md | CREATE | Required PLAN artifact for multi-file trust hardening change. |
| spectrum_systems/modules/runtime/agent_golden_path.py | MODIFY | Enforce canonical run_id/trace_id propagation and full lineage graph generation/validation for all MVP-01 artifacts. |
| contracts/schemas/grounding_factcheck_eval.schema.json | MODIFY | Require explicit top-level run_id and trace_id on grounding eval artifacts. |
| contracts/schemas/replay_execution_record.schema.json | MODIFY | Add canonical run_id/trace_id requirements and nested consistency shape. |
| contracts/schemas/observability_record.schema.json | MODIFY | Require explicit run_id and trace_id fields. |
| contracts/schemas/control_loop_certification_pack.schema.json | MODIFY | Require explicit run_id and trace_id fields for certification pack identity propagation. |
| contracts/schemas/done_certification_record.schema.json | MODIFY | Require explicit run_id field alongside trace_id. |
| contracts/schemas/done_certification_error.schema.json | MODIFY | Require explicit run_id + trace_id and deterministic error identity when certification fails. |
| contracts/schemas/artifact_lineage.schema.json | MODIFY | Support full graph lineage payload with run_id and trace_id requirements. |
| contracts/schemas/evaluation_enforcement_action.schema.json | MODIFY | Require explicit run_id + trace_id for enforcement bridge outputs. |
| contracts/schemas/meeting_minutes_record.schema.json | MODIFY | Require explicit trace_id to align meeting artifact with canonical execution identity. |
| contracts/examples/grounding_factcheck_eval.json | MODIFY | Keep example schema-valid with required top-level run_id/trace_id. |
| contracts/examples/meeting_minutes_record.example.json | MODIFY | Keep example schema-valid with required trace_id. |
| contracts/examples/replay_execution_record.json | MODIFY | Keep example schema-valid with required canonical run_id/trace_id fields. |
| contracts/examples/observability_record.json | MODIFY | Keep example schema-valid with required run_id/trace_id fields. |
| contracts/examples/control_loop_certification_pack.json | MODIFY | Keep example schema-valid with required run_id/trace_id fields. |
| contracts/examples/done_certification_record.json | MODIFY | Keep example schema-valid with required run_id field. |
| contracts/examples/done_certification_error.json | MODIFY | Keep example schema-valid with required deterministic error identity and explicit run_id/trace_id. |
| contracts/examples/artifact_lineage.json | MODIFY | Keep example schema-valid with full lineage graph shape and required IDs. |
| contracts/standards-manifest.json | MODIFY | Version bumps for updated contracts per contract governance policy. |
| tests/test_agent_golden_path.py | MODIFY | Assert canonical identity consistency and full lineage graph coverage across emitted artifacts. |
| tests/test_contracts.py | MODIFY | Ensure updated contract examples validate with required identity fields. |

## Contracts touched
- grounding_factcheck_eval
- replay_execution_record
- observability_record
- control_loop_certification_pack
- done_certification_record
- artifact_lineage

## Tests that must pass after execution
1. `pytest tests/test_agent_golden_path.py tests/test_contracts.py`
2. `python scripts/run_contract_enforcement.py`
3. `python scripts/run_agent_golden_path.py --task-type meeting_minutes`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not refactor unrelated modules outside MVP-01 golden path identity/lineage boundaries.
- Do not alter prompt-queue or non-MVP runtime orchestration behaviors.
- Do not add new artifact types.

## Dependencies
- Existing AG-01/AG-02 MVP runtime path must remain operational.
- Existing contract loader and schema validation infrastructure must remain unchanged.
