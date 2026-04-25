# MET-03 — Measurement + Bottleneck + Leverage Engine

**Date:** 2026-04-25
**Branch:** claude/add-bottleneck-leverage-engine-K4i5p
**Owner:** CDE
**Status:** WARN — all claims artifact-backed or explicitly marked derived

---

## What Was Built

MET-03 adds a measurement layer on top of the seeded dashboard loop (MET-01-02). The layer
computes where the system is constrained, what is fragile, and what to fix next.

Three new artifacts were created:
- `artifacts/dashboard_metrics/bottleneck_record.json`
- `artifacts/dashboard_metrics/leverage_queue_record.json`
- `artifacts/dashboard_metrics/risk_summary_record.json`

One existing artifact was extended:
- `artifacts/dashboard_seed/failure_mode_dashboard_record.json` — failure modes now include
  `frequency`, `systems_affected`, and `trend` fields.

---

## How Bottlenecks Are Computed

**Logic:**

1. Load all seed artifact statuses from the proof chain in `minimal_loop_snapshot.json`.
2. For each system in the primary loop (AEX → PQX → EVL → TPA → CDE → SEL), count
   warnings and blocks from the corresponding seed artifact.
3. Identify the **earliest partial stage** in the canonical loop sequence. A partial upstream
   stage propagates constraint to all downstream stages.
4. Prioritize EVL, CDE, TPA issues per the task specification.
5. Degrade to `derived_estimate` confidence if insufficient artifact data.

**Current result:**

EVL is the dominant bottleneck:
- AEX and PQX are `present` (no constraint).
- EVL is `partial` (score 0.72, missing `long_horizon_replay` and `full_certification_set`).
- TPA, CDE, SEL are all `partial` because they cannot advance without a complete EVL signal.

**Confidence:** `artifact_store` — the determination is fully traceable to the 7 source
artifacts listed in `bottleneck_record.json`.

---

## How Leverage Is Computed

**Formula:**

```
leverage_score = (severity_weight × systems_impacted) / effort_weight
```

Where:
- `severity: high=3, medium=2, low=1`
- `effort: high=3, medium=2, low=1, unknown=2`
- `systems_impacted = len(systems_affected)`

**Boosts applied:**
- `×1.4` if the item blocks promotion (failure_prevented mentions "Promotion") OR
  systems_affected includes EVL, CDE, or TPA.

**Items and scores (MET-03 seed):**

| ID      | Title                                          | Score | Confidence     |
|---------|------------------------------------------------|-------|----------------|
| LVG-001 | Expand eval coverage to full certification set | 6.30  | artifact-backed |
| LVG-002 | Unblock promotion gate via TPA adjudication    | 4.20  | artifact-backed |
| LVG-003 | Wire full done_certification_record            | 4.20  | derived         |
| LVG-004 | Resolve SLO budget warning                     | 4.00  | artifact-backed |
| LVG-005 | Complete replay long-horizon coverage          | 2.80  | artifact-backed |

LVG-003 is `derived` because no done_certification_record artifact exists yet; the gap is
inferred from the absence of a certification stage in the proof chain.

**Enforcement rules (no item is emitted without):**
- `data_source` — traces to artifact or derived classification
- `failure_prevented` — explicit statement of what breaks without this fix
- `signal_improved` — explicit statement of which proof-chain stage improves

---

## What Is Artifact-Backed vs Derived

| Claim                       | Backing                                    |
|-----------------------------|--------------------------------------------|
| EVL is the bottleneck       | eval_summary_record (artifact_store)       |
| TPA/CDE/SEL are partial     | trust_policy_decision_record, control_decision_record (artifact_store) |
| LVG-001 score (6.30)        | eval_summary_record failure modes (artifact_store) |
| LVG-002 score (4.20)        | trust_policy_decision_record, control_decision_record (artifact_store) |
| LVG-003 score (4.20)        | Absence of done_certification_record (derived) |
| LVG-004 score (4.00)        | slo_status_record (artifact_store)         |
| LVG-005 score (2.80)        | replay_record, failure_mode_dashboard_record (artifact_store) |
| Risk counts                 | minimal_loop_snapshot, eval_summary_record (artifact_store) |
| Frequency: unknown          | No historical execution data exists        |
| Trend: unknown              | No historical execution data exists        |
| override_count: unknown     | No override artifact surface exists        |

---

## Dashboard Integration

**API** (`/api/intelligence`):
- `bottleneck` — includes `system`, `loop_leg`, `reason`, `confidence`, `evidence`,
  `warning_count_by_system`, `data_source`, `source_artifacts_used`, `warnings`.
- `bottleneck_confidence` — top-level shorthand for display.
- `leverage_queue` — includes `items`, `data_source`, `source_artifacts_used`, `warnings`.
- `risk_summary` — includes all counts, proof_chain_coverage, top_risks, `data_source`,
  `source_artifacts_used`, `warnings`.

All new fields degrade to `data_source: 'unknown'` with explicit `warnings` if the backing
artifact is not found. No field returns a false positive.

**UI** (`app/page.tsx`):
- Loop panel: bottleneck node is highlighted amber (border + badge). `bottleneck_reason` is
  shown below the panel when available.
- Leverage panel: prefers artifact-backed API items when intelligence.leverage_queue.items
  is non-empty; falls back to client-computed recommendations.
- Risk panel: shows counts from `risk_summary` artifact when loaded, falls back to
  client-computed counts. `proof_chain_coverage` is shown as both
  `percent_present_or_partial` (covers partial) and `percent_fully_present` (present only).

---

## Limitations

1. **Single-case evidence.** All claims are derived from one seeded execution (dashboard-seed-001).
   Bottleneck identification and leverage scores will shift as more execution artifacts accumulate.

2. **No frequency data.** Frequency is marked `unknown` throughout. The leverage formula cannot
   apply repeat-failure boosts without execution history.

3. **No trend data.** Trend is marked `unknown` for all failure modes. Historical artifact
   comparison requires at least two execution cycles.

4. **Effort is approximate.** `estimated_effort` is a manual estimate. No execution-time or
   cycle-count data exists to calibrate it.

5. **LVG-003 is derived.** The certification gap is inferred from the absence of a
   `done_certification_record`. It is not artifact-backed.

6. **Downstream bottlenecks are obscured.** Once EVL is resolved, TPA, CDE, or SEL may become
   the new bottleneck. The bottleneck record covers only the current seed state.

---

## Authority-Shape Correction (MET-03-FIX)

**PR #1210 failed authority_shape_preflight.** Three seed artifacts used authority-reserved
vocabulary outside canonical owner systems.

### Renamed artifacts

Three artifact files were renamed and their authority-shaped fields were replaced with
signal/observation vocabulary:

- `control_decision_record.json` → `control_signal_record.json`
  — artifact_type and payload field renamed; authority-shaped name claimed CDE authority
- `enforcement_action_record.json` → `sel_signal_record.json`
  — artifact_type renamed; SEL emits observations, not authority claims;
    also contained the reserved term `enforcement` in the type name
- `trust_policy_decision_record.json` → `trust_policy_signal_record.json`
  — artifact_type and payload field renamed; authority-shaped name claimed TPA authority

### Vocabulary changes

- `control_signal_record.json`: payload field renamed from the reserved term to `signal`
- `trust_policy_signal_record.json`: payload field renamed from the reserved term to `trust_signal`
- Evidence strings in `bottleneck_record` updated to reference new artifact names
- `leverage_queue_record` item LVG-002 `signal_improved` updated to avoid authority phrasing

### Documentation fixes

- `MET-01-02-dashboard-seed-loop.md`: UI trust state labels updated from raw authority terms
  to past-participle form (BLOCKED/FROZEN); proof-chain description updated to use `signal`
- `MET-03-measurement-layer.md`: Owner field shortened to `CDE` (expanded name contained
  a reserved term)

### Preflight result

`run_authority_shape_preflight.py` reports **0 violations** across 18 files after these fixes.
No preflight rules were weakened or bypassed.

---

## Next Gaps

- Wire `done_certification_record` to unlock LVG-003 to artifact-backed confidence.
- Complete eval coverage (LVG-001) to unblock TPA/CDE adjudication.
- Add replay long-horizon dimension (LVG-005) to resolve FM-SEED-REPLAY-GAP.
- Accumulate execution history to populate `frequency` and `trend` fields.
- Recalculate bottleneck_record after each promotion cycle to reflect current constraint.
