const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

function read(rel) {
  return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8')
}

test('serial-02 registry includes causal/trace/correlation/evidence panels with blocked diagnostics', () => {
  const src = read('lib/contracts/surface_contract_registry.ts')
  for (const panel of ['causal_chain', 'decision_trace', 'multi_artifact_correlation', 'evidence_strength']) {
    assert.ok(src.includes(`panel_id: '${panel}'`), `${panel} contract missing`)
  }
  assert.ok(src.includes("blocked_state_behavior: 'render_blocked_diagnostic'"))
})

test('serial-02 capability map preserves read-only authority for causal surfaces', () => {
  const src = read('lib/contracts/panel_capability_map.ts')
  for (const panel of ['causal_chain', 'decision_trace', 'multi_artifact_correlation', 'evidence_strength']) {
    assert.ok(src.includes(`panel_id: '${panel}'`), `${panel} capability missing`)
  }
  assert.ok(!src.includes("decision_authority: 'write'"))
})

test('serial-02 field provenance includes transformation path for causal edges', () => {
  const src = read('lib/provenance/field_provenance.ts')
  assert.ok(src.includes("panel_id: 'causal_chain'"))
  assert.ok(src.includes('transformation_path'))
  assert.ok(src.includes("serial_bundle_validator_result.pass -> causal_chain.outcome_node"))
})

test('serial-02 compiler includes fail-closed causal and evidence panel logic', () => {
  const src = read('lib/read_model/dashboard_read_model_compiler.ts')
  assert.ok(src.includes("blocked('causal_chain'"))
  assert.ok(src.includes("blocked('decision_trace'"))
  assert.ok(src.includes("blocked('multi_artifact_correlation'"))
  assert.ok(src.includes("blocked('evidence_strength'"))
})

test('serial-02 certification gate enforces blocked status and provenance requirements', () => {
  const src = read('lib/guards/dashboard_certification_gate.ts')
  assert.ok(src.includes('missing provenance requirements'))
  assert.ok(src.includes('blocked status missing from contract'))
})
