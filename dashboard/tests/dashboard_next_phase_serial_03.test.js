const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

function read(rel) {
  return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8')
}

test('serial-03 registry declares policy/audit/action/review/misinterpretation panels', () => {
  const src = read('lib/contracts/surface_contract_registry.ts')
  for (const panel of ['policy_visibility', 'audit_trail', 'action_surface', 'review_queue_surface', 'misinterpretation_guard']) {
    assert.ok(src.includes(`panel_id: '${panel}'`), `${panel} contract missing`)
  }
  assert.ok(src.includes("allowed_statuses: ['renderable', 'blocked']"))
})

test('serial-03 capability map keeps decision authority read_only', () => {
  const src = read('lib/contracts/panel_capability_map.ts')
  for (const panel of ['policy_visibility', 'audit_trail', 'action_surface', 'review_queue_surface', 'misinterpretation_guard']) {
    assert.ok(src.includes(`panel_id: '${panel}'`), `${panel} capability missing`)
  }
  assert.ok(!src.includes("decision_authority: 'write'"))
})

test('serial-03 provenance map includes field-level trace entries for new panels', () => {
  const src = read('lib/provenance/field_provenance.ts')
  for (const panel of ['policy_visibility', 'audit_trail', 'action_surface', 'review_queue_surface', 'misinterpretation_guard']) {
    assert.ok(src.includes(`panel_id: '${panel}'`), `${panel} provenance missing`)
  }
  assert.ok(src.includes('recommendation_review_surface.json'))
})

test('serial-03 compiler wires fail-closed operator surfaces and uncertainty guard', () => {
  const src = read('lib/read_model/dashboard_read_model_compiler.ts')
  assert.ok(src.includes("blocked('action_surface'"))
  assert.ok(src.includes("blocked('review_queue_surface'"))
  assert.ok(src.includes("blocked('policy_visibility'"))
  assert.ok(src.includes("blocked('audit_trail'"))
  assert.ok(src.includes("panelId: 'misinterpretation_guard'"))
  assert.ok(src.includes('no decision execution'))
})

test('serial-03 certification gate still enforces contract/provenance parity', () => {
  const src = read('lib/guards/dashboard_certification_gate.ts')
  assert.ok(src.includes('missing capability map entry'))
  assert.ok(src.includes('missing field provenance entry'))
  assert.ok(src.includes('selector-side governance decision authority detected'))
})
