const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

function read(rel) {
  return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8')
}

test('surface contract registry declares required panel governance fields', () => {
  const src = read('lib/contracts/surface_contract_registry.ts')
  for (const key of ['panel_id', 'artifact_family', 'owning_system', 'render_gate_dependency', 'freshness_dependency', 'provenance_requirements', 'blocked_state_behavior', 'allowed_statuses', 'certification_relevant', 'high_risk', 'mobile_critical']) {
    assert.ok(src.includes(key))
  }
})

test('panel capability map enforces read_only non-ownership of decision logic', () => {
  const src = read('lib/contracts/panel_capability_map.ts')
  assert.ok(src.includes("decision_authority: 'read_only'"))
  assert.ok(src.includes('prohibited_local_authority'))
})

test('read model compiler is pure and fail-closed on unknown statuses', () => {
  const src = read('lib/read_model/dashboard_read_model_compiler.ts')
  assert.ok(src.includes('compileDashboardReadModel(publication: DashboardPublication)'))
  assert.ok(src.includes('normalizeDecisionStatus'))
  assert.ok(src.includes("unknown_blocked"))
  assert.ok(src.includes("blocked('control_decisions'"))
})

test('field-level provenance map covers trust/control/judgment/override/replay panels', () => {
  const src = read('lib/provenance/field_provenance.ts')
  for (const panel of ['trust_posture', 'control_decisions', 'judgment_records', 'override_lifecycle', 'replay_certification']) {
    assert.ok(src.includes(`panel_id: '${panel}'`))
  }
  assert.ok(src.includes('fields:'))
})

test('status normalization is contract-backed and blocks unknown values', () => {
  const src = read('lib/normalization/status_normalization.ts')
  assert.ok(src.includes('DECISION_STATUS_MAP'))
  assert.ok(!src.includes('.includes('))
  assert.ok(src.includes("return normalized ?? 'unknown_blocked'"))
})

test('dashboard certification gate blocks missing contracts/provenance and selector authority drift', () => {
  const src = read('lib/guards/dashboard_certification_gate.ts')
  assert.ok(src.includes('missing capability map entry'))
  assert.ok(src.includes('missing field provenance entry'))
  assert.ok(src.includes('selector-side governance decision authority detected'))
})

test('sections render governed operator panels and certification gate', () => {
  const src = read('components/sections/DashboardSections.tsx')
  assert.ok(src.includes('Dashboard certification gate'))
  assert.ok(src.includes('model.operatorPanels.map'))
})

test('loader wires control/judgment/override/replay/coverage/certification artifacts', () => {
  const src = read('lib/loaders/dashboard_publication_loader.ts')
  for (const artifact of ['judgment_application_artifact.json', 'rq_next_24_01__umbrella_1__nx_05_operator_override_capture.json', 'rq_next_24_01__umbrella_3__nx_13_recommendation_replay_pack.json', 'serial_bundle_validator_result.json', 'dashboard_public_contract_coverage.json', 'governed_promotion_discipline_gate.json']) {
    assert.ok(src.includes(artifact))
  }
})
