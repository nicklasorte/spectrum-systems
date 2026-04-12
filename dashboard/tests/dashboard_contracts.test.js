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

test('render-state stale gate enforces explicit freshness contract and freshness-vs-time consistency', () => {
  const src = read('lib/guards/render_state_guards.ts')
  assert.ok(src.includes('DEFAULT_FRESHNESS_WINDOW_HOURS = 6'))
  assert.ok(src.includes("normalizedFreshnessStatus !== 'fresh' && normalizedFreshnessStatus !== 'stale'"))
  assert.ok(src.includes("(normalizedFreshnessStatus === 'fresh' && staleByTime)"))
  assert.ok(src.includes("(normalizedFreshnessStatus === 'stale' && !staleByTime)"))
})

test('manifest completeness and sync audit state are truthfully derived', () => {
  const src = read('lib/selectors/dashboard_selectors.ts')
  assert.ok(src.includes('const declaredCount = declaredRequired.length'))
  assert.ok(src.includes('publication.syncAudit.exists && publication.syncAudit.valid'))
  assert.ok(src.includes('sync_audit:'))
})

test('recommendation provenance drawer binds to recommendation provenance', () => {
  const src = read('components/sections/DashboardSections.tsx')
  assert.ok(src.includes("rows={model.recommendation.provenance}"))
})

test('discriminator-aware validation rules exist for critical artifacts', () => {
  const src = read('lib/validation/dashboard_validation.ts')
  assert.ok(src.includes("if (name === 'repo_snapshot_meta.json')"))
  assert.ok(src.includes("if (name === 'dashboard_freshness_status.json')"))
  assert.ok(src.includes("if (name === 'hard_gate_status_record.json')"))
  assert.ok(src.includes("if (name === 'current_run_state_record.json')"))
  assert.ok(src.includes("if (name === 'next_action_recommendation_record.json')"))
  assert.ok(src.includes("if (name === 'refresh_run_record.json')"))
  assert.ok(src.includes("if (name === 'publication_attempt_record.json')"))
})

test('artifact explorer distinguishes declared/loaded/missing/invalid states', () => {
  const src = read('lib/selectors/dashboard_selectors.ts')
  for (const status of ['declared_loaded_valid', 'declared_not_loaded', 'declared_missing', 'loaded_invalid']) {
    assert.ok(src.includes(status))
  }
})



test('selector does not use token heuristics for policy-significant status', () => {
  const src = read('lib/selectors/dashboard_selectors.ts')
  assert.ok(!src.includes('truthyStatus'))
  assert.ok(!src.includes('blockedStatus'))
  assert.ok(src.includes('deriveHardGateUnsatisfied'))
  assert.ok(src.includes('deriveRunBlocked'))
})

test('provenance no longer uses artifact-backed placeholders', () => {
  const src = read('lib/selectors/dashboard_selectors.ts')
  assert.ok(!src.includes("keysUsed: ['artifact-backed']"))
  assert.ok(src.includes("item.name === 'next_action_recommendation_record.json'"))
  assert.ok(src.includes("item.name === 'dashboard_freshness_status.json'"))
})

test('recommendation path is artifact-first with explicit fallback labeling', () => {
  const src = read('lib/selectors/dashboard_selectors.ts')
  assert.ok(src.includes('const recommendationIsArtifactBacked'))
  assert.ok(src.includes("sourceBasis: 'recommendation artifact'"))
  assert.ok(src.includes("title: 'No recommendation available'"))
  assert.ok(src.includes("reason: 'Governed recommendation artifact missing or invalid'"))
  assert.ok(src.includes("sourceBasis: 'abstain_missing_artifact'"))
  assert.ok(src.includes('synthesizedFallback: true'))
  assert.ok(!src.includes('Satisfy hard gate'))
  assert.ok(!src.includes('Run bounded repair'))
  assert.ok(!src.includes('Address bottleneck'))
})

test('runtime hotspots are not read before renderable branch', () => {
  const src = read('components/RepoDashboard.tsx')
  assert.ok(!src.includes('runtime_hotspots'))
})

test('validation rejects malformed critical artifact fields', () => {
  const src = read('lib/validation/dashboard_validation.ts')
  assert.ok(src.includes('invalid data_source_state enum'))
  assert.ok(src.includes('invalid readiness_status/pass_fail enum'))
  assert.ok(src.includes('invalid current_run_status/status enum'))
  assert.ok(src.includes('records must be non-empty array'))
})

test('manifest validation is strict for publication state and required files integrity', () => {
  const src = read('lib/validation/dashboard_validation.ts')
  assert.ok(src.includes("if (name === 'dashboard_publication_manifest.json')"))
  assert.ok(src.includes('invalid publication_state enum'))
  assert.ok(src.includes('required_files must be non-empty string[]'))
  assert.ok(src.includes('artifact_count must match required_files length (or +1 when manifest self-counted)'))
  assert.ok(src.includes('required_files must contain unique entries'))
})

test('provenance explicitly marks unknown fields as low confidence when necessary', () => {
  const src = read('lib/selectors/dashboard_selectors.ts')
  assert.ok(src.includes("keyFields: ['unknown']"))
  assert.ok(src.includes("provenanceConfidence: 'low'"))
  assert.ok(src.includes("provenanceConfidence: 'high'"))
})

test('artifact explorer uses explicit mapping table and no string includes classification', () => {
  const src = read('lib/selectors/dashboard_selectors.ts')
  assert.ok(src.includes('ARTIFACT_EXPLORER_FAMILY_BY_NAME'))
  assert.ok(src.includes('artifactExplorerFamily'))
  assert.ok(!src.includes("name.includes('recommendation')"))
  assert.ok(!src.includes("name.includes('run')"))
  assert.ok(!src.includes("name.includes('gate')"))
})
test('artifact set exists for critical publication files', () => {
  const pubDir = path.join(__dirname, '..', 'public')
  for (const artifact of ['repo_snapshot.json', 'repo_snapshot_meta.json', 'hard_gate_status_record.json', 'current_run_state_record.json', 'next_action_recommendation_record.json']) {
    assert.ok(fs.existsSync(path.join(pubDir, artifact)), `${artifact} must exist`)
  }
})
