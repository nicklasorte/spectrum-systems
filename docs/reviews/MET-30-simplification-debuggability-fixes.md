# MET-30 — Fixes for Red-Team #2 (MET-29)

## Prompt type
FIX

## Scope

Fix every `must_fix` finding from
`MET-29-simplification-debuggability-redteam.md`.

## Fixes

### Fix F1 — Compact sections cap items at 5

- **finding:** Compact panels rendering 20+ items overflow operator budget.
- **fix:** `apps/dashboard-3ls/app/page.tsx` defines
  `MET_COMPACT_ITEM_MAX = 5`. Every MET-19-33 panel uses
  `slice(0, MET_COMPACT_ITEM_MAX)` over its rendered list.
- **files changed:**
  - `apps/dashboard-3ls/app/page.tsx`
  - `apps/dashboard-3ls/__tests__/components/Met19_33Panels.test.tsx`
  - `tests/metrics/test_met_19_33_contract_selection.py`
- **tests added:**
  - jest: `compact sections do not render more than 5 items each`
  - pytest: `test_dashboard_page_compact_max_constant_present`
- **residual risk:** Future panels added without `MET_COMPACT_ITEM_MAX`
  could regress; the pytest constant check guards regression.

### Fix F2 — Debug index entries point to next_recommended_input

- **finding:** Debug entries without next inputs fail the 15-minute target.
- **fix:** Every `explanation_entries[]` carries
  `next_recommended_input` as a non-empty string. Pytest enforces it.
- **files changed:**
  - `artifacts/dashboard_metrics/debug_explanation_index_record.json`
  - `tests/metrics/test_met_19_33_contract_selection.py`
  - `apps/dashboard-3ls/__tests__/api/met-19-33-artifacts.test.ts`
- **tests added:**
  - `test_debug_explanation_index_targets_under_15_minutes`
  - `MET-25 — debug explanation index targets under 15 minutes` jest block
- **residual risk:** None — the test pins the contract.

### Fix F3 — Every new artifact justifies itself

- **finding:** Each MET artifact must carry failure_prevented and
  signal_improved.
- **fix:** All MET-19-33 artifacts include non-empty top-level
  `failure_prevented` and `signal_improved`. Pytest parameter-runs the
  check across every file.
- **files changed:**
  - `artifacts/dashboard_metrics/*` (all seven new MET-19-33 files)
  - `tests/metrics/test_met_19_33_contract_selection.py`
- **tests added:**
  - `test_met_19_33_artifact_failure_prevented_and_signal_improved`
- **residual risk:** None — fail-closed.

### Fix F4 — Duplicate-with-MET-04-18 paths are flagged

- **finding:** MET-09 and MET-06 overlap with MET-23 and MET-24.
- **fix:** MET-21 audit table marks them `fold_candidate`. The dependency
  index records the overlap with `keep_fold_remove = "fold_candidate"` and
  the rationale points at the MET-23/MET-24 replacements. Per the charter,
  **no existing artifact is removed in this PR** — fold/remove only
  follows a canonical-owner read. The reviewing owner therefore inherits a
  named handoff target rather than a deleted record.
- **files changed:**
  - `artifacts/dashboard_metrics/met_artifact_dependency_index_record.json`
  - `docs/reviews/MET-21-metric-usefulness-pruning-audit.md`
  - `tests/metrics/test_met_19_33_contract_selection.py`
- **tests added:**
  - `test_dependency_index_covers_met_19_33_paths` (validates the
    `keep_fold_remove` field is one of the allowed values).
- **residual risk:** None for this PR — the fold action stays advisory.

## Residual must_fix items

None. All MET-29 must_fix findings are fixed.
