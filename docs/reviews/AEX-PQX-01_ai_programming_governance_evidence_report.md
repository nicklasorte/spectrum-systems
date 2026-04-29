# AEX-PQX-01 — AI Programming Governance Evidence Report

**Status:** BLOCK (honest — boot­strap gap acknowledged, not hidden)  
**Created:** 2026-04-29  
**Branch:** `claude/backfill-ai-governance-evidence-lde9G`  
**Authority disclaimer:** MET observes. AEX owns admission. PQX owns execution.
EVL owns eval. CDE owns control. SEL owns enforcement.

---

## Dashboard State Before Fix

| Field | Before |
|---|---|
| AI Programming Governance | BLOCK |
| score | 1/6 |
| AEX | present (**wrong** — no work item had AEX present) |
| PQX | missing |
| EVL | unknown |
| TPA | missing |
| CDE | unknown |
| SEL | missing |
| repo_mutating | true |
| core_loop_complete | false |
| violation_count | 4 |
| work_items surfaced | 3 (AIPG-CODEX-001, AIPG-CLAUDE-001, AIPG-UNKNOWN-001) |
| AEX-PQX-DASH-02 in work items | **no** (unreported bootstrap gap) |
| AEX-PQX-DASH-02-CODEX-PRECURSOR in work items | **no** (unreported) |

The v1 artifact incorrectly declared `core_loop_compliance.AEX = "present"` even
though no work item had `aex_admission_observation = "present"`. This was a data
inconsistency introduced when the governing record was hand-authored without a
deterministic builder.

---

## Dashboard State After Fix

| Field | After |
|---|---|
| AI Programming Governance | BLOCK (unchanged — still BLOCK, more honest) |
| score | 0/6 (corrected from 1/6) |
| AEX | missing (corrected) |
| PQX | missing (unchanged) |
| EVL | partial (corrected from "unknown") |
| TPA | unknown (unchanged) |
| CDE | unknown (unchanged) |
| SEL | unknown (corrected from "missing") |
| repo_mutating | true |
| core_loop_complete | false |
| violation_count | 6 (corrected from 4; AIPG-CODEX-001 AEX + AIPG-CLAUDE-001 PQX added) |
| work_items surfaced | 5 (added AEX-PQX-DASH-02 and AEX-PQX-DASH-02-CODEX-PRECURSOR) |

The dashboard remains BLOCK. The fix makes it MORE honest, not green.

---

## Artifacts and Source Records Inspected

| Artifact | Finding |
|---|---|
| `artifacts/dashboard_metrics/ai_programming_governed_path_record.json` | v1 hand-authored; `core_loop_compliance.AEX` wrongly "present"; missing AEX-PQX-DASH-02 and CODEX-PRECURSOR work items |
| `artifacts/dashboard_metrics/governance_violation_record.json` | Had 4 violations; referenced AEX-PQX-DASH-02 and CODEX-PRECURSOR but they weren't in governed_path work_items |
| `artifacts/aex/aex_admission_evidence_record.json` | Exists; references req-aex-trust-01-1, not any specific AI programming work item |
| `artifacts/pqx_runs/preflight.pqx_slice_execution_record.json` | Exists; general preflight slice, not work-item-specific |
| `artifacts/rdx_runs/ROADMAP-APPLY-01-artifact-trace.json` | Partial AEX evidence for AIPG-CLAUDE-001 (RDX trace, not AEX-owned record) |
| `artifacts/ai_programming/` | **Did not exist** before this change |
| `contracts/schemas/ai_programming_*` | **Did not exist** before this change |
| `scripts/build_ai_programming_governance_rollup.py` | **Did not exist** — no deterministic builder existed |
| `tests/metrics/test_ai_programming_governance_rollup.py` | **Did not exist** before this change |

---

## Work Items Found and Evidence Status

| Work Item | Tool | AEX | PQX | EVL | TPA | CDE | SEL | Lineage | Compliance |
|---|---|---|---|---|---|---|---|---|---|
| AIPG-CODEX-001 | codex | missing | present | partial | unknown | unknown | unknown | missing | BLOCK |
| AIPG-CLAUDE-001 | claude | partial | missing | partial | unknown | unknown | unknown | partial | BLOCK |
| AEX-PQX-DASH-02 | claude | missing | missing | unknown | unknown | unknown | unknown | missing | BLOCK |
| AEX-PQX-DASH-02-CODEX-PRECURSOR | codex | partial | partial | partial | unknown | unknown | unknown | missing | BLOCK |
| AIPG-UNKNOWN-001 | unknown | unknown | unknown | unknown | unknown | unknown | unknown | unknown | BLOCK |

---

## Backfilled Records Created

| Artifact | Type | Notes |
|---|---|---|
| `artifacts/ai_programming/aipg_codex_001_work_item_record.json` | `ai_programming_work_item_record` | AEX missing; PQX present (preflight); reason codes explicit |
| `artifacts/ai_programming/aipg_claude_001_work_item_record.json` | `ai_programming_work_item_record` | AEX partial (RDX trace); PQX missing; reason codes explicit |
| `artifacts/ai_programming/aex_pqx_dash_02_missing_evidence.json` | `ai_programming_work_item_record` | Both AEX and PQX missing; bootstrap gap documented; human review required |
| `artifacts/ai_programming/aex_pqx_dash_02_codex_precursor_partial_lineage.json` | `ai_programming_work_item_record` | AEX/PQX/EVL all partial; lineage missing; backfill allowed |
| `artifacts/ai_programming/aipg_codex_001_loop_run_record.json` | `3ls_loop_run_record` | loop_status=partial; first_failure_system=AEX |
| `artifacts/ai_programming/aipg_claude_001_loop_run_record.json` | `3ls_loop_run_record` | loop_status=partial; first_failure_system=AEX |
| `artifacts/ai_programming/aex_pqx_dash_02_loop_run_record.json` | `3ls_loop_run_record` | loop_status=blocked; first_failure_system=AEX |
| `artifacts/ai_programming/aex_pqx_dash_02_codex_precursor_loop_run_record.json` | `3ls_loop_run_record` | loop_status=partial; first_failure_system=EVL |
| `artifacts/ai_programming/ai_programming_governance_rollup.json` | `ai_programming_governance_rollup_record` | Generated by builder; compliance=BLOCK; score=0.0 |

---

## Missing Evidence That Remains Unprovable

| Work Item | Leg | Why Unprovable |
|---|---|---|
| AEX-PQX-DASH-02 | AEX | Dashboard implementation pre-dated AEX intake instrumentation (bootstrap gap). No AEX-owned artifact names this work item. Human review required. |
| AEX-PQX-DASH-02 | PQX | No PQX execution record was emitted for the dashboard files. No `run_codex_to_pqx_wrapper.py` was invoked. Human review required. |
| AIPG-CODEX-001 | AEX | Existing `aex_admission_evidence_record.json` references req-aex-trust-01-1, not AIPG-CODEX-001. Cannot assert retroactively without AEX-owned artifact naming this work item. |
| AIPG-CLAUDE-001 | PQX | Branch `claude/ai-governed-path-dashboard-ypm4c` made direct repo mutations without a PQX execution record. Cannot backfill retroactively without PQX-owned artifact. |
| All items | TPA/CDE/SEL | No TPA, CDE, or SEL artifacts exist for any AI programming work item. These require the canonical systems to emit artifacts. |

---

## Rollup Artifact

**Path:** `artifacts/ai_programming/ai_programming_governance_rollup.json`

**Builder:** `scripts/build_ai_programming_governance_rollup.py`

Key fields:
```json
{
  "compliance_status": "BLOCK",
  "score": 0.0,
  "total_ai_programming_items": 4,
  "codex_work_count": 2,
  "claude_work_count": 2,
  "repo_mutating_count": 4,
  "with_aex_evidence": 0,
  "with_pqx_evidence": 1,
  "full_loop_complete_count": 0,
  "per_leg_counts": {
    "AEX": {"present": 0, "partial": 2, "missing": 2, "unknown": 0},
    "PQX": {"present": 1, "partial": 1, "missing": 2, "unknown": 0},
    "EVL": {"present": 0, "partial": 3, "missing": 0, "unknown": 1}
  }
}
```

---

## SMA Artifact Refs

| Work Item | SMA Record | Loop Status |
|---|---|---|
| AIPG-CODEX-001 | `artifacts/ai_programming/aipg_codex_001_loop_run_record.json` | partial (first_failure: AEX) |
| AIPG-CLAUDE-001 | `artifacts/ai_programming/aipg_claude_001_loop_run_record.json` | partial (first_failure: AEX) |
| AEX-PQX-DASH-02 | `artifacts/ai_programming/aex_pqx_dash_02_loop_run_record.json` | blocked (first_failure: AEX) |
| AEX-PQX-DASH-02-CODEX-PRECURSOR | `artifacts/ai_programming/aex_pqx_dash_02_codex_precursor_loop_run_record.json` | partial (first_failure: EVL) |

All SMA records are referenced in `rollup.sma_artifact_refs`.

---

## New Schemas Registered

| Schema | Class | Notes |
|---|---|---|
| `ai_programming_work_item_record` | governance | Per-work-item evidence; fail-closed rules enforced |
| `ai_programming_governance_rollup_record` | governance | Aggregate rollup produced by builder |
| `ai_programming_loop_violation_record` | governance | Per-violation observation |

All three registered in `contracts/standards-manifest.json` under `introduced_in: AEX-PQX-01`.

---

## Tests Run

| Test Suite | Result |
|---|---|
| `tests/metrics/test_ai_programming_governance_rollup.py` (36 tests, new) | **36 passed** |
| `tests/metrics/test_ai_programming_governed_path_dashboard.py` (15 tests, existing) | **15 passed** |
| `tests/ -k "ai_programming or aex_pqx or 3ls or measurement or dashboard or tls or met"` | **1709 passed, 1 skipped** |

---

## Final Governance Status

| Check | Result |
|---|---|
| AI programming loop evidence is artifact-backed | ✓ Per-work-item records in `artifacts/ai_programming/` |
| Missing legs are explicit and honest | ✓ Missing legs carry reason_codes; no inference |
| AEX/PQX gaps cannot be silently hidden | ✓ Tests enforce this; BLOCK propagates |
| Repo-mutating work without AEX/PQX remains BLOCK | ✓ Confirmed: all 4 repo-mutating items are BLOCK |
| Dashboard reads rollup artifacts instead of computing truth | ✓ Route reads artifact; computeGovernedPathSummary() server-side |
| SMA measurement artifacts are referenced | ✓ 4 3ls_loop_run_records; refs in rollup |
| Tests prove missing evidence blocks | ✓ 10 new tests for fail-closed behavior |
| No authority boundaries changed | ✓ MET observes only; AEX/PQX/EVL/CDE/SEL authority unchanged |
| No fake compliance introduced | ✓ Score corrected from 1/6 to 0/6; dashboard stays BLOCK |

---

## Remaining Risks

1. **Bootstrap gap is permanent until human review:** AEX-PQX-DASH-02 cannot have
   its AEX and PQX legs upgraded to "present" without a human confirming whether
   retroactive evidence can be produced. The missing-evidence record explicitly
   documents this.

2. **TPA/CDE/SEL gaps require canonical system action:** None of the AI programming
   work items have TPA trust records, CDE control decisions, or SEL enforcement
   signals. These cannot be backfilled by MET; they require the canonical authority
   systems to emit artifacts naming the work items.

3. **AIPG-UNKNOWN-001 classification unknown:** The tool source for AIPG-UNKNOWN-001
   remains "unknown_ai_agent". Classifying it as codex or claude would allow proper
   AEX/PQX evidence attachment.

4. **Rollup reads from `artifacts/ai_programming/` only:** Work items in the
   `ai_programming_governed_path_record.json` that have no corresponding work_item_record
   (e.g., AIPG-UNKNOWN-001) are not included in the rollup counts. This is intentional:
   the rollup only reflects items with source evidence records.

---

## Next Recommended Prompt

```
SMA-02 — Wire TPA, CDE, and SEL evidence for AI programming work items.

For each of the four known AI programming work items:
- Request TPA trust/policy record from TPA authority
- Request CDE control decision record from CDE authority
- Request SEL enforcement signal from SEL authority
- Link all three to the existing 3ls_loop_run_records via policy_ref,
  decision_input_ref, and enforcement_signal_ref

Once these are attached, the full loop can be declared complete for at
least one work item and the score can increase above 0/6.

Do not fabricate these records. Only emit them when the canonical systems
produce them.
```
