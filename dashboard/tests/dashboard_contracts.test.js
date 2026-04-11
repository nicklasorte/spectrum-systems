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

test('central publication loader validates artifacts', () => {
  const src = read('lib/loaders/dashboard_publication_loader.ts')
  assert.ok(src.includes('markValidated'))
  assert.ok(src.includes('dashboard_publication_manifest.json'))
})

test('operator and executive routes are split', () => {
  const src = read('app/executive-summary/page.tsx')
  assert.ok(src.includes('Executive Summary'))
})

test('artifact set exists for critical publication files', () => {
  const pubDir = path.join(__dirname, '..', 'public')
  for (const artifact of ['repo_snapshot.json', 'repo_snapshot_meta.json', 'hard_gate_status_record.json', 'current_run_state_record.json']) {
    assert.ok(fs.existsSync(path.join(pubDir, artifact)), `${artifact} must exist`)
  }
})
