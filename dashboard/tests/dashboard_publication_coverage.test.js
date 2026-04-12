const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const DASHBOARD_ROOT = path.join(__dirname, '..')

function read(rel) {
  return fs.readFileSync(path.join(DASHBOARD_ROOT, rel), 'utf8')
}

test('loader attempts every manifest-declared required file via required_files loop', () => {
  const loaderSrc = read('lib/loaders/dashboard_publication_loader.ts')
  assert.ok(loaderSrc.includes('const requiredFiles = manifest.data?.required_files ?? []'))
  assert.ok(loaderSrc.includes('Promise.all(requiredFiles.map((name) => fetchJsonArtifact(name)))'))
})

test('allArtifacts is built from full validated required artifact list', () => {
  const loaderSrc = read('lib/loaders/dashboard_publication_loader.ts')
  assert.ok(loaderSrc.includes('const validatedDeclaredArtifacts = declaredArtifacts.map(markValidated)'))
  assert.ok(loaderSrc.includes('allArtifacts: [manifest, ...validatedDeclaredArtifacts]'))
})

test('declared artifact map exists for non-typed selectors', () => {
  const loaderSrc = read('lib/loaders/dashboard_publication_loader.ts')
  assert.ok(loaderSrc.includes('declaredArtifactMap: Object.fromEntries(validatedDeclaredArtifacts.map((artifact) => [artifact.name, artifact]))'))
})

test('current repo snapshot has all manifest-declared required files present on disk', () => {
  const manifest = JSON.parse(read('public/dashboard_publication_manifest.json'))
  const required = manifest.required_files
  const missing = required.filter((name) => !fs.existsSync(path.join(DASHBOARD_ROOT, 'public', name)))
  assert.deepStrictEqual(missing, [])
})

test('fallback validation supports object/array for untyped artifacts', () => {
  const validationSrc = read('lib/validation/dashboard_validation.ts')
  assert.ok(validationSrc.includes('if (Array.isArray(data) || isObject(data))'))
  assert.ok(validationSrc.includes('return { valid: false, error: `${name} must be JSON object or array` }'))
})

test('render gate retains fail-closed incomplete_manifest_coverage behavior', () => {
  const guardSrc = read('lib/guards/render_state_guards.ts')
  assert.ok(guardSrc.includes("truthViolationReasons: ['incomplete_manifest_coverage']"))
  assert.ok(guardSrc.includes('const incompleteArtifacts = [...new Set([...missingDeclared, ...invalidLoaded])]'))
})

test('loader and guard wire freshness source-of-truth through dashboard_freshness_status', () => {
  const loaderSrc = read('lib/loaders/dashboard_publication_loader.ts')
  const guardSrc = read('lib/guards/render_state_guards.ts')
  assert.ok(loaderSrc.includes("dashboard_freshness_status.json"))
  assert.ok(guardSrc.includes('snapshot_last_refreshed_time'))
  assert.ok(guardSrc.includes('freshness_window_hours'))
  assert.ok(guardSrc.includes('freshnessTimestampMs !== metaTimestampMs'))
  assert.ok(guardSrc.includes('publicationAttemptRecord'))
  assert.ok(guardSrc.includes('trace_linkage_missing'))
})

test('loader includes refresh and publication attempt artifacts', () => {
  const loaderSrc = read('lib/loaders/dashboard_publication_loader.ts')
  assert.ok(loaderSrc.includes('refresh_run_record.json'))
  assert.ok(loaderSrc.includes('publication_attempt_record.json'))
})

test('freshness parsing is explicit UTC and fail-closed on malformed timestamps', () => {
  const guardSrc = read('lib/guards/render_state_guards.ts')
  assert.ok(guardSrc.includes('function parseIsoUtcTimestamp'))
  assert.ok(guardSrc.includes('^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$'))
  assert.ok(guardSrc.includes('freshnessTimestampMs === null'))
  assert.ok(guardSrc.includes('metaTimestampMs === null'))
})
