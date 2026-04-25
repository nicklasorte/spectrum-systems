# DSH-11A-F Review — Visual Leverage + Bottleneck Dashboard

## Prompt type
BUILD

## Panels added

1. **Trust Posture**
   - Adds PASS/WARN/FREEZE/BLOCK trust-state banner.
   - Shows top reason codes, source mix counts, and artifact-backed percentage.

2. **Governed Loop + Bottleneck**
   - Renders AEX → PQX → EVL → TPA → CDE → SEL plus REP/LIN/OBS/SLO overlays.
   - Shows system id, authority role, status, data_source, and warning count per node.
   - Shows current bottleneck and bottleneck confidence source label.

3. **Proof Chain**
   - Adds Source → Output → Eval → Control → Enforcement → Certification stage status rows.
   - Shows present/partial/missing/unknown state, data_source, reason_codes, and coverage %.
   - Missing Eval or lineage visibility drives BLOCK posture.

4. **Fragility + Risk Snapshot**
   - Adds fallback/unknown/missing-eval/missing-trace/override counts.
   - Lists top failure modes from intelligence risks + operational signal warnings.
   - Trend explicitly marked `unknown` when no historical artifacts exist.

5. **Leverage Queue**
   - Adds ranked top fixes with title, failure_prevented, signal_improved, systems affected,
     severity, effort, source, confidence, and leverage_score.
   - Ranking formula uses severity × impacted systems ÷ effort with boosts for promotion blockers,
     EVL/CDE/TPA impact, and fallback/unknown reduction value.

6. **RGE Readiness**
   - Adds `rge_can_operate`, `data_source`, `context_maturity_level`, `mg_kernel_status`, and
     `active_drift_legs`.
   - Enforces unverified rendering for derived_estimate/stub_fallback.
   - Displays authority statement: **RGE proposes only. CDE decides. SEL enforces.**

## Data sources used

- `/api/health` for per-system loop status + source mix.
- `/api/intelligence` for bottleneck/risk/certification context.
- `/api/systems` for source artifact presence in proof-chain source stage.
- `/api/rge/analysis` for readiness and maturity posture.

## Artifact-backed vs derived vs fallback

- **Artifact-backed**: source envelopes and intelligence stages when API returns `artifact_store` or
  `repo_registry`.
- **Derived**: bottleneck fallback derivation and leverage ranking arithmetic.
- **Provisional (derived_estimate)**: explicitly badged as provisional.
- **Fallback/unknown**: never allowed to render healthy state; downgraded in trust posture and risk.

## Known gaps

- Health route still relies heavily on stub-backed system rows; trust posture therefore trends FREEZE/BLOCK.
- Override count is not exposed by current APIs and remains `unknown`.
- Historical trend artifacts are not currently provided, so trend remains `unknown` by rule.

## Next recommended improvements

1. Replace stub-backed health rows with real per-system health artifacts.
2. Add explicit override artifact and expose via `/api/intelligence` or `/api/health`.
3. Add historical snapshot API to unlock artifact-backed trend lines (without inference).
4. Add per-stage reason-code contracts from upstream APIs to reduce derived reasoning in UI.
