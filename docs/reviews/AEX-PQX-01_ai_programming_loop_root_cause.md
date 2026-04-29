# AEX-PQX-01 — AI Programming Loop Root Cause Analysis

**Status:** BLOCK  
**Created:** 2026-04-29  
**Owner:** MET (observation only)  
**Authority disclaimer:** MET does not admit, execute, eval, decide, or enforce.
AEX owns admission. PQX owns execution. EVL owns eval. CDE owns control.
SEL owns enforcement.

---

## Purpose

Root cause the missing AEX → PQX → EVL → TPA → CDE → SEL evidence for all
known AI programming work items so that the dashboard can render honest,
artifact-backed compliance status rather than inferring absence as presence.

---

## Method

Inspected the following artifacts:

- `artifacts/dashboard_metrics/ai_programming_governed_path_record.json`
- `artifacts/dashboard_metrics/governance_violation_record.json`
- `artifacts/aex/aex_admission_evidence_record.json`
- `artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`
- `artifacts/rdx_runs/ROADMAP-APPLY-01-artifact-trace.json`
- `artifacts/dashboard_seed/lineage_record.json`
- `artifacts/dashboard_seed/control_decision_record.json`
- `artifacts/dashboard_seed/enforcement_action_record.json`
- `artifacts/dashboard_seed/eval_summary_record.json`
- `docs/architecture/system_registry.md`

---

## Work Item Roster

### 1. AIPG-CODEX-001

| Field | Value |
|---|---|
| work_item_id | AIPG-CODEX-001 |
| tool_source | codex |
| repo_mutating | true |
| branch_ref | unknown |
| pr_ref | unknown |

**Per-leg evidence status:**

| Leg | Status | Artifact Refs | Reason Codes |
|---|---|---|---|
| AEX | missing | — | `aex_intake_record_not_linked_to_work_item` |
| PQX | present | `artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`, `artifacts/pqx_runs/pqx_003/admitted_slices_20.json` | — |
| EVL | partial | `outputs/contract_preflight/preflight.pqx_execution_eval_result.json` (from preflight slice) | `eval_coverage_partial_preflight_only` |
| TPA | unknown | — | `no_tpa_record_linked_to_work_item` |
| CDE | unknown | — | `no_cde_record_linked_to_work_item` |
| SEL | unknown | — | `no_sel_record_linked_to_work_item` |

**Missing artifact refs:**
- No AEX admission_evidence_record with `work_item_id=AIPG-CODEX-001`

**Reason codes for missing legs:**
- `aex_intake_record_not_linked_to_work_item` — AEX admission evidence exists (`aex_admission_evidence_record.json`) but references `req-aex-trust-01-1`, not AIPG-CODEX-001. Cannot assert the preflight Codex run traversed AEX for this specific work item.
- `eval_coverage_partial_preflight_only` — EVL artifacts emitted by the PQX preflight slice are for the slice run, not for this specific Codex work item.

**Backfill allowed:** Yes, from preflight PQX evidence. AEX backfill is partial only; cannot establish retroactive AEX admission for this work item.

**Human review required:** No for PQX/EVL. Yes for AEX backfill (cannot prove AEX admission retroactively without an AEX-owned artifact naming this work item).

---

### 2. AIPG-CLAUDE-001

| Field | Value |
|---|---|
| work_item_id | AIPG-CLAUDE-001 |
| tool_source | claude |
| repo_mutating | true |
| branch_ref | claude/ai-governed-path-dashboard-ypm4c |
| pr_ref | unknown |

**Per-leg evidence status:**

| Leg | Status | Artifact Refs | Reason Codes |
|---|---|---|---|
| AEX | partial | `artifacts/rdx_runs/ROADMAP-APPLY-01-artifact-trace.json` | `aex_evidence_is_rdx_trace_not_admission_record` |
| PQX | missing | — | `no_pqx_execution_record_for_claude_branch` |
| EVL | partial | `artifacts/rdx_runs/ROADMAP-APPLY-01-artifact-trace.json` | `eval_evidence_from_rdx_trace_not_evl_record` |
| TPA | unknown | — | `no_tpa_record_linked_to_work_item` |
| CDE | unknown | — | `no_cde_record_linked_to_work_item` |
| SEL | unknown | — | `no_sel_record_linked_to_work_item` |

**Missing artifact refs:**
- No PQX `pqx_slice_execution_record` with work_item_id=AIPG-CLAUDE-001
- No AEX `admission_evidence_record` with work_item_id=AIPG-CLAUDE-001 (only indirect RDX trace)

**Reason codes for missing legs:**
- `aex_evidence_is_rdx_trace_not_admission_record` — The RDX trace shows a governed roadmap-apply step was executed, but does not constitute an AEX admission record.
- `no_pqx_execution_record_for_claude_branch` — The Claude branch made direct repo mutations without a PQX execution record linking the branch to PQX authority.
- `eval_evidence_from_rdx_trace_not_evl_record` — RDX trace contains evaluation signals but is not an EVL-owned eval artifact.

**Backfill allowed:** Partial. AEX can be upgraded from partial to present if an AEX admission record is produced for this work item. PQX cannot be backfilled retroactively without PQX-owned execution artifacts.

**Human review required:** Yes for PQX. The missing PQX leg represents a governance gap that requires a human to confirm the scope of execution and whether a PQX record can be retroactively produced.

---

### 3. AEX-PQX-DASH-02

| Field | Value |
|---|---|
| work_item_id | AEX-PQX-DASH-02 |
| tool_source | claude |
| repo_mutating | true |
| branch_ref | unknown (dashboard implementation branch) |
| pr_ref | unknown |

**Context:** AEX-PQX-DASH-02 is the work item ID assigned to the AI Programming
Governance dashboard implementation (the dashboard panel, helper, API route,
and tests). This work was performed by Claude. It is referenced in
`governance_violation_record.json` violations GVL-AEX-MISSING-CLAUDE-001,
GVL-PQX-MISSING-CLAUDE-001, and GVL-CDE-MISSING-UNKNOWN-001 but is NOT
present in `ai_programming_governed_path_record.json`'s `ai_programming_work_items`
array. This is the primary gap that makes the dashboard unable to surface its
own governance status.

**Per-leg evidence status:**

| Leg | Status | Artifact Refs | Reason Codes |
|---|---|---|---|
| AEX | missing | — | `no_aex_intake_record_for_dashboard_implementation`, `dashboard_built_before_aex_intake_instrumented` |
| PQX | missing | — | `no_pqx_execution_record_for_dashboard_implementation`, `dashboard_built_before_pqx_wrapper_in_place` |
| EVL | unknown | — | `no_evl_artifact_for_dashboard_work_item` |
| TPA | unknown | — | `no_tpa_record_for_dashboard_work_item` |
| CDE | unknown | — | `no_cde_record_for_dashboard_work_item` |
| SEL | unknown | — | `no_sel_record_for_dashboard_work_item` |

**Missing artifact refs:**
- No AEX `admission_evidence_record` naming work_item_id=AEX-PQX-DASH-02
- No PQX `pqx_slice_execution_record` naming work_item_id=AEX-PQX-DASH-02
- No EVL, TPA, CDE, or SEL artifacts for this work item

**Reason codes for all missing legs:**
- `dashboard_built_before_aex_intake_instrumented` — The AEX-PQX-DASH-01 dashboard work predates the requirement to emit AEX intake records for Claude-driven repo mutations, creating a bootstrap gap.
- `no_pqx_execution_record_for_dashboard_implementation` — PQX does not have a retrospective execution record for the dashboard files written. No `run_codex_to_pqx_wrapper.py` or equivalent was invoked.
- `retroactive_backfill_not_possible` — Because no AEX admission or PQX execution evidence was captured at time of execution, the legs cannot be backfilled with high confidence. Only partial evidence (PR body, branch name, file changes) is available.

**Backfill allowed:** Partial only. Cannot assert present status; can only emit an explicit missing-evidence record explaining why proof cannot be established.

**Human review required:** Yes. The missing AEX and PQX legs represent a fundamental governance gap for a repo-mutating Claude work item. A human must review whether retrospective evidence can be produced or whether this work item will permanently carry missing legs.

---

### 4. AEX-PQX-DASH-02-CODEX-PRECURSOR

| Field | Value |
|---|---|
| work_item_id | AEX-PQX-DASH-02-CODEX-PRECURSOR |
| tool_source | codex |
| repo_mutating | true |
| branch_ref | unknown (Codex precursor to dashboard implementation) |
| pr_ref | unknown |

**Context:** AEX-PQX-DASH-02-CODEX-PRECURSOR is the Codex work item that preceded
the Claude dashboard implementation. It is referenced in
`governance_violation_record.json` violation GVL-LINEAGE-MISSING-CODEX-001.
AEX and PQX evidence exist in the repo (from preflight records) but no lineage
chain links AEX intake → PQX execution → EVL evaluation specifically for this
work item. It is also NOT present in `ai_programming_governed_path_record.json`.

**Per-leg evidence status:**

| Leg | Status | Artifact Refs | Reason Codes |
|---|---|---|---|
| AEX | partial | `artifacts/aex/aex_admission_evidence_record.json` | `aex_record_not_explicitly_named_for_this_work_item` |
| PQX | partial | `artifacts/pqx_runs/preflight.pqx_slice_execution_record.json` | `pqx_record_is_preflight_slice_not_work_item_specific` |
| EVL | partial | `outputs/contract_preflight/preflight.pqx_execution_eval_result.json` | `eval_from_preflight_slice_not_work_item_specific` |
| TPA | unknown | — | `no_tpa_record_for_codex_precursor` |
| CDE | unknown | — | `no_cde_record_for_codex_precursor` |
| SEL | unknown | — | `no_sel_record_for_codex_precursor` |
| Lineage | missing | — | `no_lineage_chain_linking_aex_pqx_evl_for_this_work_item` |

**Missing artifact refs:**
- No lineage_record entry linking `aex_admission_evidence_record.json` → `preflight.pqx_slice_execution_record.json` → EVL artifact for this specific work item
- No TPA, CDE, or SEL artifacts

**Reason codes:**
- `aex_record_not_explicitly_named_for_this_work_item` — The AEX admission evidence exists (`req-aex-trust-01-1`) but is not explicitly named for AEX-PQX-DASH-02-CODEX-PRECURSOR.
- `no_lineage_chain_linking_aex_pqx_evl_for_this_work_item` — The `dashboard_seed/lineage_record.json` links seeded chain artifacts, not the Codex precursor work item chain.
- `pqx_record_is_preflight_slice_not_work_item_specific` — The PQX preflight slice record covers a general preflight execution, not a work-item-specific run.

**Backfill allowed:** Yes — partial lineage can be constructed from existing evidence. The AEX and PQX records are "partial" rather than "missing" because they exist in the repo; they are simply not explicitly tagged to this work item.

**Human review required:** No — a partial lineage artifact can be emitted using existing source evidence, clearly marking it as partial with reason codes.

---

## Summary Table

| Work Item | Tool | Repo-Mutating | AEX | PQX | EVL | TPA | CDE | SEL | Backfill Allowed | Human Review |
|---|---|---|---|---|---|---|---|---|---|---|
| AIPG-CODEX-001 | codex | true | missing | present | partial | unknown | unknown | unknown | partial | yes (AEX) |
| AIPG-CLAUDE-001 | claude | true | partial | missing | partial | unknown | unknown | unknown | partial | yes (PQX) |
| AEX-PQX-DASH-02 | claude | true | missing | missing | unknown | unknown | unknown | unknown | partial only | yes |
| AEX-PQX-DASH-02-CODEX-PRECURSOR | codex | true | partial | partial | partial | unknown | unknown | unknown | yes | no |

---

## Root Cause Patterns

1. **Bootstrap gap** — The AEX-PQX-DASH-01 dashboard panel was built before AEX
   intake and PQX execution records were required for Claude-driven repo mutations.
   This creates a self-referential governance gap: the governance dashboard itself
   lacks the governance evidence it requires of others.

2. **Work item not registered in path record** — AEX-PQX-DASH-02 and
   AEX-PQX-DASH-02-CODEX-PRECURSOR appear in `governance_violation_record.json`
   violations but are absent from `ai_programming_governed_path_record.json`'s
   `ai_programming_work_items` array, so the dashboard cannot surface their
   evidence status.

3. **Preflight evidence is not work-item-specific** — PQX and AEX artifacts from
   the preflight run (`req-aex-trust-01-1`, `pqx-slice-20260403T094715Z`) are
   general-purpose and not bound to specific work item IDs. Evidence exists but
   cannot be asserted as "present" for a named work item without explicit naming.

4. **Lineage record is seeded, not derived** — The `lineage_record.json` links
   seeded dashboard artifacts, not real work item chains, so none of the AI
   programming work items have lineage evidence.

5. **No rollup builder exists** — The `ai_programming_governed_path_record.json`
   is hand-authored, not generated. There is no deterministic builder that reads
   source evidence and produces the rollup, meaning the dashboard truth is
   maintained manually and can drift.

---

## Remediation Required

1. Add AEX-PQX-DASH-02 and AEX-PQX-DASH-02-CODEX-PRECURSOR to
   `ai_programming_governed_path_record.json` with honest evidence status.

2. Create source evidence artifacts in `artifacts/ai_programming/` for all
   four work items, including explicit missing-evidence records where proof
   cannot be established.

3. Create a deterministic rollup builder script that reads
   `artifacts/ai_programming/` and regenerates the governed path record.

4. Add 3LS loop run records (SMA artifacts) for each work item so the
   measurement layer can observe loop completion status.

5. Register new schemas in `contracts/standards-manifest.json`.

6. Add tests enforcing the fail-closed contract: missing AEX or PQX for a
   repo-mutating work item must remain BLOCK.

**What must NOT happen:**
- Do not mark AEX or PQX as "present" for AEX-PQX-DASH-02 without an artifact.
- Do not remove AEX-PQX-DASH-02 from the violation list to make the score green.
- Do not infer "unknown" as "present" in any computed field.
