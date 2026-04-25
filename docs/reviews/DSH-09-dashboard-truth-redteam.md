# DSH-09 — Dashboard Truth Red-Team Review

**Date:** 2026-04-25
**Reviewer:** Claude (autonomous execution, DSH-09 scope)
**Branch:** claude/redteam-dashboard-truth-FDmCd
**PRs reviewed:** #1188, #1191 (merged)
**Scope:** apps/dashboard-3ls — all routes, components, libs, Vercel path assumptions

---

## Summary

A full truth-layer red-team was performed on the merged dashboard implementation.
Seven must-fix findings were identified. All seven were fixed in this PR.
Build passes, tests pass (141 total, 31 new tests added).

**Production readiness: NO** — pending Vercel configuration steps documented below.
**Vercel preview readiness: CONDITIONAL** — requires `REPO_ROOT` env var and Root Directory project setting.

---

## Files Reviewed

| File | Role |
|---|---|
| `lib/artifactLoader.ts` | Repo root resolution, artifact loading |
| `lib/truthClassifier.ts` | Data source classification (DSH-03) |
| `lib/signalStatus.ts` | No-green-without-source enforcement (DSH-04/05) |
| `lib/sourceClassification.ts` | Envelope builder (DSH-08) |
| `lib/rgeSignals.ts` | RGE signal derivation |
| `lib/systemSignals.ts` | System metric derivation |
| `lib/displayGroups.ts` | 3LS display grouping (DSH-06/07) |
| `lib/types.ts` | Type contracts |
| `app/api/health/route.ts` | Health API |
| `app/api/systems/route.ts` | Systems API |
| `app/api/intelligence/route.ts` | Intelligence API |
| `app/api/rge/analysis/route.ts` | RGE analysis API |
| `app/api/rge/roadmap/route.ts` | RGE roadmap API |
| `app/api/rge/proposals/route.ts` | RGE proposals API |
| `app/api/trends/route.ts` | Trends API |
| `app/api/compliance/route.ts` | Compliance API |
| `app/api/incidents/route.ts` | Incidents API |
| `app/page.tsx` | Main dashboard page |
| `app/rge/page.tsx` | RGE page |
| `app/detail/page.tsx` | System detail page |
| `app/compliance/page.tsx` | Compliance page |
| `app/on-call/page.tsx` | On-call page |
| `components/SystemCard.tsx` | System card component |
| `components/SystemDetail.tsx` | System detail component |
| `next.config.js` | Next.js / Vercel build config |
| `__tests__/**` | All 12 test suites |

---

## Tests Run

```
npm run build  → PASS
npm run test   → 141 tests, 12 suites, all pass
```

New test suite added: `__tests__/api/redteam.test.ts` (31 tests, 8 describe blocks)

---

## Findings

### F-01 — trends route missing source envelope [MUST-FIX] ✅ FIXED

**Severity:** HIGH
**File:** `app/api/trends/route.ts`

The `/api/trends` response had no `data_source`, `generated_at`, `source_artifacts_used`, or `warnings` fields. Trend data was generated with `Math.random()`, producing non-deterministic values that changed on every request, giving a false impression of real telemetry.

**Fix:** Added `data_source: 'stub_fallback'`, full envelope, removed `Math.random()` in favour of deterministic sine-only variance. Warning text explains data is synthetic.

---

### F-02 — compliance route missing source envelope [MUST-FIX] ✅ FIXED

**Severity:** HIGH
**File:** `app/api/compliance/route.ts`

The `/api/compliance` response had no `data_source`, `generated_at`, `source_artifacts_used`, or `warnings`. Hardcoded `compliant: true` entries were presented with no source attribution, implying verified compliance.

**Fix:** Added `data_source: 'stub_fallback'` and full envelope with explicit warning that compliance status is statically defined and cannot be treated as verified.

---

### F-03 — incidents route missing source envelope [MUST-FIX] ✅ FIXED

**Severity:** HIGH
**File:** `app/api/incidents/route.ts`

The `/api/incidents` response had no `data_source`, `generated_at`, `source_artifacts_used`, or `warnings`. Hardcoded incident records were presented as if they were live signals.

**Fix:** Added `data_source: 'stub_fallback'` and full envelope with explicit warning that incidents are statically defined.

---

### F-04 — proposals POST response missing source envelope [MUST-FIX] ✅ FIXED

**Severity:** MEDIUM
**File:** `app/api/rge/proposals/route.ts` (POST handler)

The POST response from `/api/rge/proposals` returned `{ result, proposal_id, decision, recorded_at }` with no `data_source`, `generated_at`, `source_artifacts_used`, or `warnings`. Every API response must include the full source envelope per the dashboard truth contract.

**Fix:** Added `data_source: 'stub_fallback'` and full envelope to the POST response, with a warning that the decision is recorded in memory only and no persistent artifact store exists.

---

### F-05 — Vercel runtime: `artifactLoader.ts` hardcodes `process.cwd()` path [MUST-FIX] ✅ FIXED

**Severity:** CRITICAL (deployment blocker)
**File:** `lib/artifactLoader.ts`

`getRepoRoot()` used `path.resolve(process.cwd(), '../..')` which assumes `process.cwd()` is the app directory. On Vercel serverless functions, `process.cwd()` is the function root (`/var/task`), so `../..` resolves to `/` and no artifacts are found. All artifact-backed routes would silently fall back to `stub_fallback` on Vercel.

**Fix:** `getRepoRoot()` now checks `process.env.REPO_ROOT` first. When set, it returns that path directly, allowing Vercel to configure the correct artifact root. Falls back to `process.cwd()/../..` for local dev and CI.

**Required Vercel configuration:**
- Project setting: **Root Directory = `apps/dashboard-3ls`**
- Environment variable: **`REPO_ROOT = /var/task`** (or the Vercel function bundle root)

---

### F-05b — `next.config.js` missing `outputFileTracingRoot` and `outputFileTracingIncludes` [MUST-FIX] ✅ FIXED

**Severity:** CRITICAL (deployment blocker)
**File:** `next.config.js`

Next.js build output file tracing does not follow dynamic `path.join()` calls, so the `artifacts/` directory (at the monorepo root, outside the app directory) was never included in the serverless function bundle. On Vercel, all `fs.readFileSync()` calls for artifact paths would throw `ENOENT`.

**Fix:** Added `experimental.outputFileTracingRoot` (monorepo root) and `experimental.outputFileTracingIncludes` to explicitly bundle `artifacts/**/*` for all `/api/**` routes. Added inline comments documenting the required Vercel project settings and the `REPO_ROOT` env var.

---

### F-07 — RGEPage: `rge_can_operate: true` renders green without source gate [MUST-FIX] ✅ FIXED

**Severity:** HIGH (truth contract violation, DSH-04)
**File:** `app/rge/page.tsx`

The `rge_can_operate: true` value rendered as green "CAN OPERATE" regardless of `analysis.data_source`. When `data_source === 'derived_estimate'`, DSH-04 forbids green/healthy rendering. A scenario where only `checkpointSummary` loads (1 of 7 artifacts) produces `derived_estimate` and `rge_can_operate === true` — this would render green without artifact backing.

**Reproduce:**
```
data_source = derived_estimate (1 of 7 artifacts loaded)
rge_can_operate = true (mg_kernel PASS, registry 'unknown' != 'misaligned')
→ UI rendered: green "CAN OPERATE"  ← violates DSH-04
```

**Fix:** Introduced `sourceAllowsGreen` guard (`artifact_store | repo_registry | derived`). When `rge_can_operate` is true but source does not allow green, renders amber `"CAN OPERATE (unverified)"` with a title attribute showing the actual data source. Green "CAN OPERATE" only renders when the source supports it.

---

## Passing Checks (no issues found)

| Check | Result |
|---|---|
| No-green-without-source in SystemCard | PASS — renders status received from API; API applies `safeCardStatus()` |
| No-green-without-source in health API | PASS — `safeCardStatus()` normalizes all stub_fallback entries to `unknown` |
| Authority boundary phrase in RGEPage | PASS — "RGE proposes only. CDE decides. SEL enforces." present on line 174 |
| No "RGE executes" UI text | PASS — button says "Propose to CDE", no execution claim |
| No "dashboard executes" UI text | PASS |
| No "PQX decides" UI text | PASS |
| No "CDE enforces" UI text | PASS |
| No "SEL decides" UI text | PASS |
| No "TPA overrides CDE silently" UI text | PASS |
| health API envelope completeness | PASS — `data_source`, `generated_at`, `source_artifacts_used`, `warnings` present |
| systems API envelope completeness | PASS — uses `buildSourceEnvelope()` |
| intelligence API envelope completeness | PASS — uses `buildSourceEnvelope()` |
| rge/analysis envelope completeness | PASS — uses `buildSourceEnvelope()` |
| rge/roadmap envelope completeness | PASS — uses `buildSourceEnvelope()` |
| rge/proposals GET envelope completeness | PASS — uses `buildSourceEnvelope()` |
| `stub_fallback` blocked from healthy in health route | PASS — `safeCardStatus()` maps stub healthy → unknown |
| `derived_estimate` blocked from healthy in signalStatus | PASS — normalizeSignalStatus() degrades to warning |
| `unknown` blocked from healthy | PASS — normalizeSignalStatus() degrades to unknown |
| RGEPage warnings banner on stub/unknown | PASS — `isFallback` check triggers warning display |
| RGEPage provisional badge on derived_estimate | PASS — `isProvisional` check shows badge |
| 3LS display grouping — visual only, IDs preserved | PASS — canonical system_ids unchanged in API |
| Authority role rendering (DSH-07) | PASS — SystemCard renders authority_role inline |
| classifySignalSource() decision order | PASS — unit tested, stub > nothing > partial > full |
| aggregateDataSource() worst-wins rule | PASS — unit tested |
| buildSourceEnvelope() single-rule helper | PASS — all routes delegate to this helper |

---

## Deployment Risks

### Risk 1 — Vercel artifact availability (HIGH)

Even with F-05/F-05b fixed, artifact availability on Vercel depends on:
1. `REPO_ROOT` env var set to the correct bundle root path
2. `outputFileTracingIncludes` successfully bundling `artifacts/**/*`
3. Artifact files being present in the deployed branch (they are in this repo)

If artifacts are missing or paths mismatch, all artifact-backed routes return `data_source: stub_fallback` with warnings. The dashboard remains functional but all signals are labeled as stubs. This is the correct fail-closed behavior.

**Mitigation:** After first Vercel preview deployment, verify that `/api/health` returns `source_artifacts_used` with at least one non-empty path. If `source_artifacts_used: []` on all routes, the `REPO_ROOT` value or the file tracing config needs adjustment.

### Risk 2 — outputFileTracingIncludes is experimental (MEDIUM)

`experimental.outputFileTracingIncludes` may behave differently across Next.js patch releases. The feature is noted as experimental by the build output. If it stops working, all artifact routes fall back gracefully to `stub_fallback`.

**Mitigation:** Pin the Next.js version in `package.json` before production deployment. Consider adding a smoke test that hits `/api/health` and asserts `source_artifacts_used.length > 0`.

### Risk 3 — `trends`, `compliance`, `incidents` are permanently stub_fallback (LOW)

No real artifact backing exists for these three routes. The dashboard correctly labels them stub_fallback with warnings. Consumers must not treat trend scores, compliance status, or incidents as operationally verified until real artifacts are wired.

---

## Must-Fix Items

All must-fix items were fixed in this PR:

| ID | Finding | Status |
|---|---|---|
| F-01 | trends route missing envelope + Math.random() | ✅ Fixed |
| F-02 | compliance route missing envelope | ✅ Fixed |
| F-03 | incidents route missing envelope | ✅ Fixed |
| F-04 | proposals POST missing envelope | ✅ Fixed |
| F-05 | artifactLoader no REPO_ROOT override | ✅ Fixed |
| F-05b | next.config.js no outputFileTracingRoot | ✅ Fixed |
| F-07 | RGEPage rge_can_operate green without source gate | ✅ Fixed |

---

## Residual Risks

| Risk | Severity | Notes |
|---|---|---|
| Vercel bundle root mismatch | HIGH | Requires manual verification post-deploy; documented in next.config.js |
| `trends`/`compliance`/`incidents` permanently stub_fallback | LOW | Correctly labeled; not a truth defect |
| `rge_max_autonomy: 'full'` when gapAnalysis missing | INFO | data_source is stub_fallback when no artifacts; warning banner shown; BLOCKED operational status shown |
| `derived_estimate` envelope-wide while individual signal (e.g. dashboard_truth_status) is from a single loaded artifact | INFO | Warning banner active when isProvisional; individual signal is accurately derived from its source |

---

## Production Recommendation

**Production readiness: NO**

Blockers before production:
1. Verify `REPO_ROOT` and `outputFileTracingIncludes` work correctly on a Vercel preview deployment
2. Confirm at least one artifact-backed route returns non-empty `source_artifacts_used` on Vercel preview
3. After verification passes, update this document with `production_ready: yes`

**Vercel preview readiness: CONDITIONAL**

Vercel preview deployment can proceed with these settings:
- Vercel project Root Directory: `apps/dashboard-3ls`
- Environment variable `REPO_ROOT` set to the Vercel function bundle root (`/var/task`)

If artifact paths do not resolve, the dashboard will still render correctly but all signals will be labeled `stub_fallback`. No truth defects will be silently introduced — the fail-closed behavior is confirmed by the test suite.
