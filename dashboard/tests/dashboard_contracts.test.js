const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

function read(rel) {
  return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8')
}

test('render states are explicitly declared', () => {
  const src = read('types/dashboard.ts')
  for (const state of ['renderable', 'no_data', 'incomplete_publication', 'stale', 'truth_violation']) {
    assert.ok(src.includes(`'${state}'`))
  }
})

test('homepage stays force-dynamic', () => {
  const src = read('app/page.tsx')
  assert.ok(src.includes("export const dynamic = 'force-dynamic'"))
})

test('central publication loader validates and loads recommendation artifacts', () => {
  const src = read('lib/loaders/dashboard_publication_loader.ts')
  assert.ok(src.includes('markValidated'))
  assert.ok(src.includes('dashboard_publication_manifest.json'))
  assert.ok(src.includes('next_action_recommendation_record.json'))
  assert.ok(src.includes('recommendation_accuracy_tracker.json'))
})

test('operator and executive routes are split', () => {
  const src = read('app/executive-summary/page.tsx')
  assert.ok(src.includes('Executive Summary'))
})

test('exclusive top-level blocked-state gate is enforced in RepoDashboard', () => {
  const src = read('components/RepoDashboard.tsx')
  assert.ok(src.includes('renderGate.kind !== \'renderable\' ? ('))
  assert.ok(src.includes('<DashboardSections model={model} />'))
  assert.ok(src.includes('Blocked-state provenance/debug (non-operational)'))
})

test('blocked-state branch does not render operator surfaces', () => {
  const src = read('components/RepoDashboard.tsx')
  const blockedBranch = src.split('renderGate.kind !== \'renderable\' ? (')[1]
  assert.ok(blockedBranch.includes('<BlockedState'))
  assert.ok(!blockedBranch.includes('TopologyPanel'))
  assert.ok(!blockedBranch.includes('Current vs prior comparison'))
})

test('render-state guard uses manifest coverage and prioritizes source_not_live before stale', () => {
  const src = read('lib/guards/render_state_guards.ts')
  assert.ok(src.includes('required_files'))
  assert.ok(src.includes('incomplete_manifest_coverage'))
  assert.ok(src.indexOf('source_not_live') < src.indexOf('stale_publication'))
})

test('manifest completeness and sync audit state are manifest-data derived', () => {
  const src = read('lib/selectors/dashboard_selectors.ts')
  assert.ok(src.includes('publication.manifest.data?.artifact_count'.replace('publication.', '')))
  assert.ok(src.includes('manifest:'))
  assert.ok(src.includes('publication.manifest.data?.publication_state'.replace('publication.', '')))
})

test('recommendation provenance drawer binds to recommendation provenance', () => {
  const src = read('components/sections/DashboardSections.tsx')
  assert.ok(src.includes("rows={model.recommendation.provenance}"))
})

test('discriminator-aware validation rules exist for critical artifacts', () => {
  const src = read('lib/validation/dashboard_validation.ts')
  assert.ok(src.includes("'repo_snapshot_meta.json': ['data_source_state', 'last_refreshed_time']"))
  assert.ok(src.includes("'hard_gate_status_record.json': ['readiness_status']"))
  assert.ok(src.includes("'current_run_state_record.json': ['current_run_status']"))
})

test('artifact explorer distinguishes declared/loaded/missing/invalid states', () => {
  const src = read('lib/selectors/dashboard_selectors.ts')
  for (const status of ['declared_loaded_valid', 'declared_not_loaded', 'declared_missing', 'loaded_invalid']) {
    assert.ok(src.includes(status))
  }
})

test('artifact set exists for critical publication files', () => {
  const pubDir = path.join(__dirname, '..', 'public')
  for (const artifact of ['repo_snapshot.json', 'repo_snapshot_meta.json', 'hard_gate_status_record.json', 'current_run_state_record.json', 'next_action_recommendation_record.json']) {
    assert.ok(fs.existsSync(path.join(pubDir, artifact)), `${artifact} must exist`)
  }
})
