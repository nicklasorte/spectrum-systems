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
  assert.ok(loaderSrc.includes('requiredFiles.map((name) => fetchJsonArtifact(name))'))
})

test('allArtifacts contains full validated required artifact set', () => {
  const loaderSrc = read('lib/loaders/dashboard_publication_loader.ts')
  assert.ok(loaderSrc.includes('const validatedArtifacts = loadedRequiredArtifacts.map(markValidated)'))
  assert.ok(loaderSrc.includes('allArtifacts: [manifest, ...validatedArtifacts]'))
})

test('no optional/unloaded bypass remains for manifest-declared artifacts', () => {
  const loaderSrc = read('lib/loaders/dashboard_publication_loader.ts')
  assert.ok(!loaderSrc.includes('optional/unloaded'))
  assert.ok(!loaderSrc.includes("declaredArtifacts.has('recommendation_accuracy_tracker.json')"))
})

test('current repo snapshot has all manifest-declared required files present on disk', () => {
  const manifest = JSON.parse(read('public/dashboard_publication_manifest.json'))
  const required = manifest.required_files
  const missing = required.filter((name) => !fs.existsSync(path.join(DASHBOARD_ROOT, 'public', name)))
  assert.deepStrictEqual(missing, [])
})

test('render gate retains fail-closed incomplete_manifest_coverage behavior', () => {
  const guardSrc = read('lib/guards/render_state_guards.ts')
  assert.ok(guardSrc.includes("truthViolationReasons: ['incomplete_manifest_coverage']"))
  assert.ok(guardSrc.includes('const incompleteArtifacts = [...new Set([...missingDeclared, ...invalidLoaded])]'))
})
