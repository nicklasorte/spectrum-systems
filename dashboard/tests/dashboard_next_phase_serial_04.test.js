const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

function read(rel) {
  return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8')
}

const PANEL_IDS = [
  'operator_coordination_layer',
  'decision_change_conditions',
  'evidence_gap_hotspots',
  'override_hotspots',
  'trust_posture_timeline',
  'judge_disagreement',
  'policy_regression',
  'capability_readiness',
  'route_efficiency',
  'failure_derived_eval',
  'correction_patterns',
  'review_outcomes',
  'escalation_triggers',
  'cross_run_intelligence',
  'high_risk_claim_board',
  'governed_exports'
]

test('serial-04 contract/capability/provenance declare all new coordination panels', () => {
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

test('serial-04 compiler wires ranking, fail-closed and read-only boundaries', () => {
  const compiler = read('lib/read_model/dashboard_read_model_compiler.ts')
  assert.ok(compiler.includes("blocked('decision_change_conditions'"))
  assert.ok(compiler.includes("blocked('evidence_gap_hotspots'"))
  assert.ok(compiler.includes('materiality_score'))
  assert.ok(compiler.includes('approaching_threshold_only'))
  assert.ok(compiler.includes('decision_artifact_separate'))
  assert.ok(compiler.includes('projection_only'))
  assert.ok(compiler.includes('no inference from partial data'))
  assert.ok(compiler.includes("panelId: 'operator_coordination_layer'"))
})

test('serial-04 required review/repair/delivery/handoff artifacts exist', () => {
  const requiredDocs = [
    '../../docs/reviews/dashboard_next_phase_serial_04_red_team_01.md',
    '../../docs/reviews/dashboard_next_phase_serial_04_repair_01.md',
    '../../docs/reviews/dashboard_next_phase_serial_04_red_team_02.md',
    '../../docs/reviews/dashboard_next_phase_serial_04_repair_02.md',
    '../../docs/reviews/dashboard_next_phase_serial_04_delivery.md',
    '../../docs/reviews/dashboard_next_phase_serial_04_fix_handoff.md'
  ]

  for (const rel of requiredDocs) {
    const abs = path.join(__dirname, rel)
    assert.ok(fs.existsSync(abs), `missing required artifact: ${rel}`)
    const body = fs.readFileSync(abs, 'utf8')
    assert.ok(body.length > 40, `artifact is unexpectedly empty: ${rel}`)
  }
})
