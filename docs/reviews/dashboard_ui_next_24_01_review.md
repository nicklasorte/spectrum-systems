# Dashboard UI Review — NEXT-24-01

**Review ID:** CLAUDE-REVIEW-DASHBOARD-UI-NEXT-24-01
**Date:** 2026-04-11
**Scope:** Dashboard UI only (`dashboard/` tree)
**Reviewer:** Claude Sonnet (architecture review, no execution authority)
**Model escalation:** Not triggered — no architectural spillover requiring Opus

---

## 1. Executive Summary

**Is the dashboard now a governed operator surface?**

Partially. The architectural intent is sound and largely implemented. The layer
separation (loader → selector → guard → presenter) is present. The `force-dynamic`
rendering contract is enforced. The `SectionShell` gate pattern is correctly applied
to the 7 artifact-backed section components. Provenance is always visible, including
during degraded states. These are genuine improvements.

However, three specific conditions allow the dashboard to lie or imply correctness
without backing artifacts. Per the review criteria, these constitute a mandatory FAIL.

**Overall trust rating: FAIL**

**Blocking conditions:**

1. `manifestCompleteness: 'Complete'` is demonstrably false when only 6 of 33
   manifest-declared artifacts are checked.
2. `syncAuditState: 'Published'` is asserted from manifest file existence alone,
   without reading the manifest's own `publication_state` field.
3. `<DashboardSections>` renders unconditionally regardless of the top-level render
   gate state — unverified topology, comparison, and health data surface during
   `truth_violation`, `stale`, and `incomplete_publication` states.

Each of these meets the explicit criterion: the UI can lie, imply correctness, or
bypass artifact truth.

---

## 2. What Was Done Well

**Layer separation is enforced and visible.**
`lib/loaders/`, `lib/guards/`, `lib/selectors/`, `lib/validation/`, and `components/`
are cleanly separated. The data pipeline — loader → markValidated → selector →
deriveRenderState → component — is traceable end to end.

**Top-level render gate is typed as a discriminated union.**
`components/RepoDashboard.tsx:5-7`: `RepoDashboardRenderGate` forces callers to narrow
to the `renderable` variant before accessing `snapshot`. No phantom access to data
through an implicit `if` check.

**`SectionShell<T>` gates all 7 artifact sections.**
`components/sections/DashboardSections.tsx:9-26`: Each section independently checks its
own `SectionState` before calling the render function. `ProvenanceDrawer` remains
visible in all degraded states, which is correct operator behavior.

**Fail-closed defaults in the guard.**
`lib/guards/render_state_guards.ts:25`: `const stale = refreshed ? ... > 6 : true` —
if `last_refreshed_time` is missing, stale is assumed. The default is fail-closed.

**`force-dynamic` on both routes.**
`app/page.tsx:5` and `app/executive-summary/page.tsx`: No static generation, no
build-time data leakage. Verified by contract test.

**Recommendation content is fail-safe during truth violation.**
`lib/selectors/dashboard_selectors.ts:41-47`: When `state.kind !== 'renderable'`, the
recommendation title explicitly reads "No recommendation: fail-closed truth gate
active." The card does not suggest an action without artifact backing.

**Provenance drawer is always rendered.**
`components/sections/DashboardSections.tsx:15, 23`: `ProvenanceDrawer` renders in both
the blocked and renderable paths of `SectionShell`. Operators can inspect which
artifact failed even when a section is degraded.

---

## 3. Critical Risks (BLOCKERS)

### BLOCKER-1: `manifestCompleteness: 'Complete'` is a lie

**File:** `lib/selectors/dashboard_selectors.ts:101`
```ts
manifestCompleteness: state.missingArtifacts.length ? 'Incomplete' : 'Complete'
```

`state.missingArtifacts` is populated only from the 6 artifacts in the `critical`
list in `lib/guards/render_state_guards.ts:3`. The manifest declares 33 artifacts
(`public/dashboard_publication_manifest.json: artifact_count: 33`). The loader loads
10. 23 artifacts are never loaded or checked at runtime.

Result: when all 6 critical artifacts exist, `manifestCompleteness` displays as
`'Complete'` in the `StateStrip` and the Publication integrity card. This is factually
incorrect. An operator reading this field cannot trust it as a publication integrity
signal.

**Blocking condition:** The UI implies a complete publication without verifying it.

---

### BLOCKER-2: `syncAuditState: 'Published'` without reading manifest content

**File:** `lib/selectors/dashboard_selectors.ts:103`
```ts
syncAuditState: publication.manifest.exists ? 'Published' : 'Missing manifest'
```

`'Published'` is asserted solely on the manifest file's existence. The manifest
artifact's own `publication_state` field (e.g., `"live"`, `"draft"`, `"partial"`)
is never read. A manifest with `publication_state: "draft"` or a partially-committed
artifact bundle would still display `syncAuditState: 'Published'`.

**Blocking condition:** The UI implies a valid publication sync without inspecting
the declared publication state.

---

### BLOCKER-3: `<DashboardSections>` renders unconditionally during blocked states

**File:** `components/RepoDashboard.tsx:22-28`
```tsx
{renderGate.kind !== 'renderable' ? (
  <BlockedState title={`Dashboard unavailable: ${model.state.kind}`} reason={model.state.reason} />
) : null}

<DashboardSections model={model} />   {/* always rendered */}
```

`<DashboardSections>` is not gated by `renderGate.kind`. During `truth_violation`,
`stale`, `incomplete_publication`, or `no_data` states:

- `<BlockedState>` renders (correct)
- `<DashboardSections>` also renders (incorrect)

Surfaces rendered without guard during blocked states:
- `StateStrip` with `manifestCompleteness` and `publicationState`
- Recommendation card (content is fail-safe, but the card renders)
- `TopologyPanel` — shows node statuses from partially-verified artifacts
- Comparison table — shows `drift`, `hardGate`, `runState` from unverified data
- Artifact explorer — shows artifact family/status derived from unloaded artifacts
- Health scorecards — scores computed from stale or unverified artifact state
- Publication integrity card

An operator seeing topology nodes as `'online'` while `<BlockedState>` declares a
truth violation receives contradictory signals. Topology validity is driven by the
runtime `valid` flag, which passes for any non-null object (see STRUCTURAL-1).

**Blocking condition:** Sections bypass the render gate and surface data from
unverified or unloaded artifacts.

---

## 4. Structural Weaknesses

### STRUCTURAL-1: Runtime schema validation validates object shape only

**File:** `lib/validation/dashboard_validation.ts:3-17`
```ts
function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}
export function validateArtifactShape(name: string, data: unknown) {
  if (!isObject(data)) return { valid: false, error: `${name} must be object` }
  return { valid: true }
}
```

Any non-null, non-array object passes as `valid: true`. An artifact file containing
`{ "foo": "bar" }` passes validation and reaches the selector. The `valid` flag does
not mean what operators would assume it means. The render gate's `renderable`
classification depends on this flag being trustworthy.

Full JSON Schema validation exists in CI only. Runtime has no equivalent.

---

### STRUCTURAL-2: Recommendation decision logic is embedded in the selector

**File:** `lib/selectors/dashboard_selectors.ts:40-74`

The selector contains a 4-branch priority decision (truth violation → hard gate
unsatisfied → run blocked → bottleneck) that determines what operational action to
recommend. This is policy-level judgment. The selector should transform artifact data
into view-model structures; it should not determine what the next operational action is.

`next_action_recommendation_record.json` is declared in the schema and the publication
manifest but is not loaded by the loader or consumed by the selector. The selector
synthesizes the recommendation inline instead of reading the governed artifact.

---

### STRUCTURAL-3: `truthyStatus` and `blockedStatus` are implicit vocabulary contracts

**File:** `lib/selectors/dashboard_selectors.ts:13-20`
```ts
function truthyStatus(value?: string): boolean {
  return ['pass', 'ready', 'good', 'healthy', 'satisfied'].some((token) => v.includes(token))
}
function blockedStatus(value?: string): boolean {
  return ['block', 'repair', 'fail', 'risk', 'freeze'].some((token) => v.includes(token))
}
```

These substring-matching functions encode governance vocabulary in the UI layer. If
artifact producers change `readiness_status` from `"pass"` to `"approved"`, these
functions silently misclassify the status. Hard gate and run state behavioral
classification is not contract-bound — it is heuristic.

---

### STRUCTURAL-4: Guard evaluation order masks truth violation reasons

**File:** `lib/guards/render_state_guards.ts:27-33`

The `stale` check fires before the `truth_violation` check. If `data_source_state`
is not `"live"` AND the data is stale, the guard returns `'stale'` and never evaluates
source state. The operator sees `'stale_publication'` but the `'source_not_live'`
condition — which requires different remediation — is masked.

---

### STRUCTURAL-5: Recommendation `ProvenanceDrawer` shows hard gate provenance

**File:** `components/sections/DashboardSections.tsx:48`
```tsx
<ProvenanceDrawer title='recommendation' rows={model.sections.hardGate.provenance} />
```

The recommendation's provenance is hardcoded to the hard gate section's provenance
regardless of what actually drove the recommendation. When the recommendation is based
on the bottleneck, run state, or truth gate, the provenance drawer shows the wrong
artifact. This is a provenance lie.

---

### STRUCTURAL-6: `keysUsed` provenance field is a hardcoded placeholder

**File:** `lib/selectors/dashboard_selectors.ts:149`
```ts
keysUsed: ['artifact-backed']
```

Every provenance entry carries `keysUsed: ['artifact-backed']`. The field is declared
in `DashboardViewModel` to express which specific keys from each artifact were consumed.
The placeholder replaces this with a non-informative constant. Provenance depth is
declared but not implemented.

---

## 5. Render Gate Integrity Assessment

The render gate architecture operates at two levels:

**Level 1 — Top-level gate (`components/RepoDashboard.tsx`)**

The discriminated union `RepoDashboardRenderGate` is correctly typed and forces
narrowing before data access. `<BlockedState>` is correctly shown during blocked states.

Failure: `<DashboardSections>` renders unconditionally. The gate is additive (adds a
blocked banner) rather than exclusive (suppresses unverified content). This is BLOCKER-3.
The gate exists but is not enforced at the section render level.

**Level 2 — Section-level gates (`SectionShell<T>`)**

`SectionShell` correctly checks `section.state !== 'renderable' || !section.data`
before calling the render function. `ProvenanceDrawer` is preserved in both paths.
This is correctly implemented.

Failure: Several surfaces in `DashboardSections` are outside `SectionShell` and have
no render gate: `StateStrip`, recommendation card, `TopologyPanel`, comparison table,
artifact explorer, health scorecards, `ReviewQueuePanel`, publication integrity card.
These always render with whatever data the selector produced.

**Assessment:** Gates are non-bypassable for the 7 section components. They are absent
for all other surfaces. Top-level gate exists but does not suppress content. Gate
integrity is partial.

---

## 6. Artifact Integrity Assessment

**Is the UI artifact-first?**

Partially. The loader is centralized, `Promise.all`-based, and fail-closed. Artifacts
are read from the filesystem at request time with no scattered fetch logic in components.
These are correct.

**Gaps:**

- 10 of 33 declared manifest artifacts are loaded. The loader does not verify its
  loaded count against the manifest's declared `artifact_count: 33` or
  `publication_state`.
- `recommendation_accuracy_tracker.json` is explicitly labeled unavailable via a
  hardcoded string (`dashboard_selectors.ts:155`: `value: 'artifact unavailable'`).
  The artifact is schema-defined and presumably exists in `public/`; the loader simply
  does not load it. The UI misrepresents an available artifact as unavailable.
- `next_action_recommendation_record.json` is schema-defined, manifest-declared, and
  not loaded. The selector synthesizes the recommendation inline instead.

**Any synthetic or inferred state?**

Yes. The recommendation is entirely synthesized from inline selector logic. The
`manifestCompleteness` and `syncAuditState` fields are inferred from artifact existence
rather than manifest content.

**Assessment:** Centralized loading is correct. Artifact coverage (10 of 33) and
manifest content verification are not.

---

## 7. Control Boundary Assessment

**Is UI leaking control or policy logic?**

Yes, in two confirmed locations:

**Recommendation priority logic** (`lib/selectors/dashboard_selectors.ts:40-74`): The
4-branch decision tree is CDE-level judgment embedded in the UI selector. The governed
pattern is for this decision to arrive as a pre-computed artifact that the selector
reads and presents without modification.

**Status vocabulary interpretation** (`lib/selectors/dashboard_selectors.ts:13-20`):
`truthyStatus` and `blockedStatus` classify artifact field values using embedded token
lists. This is governance policy (what constitutes "pass" vs. "blocked") embedded in
the UI, driving render state, review queue insertion, and health scorecard grading.

**Assessment:** FAIL on control boundary. Recommendation decision logic is not external
to the UI.

---

## 8. Extensibility Assessment

Adding a new artifact-backed section currently requires changes in 4 files:
1. `types/dashboard.ts` — add to `DashboardPublication` and `DashboardViewModel.sections`
2. `lib/loaders/dashboard_publication_loader.ts` — add `fetchJsonArtifact` call
3. `lib/selectors/dashboard_selectors.ts` — add `makeSection` call
4. `components/sections/DashboardSections.tsx` — add `SectionShell` render

The `SectionShell<T>` pattern is the correct abstraction. If followed, a new section
cannot accidentally bypass the render gate. There is no mechanism to enforce this —
a developer can render section data directly without `SectionShell`.

The `critical` list in `lib/guards/render_state_guards.ts:3` is hardcoded. A new
critical artifact requires a manual list update with no compile-time enforcement.

**Assessment:** Pattern is correct and bounded. The 4-file coupling and hardcoded
critical list create non-obvious maintenance surface that will drift under pressure.

---

## 9. Top 5 Surgical Fixes (Ranked)

### Fix 1 — Gate `<DashboardSections>` under the top-level render gate

**File:** `components/RepoDashboard.tsx:28`

Wrap `<DashboardSections>` in the `renderGate.kind === 'renderable'` condition. During
blocked states, render only `<BlockedState>` plus a minimal provenance-only panel
(artifact chip list and state strip). This eliminates BLOCKER-3 and prevents topology,
comparison, and health data from surfacing with unverified backing.

---

### Fix 2 — Read manifest content for `manifestCompleteness` and `syncAuditState`

**File:** `lib/selectors/dashboard_selectors.ts:101-103`

Read `publication.manifest.data?.publication_state` and
`publication.manifest.data?.artifact_count`. Compute:

```ts
manifestCompleteness: declaredCount > 0 && loadedCount >= declaredCount
  ? 'Complete' : 'Incomplete'
syncAuditState: declaredState === 'live'
  ? 'Published' : `manifest_state:${declaredState}`
```

Eliminates BLOCKER-1 and BLOCKER-2. `manifestCompleteness` and `syncAuditState`
become grounded in manifest-declared values, not artifact existence.

---

### Fix 3 — Load and use `next_action_recommendation_record.json`

**Files:** `lib/loaders/dashboard_publication_loader.ts`,
`lib/selectors/dashboard_selectors.ts`

Add the artifact to the loader. In the selector, read the recommendation from the
loaded artifact. Fall back to the current synthesized logic only if the artifact is
missing or invalid, and mark the fallback explicitly in `sourceBasis`
(e.g., `'synthesized:fallback'`). This eliminates the policy logic from the selector
(STRUCTURAL-2) and makes the recommendation artifact-first.

---

### Fix 4 — Add discriminator-field presence checks to `validateArtifactShape`

**File:** `lib/validation/dashboard_validation.ts`

For each critical artifact, check that the fields driving render gate decisions are
present. Minimum:
- `repo_snapshot_meta.json`: require `data_source_state` and `last_refreshed_time`
- `hard_gate_status_record.json`: require `readiness_status`
- `current_run_state_record.json`: require `current_run_status`

An artifact missing its discriminator field returns `valid: false`. This makes the
`valid` flag meaningful to the render gate. Addresses STRUCTURAL-1.

---

### Fix 5 — Correct the recommendation `ProvenanceDrawer` binding

**File:** `components/sections/DashboardSections.tsx:48`

Replace `rows={model.sections.hardGate.provenance}` with a dedicated
`model.recommendation.provenance` field in `DashboardViewModel`, populated in the
selector based on whichever artifact actually drove the recommendation. Low-effort,
eliminates STRUCTURAL-5.

---

## 10. Recommended Next Hard Gate

**Gate name:** DASHBOARD-RENDER-INTEGRITY-GATE

Before any new dashboard section, operator surface, or artifact integration is added,
the following must be verified and contract-tested:

1. `<DashboardSections>` does not render during any blocked render gate state.
2. `manifestCompleteness` and `syncAuditState` read from manifest content fields, not
   artifact existence.
3. Contract tests assert both conditions above against a simulated blocked render state.
4. The `valid` flag for critical artifacts reflects discriminator-field presence, not
   object shape alone.

**Rationale:** Without these four conditions locked, the dashboard can reach
`manifestCompleteness: 'Complete'` and render topology and comparison data during truth
violations. These are the specific failure modes that make the dashboard untrustworthy
as an operator surface. No surface expansion should proceed until these invariants are
enforced.

---

## Appendix: Dead Code

**File:** `components/RepoDashboard.tsx:26`
```tsx
{renderGate.kind !== 'renderable' ? null : renderGate.snapshot.runtime_hotspots ? null : null}
```

This triple-null conditional always renders nothing in all branches. It appears to be
an incomplete implementation of a `runtime_hotspots` rendering path. Not a blocker,
but signals incomplete feature work adjacent to a gated access point.
