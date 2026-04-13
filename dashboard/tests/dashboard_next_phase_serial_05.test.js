const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

function read(rel) {
  return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8')
}

const PANEL_IDS = [
  'trust_posture_artifact_browser', 'trust_posture_diff', 'capability_readiness_timeline', 'capability_expansion_blockers',
  'improvement_recommendation', 'improvement_recommendation_outcomes', 'artifact_family_health', 'artifact_family_health_trend',
  'evidence_coverage_density', 'evidence_sufficiency_change', 'judge_calibration', 'judge_drift', 'human_correction_magnitude',
  'correction_absorption', 'policy_deviation', 'policy_change_impact', 'route_distribution', 'quality_vs_cost', 'latency_vs_quality',
  'retry_validation_failure', 'prompt_version_impact', 'context_recipe_comparison', 'context_source_reliability', 'context_exclusion_rationale',
  'contradiction_type', 'cross_artifact_consistency', 'schema_drift', 'provenance_coverage', 'lineage_coverage', 'trace_integrity',
  'openlineage_trace_correlation', 'run_bundle_audit', 'promotion_readiness', 'promotion_failure', 'certification_failure',
  'replay_mismatch_root_cause', 'replay_stability', 'non_determinism_hotspot', 'error_budget_burn', 'budget_breach_history',
  'incident_correlation', 'alert_quality', 'review_queue_load', 'review_queue_routing_quality', 'review_debt', 'review_to_eval_closure',
  'hitl_override_quality', 'human_review_reason', 'decision_log_integrity', 'decision_alternative', 'decision_fragility',
  'counterfactual_study_index', 'route_canary', 'model_tournament', 'slice_severity', 'missing_eval_slice', 'blocking_bottleneck',
  'roadmap_feed', 'control_vs_roadmap_split', 'human_review_consumption', 'quality_sli', 'reliability_sli', 'capacity_cost_sli',
  'time_to_insight', 'link_integrity', 'dashboard_self_health', 'operator_session_path', 'cognitive_load',
  'panel_materiality_ranking', 'panel_retirement_candidate', 'certification_gate_reinforcement'
]

test('serial-05 contract/capability/provenance include all dashboard-next-75 surfaces', () => {
  const registry = read('lib/contracts/surface_contract_registry.ts')
  const capabilities = read('lib/contracts/panel_capability_map.ts')
  const provenance = read('lib/provenance/field_provenance.ts')

  for (const id of PANEL_IDS) {
    assert.ok(registry.includes(`panel_id: '${id}'`), `registry missing ${id}`)
    assert.ok(capabilities.includes(`panel_id: '${id}'`), `capability map missing ${id}`)
    assert.ok(provenance.includes(`panel_id: '${id}'`), `provenance map missing ${id}`)
  }

  assert.ok(!capabilities.includes("decision_authority: 'write'"))
})

test('serial-05 compiler preserves fail-closed, uncertainty and abstention behavior', () => {
  const compiler = read('lib/read_model/dashboard_read_model_compiler.ts')
  assert.ok(compiler.includes('SERIAL_05_PANEL_BINDINGS'))
  assert.ok(compiler.includes('explicit_uncertainty'))
  assert.ok(compiler.includes('insufficient governed materiality evidence'))
  assert.ok(compiler.includes("panelId: panel.panelId"))
})

test('serial-05 review artifacts exist', () => {
  const requiredDocs = [
    '../../docs/reviews/dashboard_next_75_serial_05_red_team_01.md',
    '../../docs/reviews/dashboard_next_75_serial_05_repair_01.md',
    '../../docs/reviews/dashboard_next_75_serial_05_red_team_02.md',
    '../../docs/reviews/dashboard_next_75_serial_05_repair_02.md',
    '../../docs/reviews/dashboard_next_75_serial_05_delivery.md',
    '../../docs/reviews/dashboard_next_75_serial_05_fix_handoff.md'
  ]

  for (const rel of requiredDocs) {
    const abs = path.join(__dirname, rel)
    assert.ok(fs.existsSync(abs), `missing required artifact: ${rel}`)
    const body = fs.readFileSync(abs, 'utf8')
    assert.ok(body.length > 40, `artifact is unexpectedly empty: ${rel}`)
  }
})
