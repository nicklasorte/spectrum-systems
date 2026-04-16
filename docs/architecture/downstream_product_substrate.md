# Downstream Product Substrate (RDM-01)

## Prompt type
BUILD

## Intent
RDM-01 establishes a deterministic transcript-to-product governed substrate where source artifacts, normalized artifacts, intelligence artifacts, product artifacts, eval artifacts, control decisions, and certification readiness are all first-class artifact contracts.

## Architecture seams reused
- Contract authority: `contracts/schemas/*` + `contracts/standards-manifest.json`.
- Deterministic runtime module pattern: `spectrum_systems/modules/runtime/*`.
- Eval/control/certification flow: required eval summary -> control decision -> readiness/certification artifact.

## Added artifact families
### Ingestion and source governance
- `raw_meeting_record_artifact`
- `normalized_transcript_artifact`
- `transcript_chunk_artifact`
- `meeting_context_bundle`

### Facts and meeting intelligence
- `transcript_fact_artifact`
- `meeting_decision_artifact`
- `meeting_action_item_artifact`
- `meeting_risk_artifact`
- `meeting_open_question_artifact`
- `meeting_contradiction_artifact`
- `meeting_gap_artifact`

### Downstream products
- `meeting_intelligence_packet`
- `faq_source_artifact`
- `faq_answer_artifact`
- `working_paper_insert_artifact`
- `decision_log_artifact`
- `product_readiness_artifact`

### Human review and breadth expansion
- `artifact_diff_record`
- `comment_resolution_artifact`
- `study_plan_artifact`

## Fail-closed guarantees
1. Non-DOCX or missing DOCX source artifacts fail closed.
2. Missing trace/run/source identifiers fail closed.
3. Missing required eval suite members block readiness.
4. Indeterminate required evals freeze control decisions.
5. Missing replay linkage, trace completeness, or control allow blocks certification.

## Replay and trace
- All derived artifacts carry `run_id`, `trace_id`, and `lineage_refs`.
- Context bundles include deterministic `manifest_hash` and `replay_token`.

## Control and certification
- Control is externalized: `build_eval_summary` + `control_decision`.
- Certification remains gate-authoritative via `certify_product_readiness` and blocks bypass states.

## Observability and artifact intelligence seam
`build_operability_report` provides deterministic summary outputs for schema pass rate, completeness, evidence coverage, contradiction/override/blocked rates, replay match rate, readiness, cost/latency by artifact family, and review queue volume.
