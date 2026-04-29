# AEX-PQX-DASH-01 — AI Programming Governed Path Dashboard

## Authority disclaimer

MET observes AI programming path evidence only.

- AEX owns admission.
- PQX owns execution.
- EVL owns eval.
- CDE owns control.
- SEL owns enforcement.

Dashboard does not execute anything. The AI Programming Governed Path panel is
an observation surface backed by `artifact_store` evidence; it does not admit
work, route execution, evaluate outcomes, take CDE control inputs, or apply
SEL enforcement signals. Authority remains canonical to the systems above.

## What was built

1. `artifacts/dashboard_metrics/ai_programming_governed_path_record.json` —
   MET-owned observation artifact recording AI programming work items
   (Codex, Claude, unknown_ai_agent), their declared `repo_mutating` state,
   and per-leg AEX / PQX / EVL / control-signal / SEL-readiness-signal /
   lineage observations. Each work item carries a `bypass_risk` value, a
   `next_recommended_input`, and a `source_artifacts_used` list.
2. `apps/dashboard-3ls/lib/aiProgrammingGovernance.ts` — pure-function helper
   that normalises agent type and presence values, computes a per-item
   governed-path status under the AEX-PQX-DASH-01 rules, and aggregates a
   summary. The helper makes no network calls and reads no live state.
3. `apps/dashboard-3ls/app/api/intelligence/route.ts` — reads the artifact
   via `loadArtifact` and exposes a new `ai_programming_governed_path` block
   on `/api/intelligence`. The block surfaces `status`, `data_source`,
   `source_artifacts_used`, `warnings`, `reason_codes`, Codex / Claude /
   AEX-present / PQX-present / governed / bypass-risk / unknown-path counts,
   the full normalised work-item list, and the top three items needing
   attention.
4. `apps/dashboard-3ls/app/page.tsx` — adds an `AiProgrammingGovernedPathPanel`
   at the top of the Overview tab. The panel shows the overall governance
   status (PASS / WARN / BLOCK / UNKNOWN), Codex / Claude counts, AEX and
   PQX evidence counts, bypass-risk counts, and the top three items needing
   attention with their per-leg AEX / PQX / EVL observations and recommended
   next inputs.
5. Tests: a Python contract-preflight selection target under
   `tests/metrics/test_ai_programming_governed_path_dashboard.py`, a TypeScript
   helper test under `apps/dashboard-3ls/__tests__/lib/`, an API wiring test
   under `apps/dashboard-3ls/__tests__/api/`, and a panel rendering test under
   `apps/dashboard-3ls/__tests__/components/`.

## How the dashboard determines whether Codex passed through AEX/PQX

For each work item with `agent_type = codex`:

- The dashboard reads the `aex_admission_observation` and
  `pqx_execution_observation` values written by MET into the artifact.
- If `repo_mutating = true` and either observation is `missing`, the panel
  renders `BLOCK` for that item, and the overall panel status is forced to
  BLOCK.
- If either observation is `partial` or `unknown` (and neither is missing),
  the panel renders `WARN` for that item.
- Only when both observations are `present` and `bypass_risk = none` is a
  per-item `PASS` reported.

This matches the canonical loop `AEX → PQX → EVL → TPA → CDE → SEL` from
`docs/architecture/system_registry.md`. The dashboard never re-evaluates the
underlying evidence; it reads what AEX and PQX have published (or not) and
shows the gap.

## How the dashboard determines whether Claude passed through AEX/PQX

The same rules apply for `agent_type = claude`. The dashboard treats Codex
and Claude symmetrically: missing AEX or PQX evidence on a repo-mutating
Claude work item renders BLOCK, and partial / unknown evidence renders WARN.

## Unknown AI agents

When `agent_type = unknown_ai_agent` and `repo_mutating = true`:

- Missing AEX or PQX renders BLOCK, because unknown-agent repo mutation with
  no admission or execution evidence is itself a bypass-risk surface.
- Otherwise the item renders WARN; the unknown agent type alone is enough to
  prevent a per-item PASS.

## What is artifact-backed vs unknown

Artifact-backed in this revision:

- The presence of the AI programming governed-path artifact itself
  (artifact loader returns non-null).
- The Codex / Claude / unknown_ai_agent enumeration of work items, with the
  per-leg observations recorded by MET against the seeded source artifacts.
- The PQX preflight slice execution evidence
  (`artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`) and the
  RDX trace fixtures used as source signals for the seeded items.
- The `data_source = artifact_store` envelope and the
  `source_artifacts_used` aggregation on the API response.

Unknown by design (visible, not hidden):

- Per-item `pr_ref`, `branch_ref`, and `changed_files_count` for AI
  programming work items that have not yet been linked to a PR or commit.
- `bypass_risk` of the unknown_ai_agent work item, which is reported as
  `unknown` rather than fabricated.
- The presence/absence of an AEX admission record for legacy Codex work
  items that pre-date the AI programming governed path artifact.

The dashboard renders `UNKNOWN` (never green) when the artifact itself is
missing, and reports unknown counts (never 0) for Codex / Claude / governed /
bypass-risk / unknown-path counts.

## What failure is prevented

Without this panel, repo-mutating AI programming changes (Codex, Claude)
could enter `main` while AEX admission evidence or PQX execution evidence
was absent or partial, and an operator scanning the Overview tab would see
no fail-closed signal. The panel forces:

- Codex repo-mutating work without AEX or PQX evidence renders BLOCK.
- Claude repo-mutating work without AEX or PQX evidence renders BLOCK.
- Unknown AI agent repo-mutating work without AEX or PQX evidence renders
  BLOCK.
- Missing artifact renders UNKNOWN with unknown counts, never green.

## What signal improved

The Overview surface now answers the operational question
"Are Codex and Claude programming changes entering through AEX and executing
through PQX?" with artifact-backed evidence, per-agent counts, per-leg
AEX / PQX / EVL observations, and explicit bypass-risk counts. Top
recommended next inputs include:

- "Add AEX admission evidence for Codex work item X"
- "Add PQX execution evidence for Codex work item X"
- "Add AEX admission evidence for Claude work item X"
- "Add PQX execution evidence for Claude work item X"
- "Attach lineage evidence for AI programming work item X"
- "Add EVL check for AI programming work item X"

Each recommendation carries `failure_prevented`, `signal_improved`,
`source_artifacts_used`, and the agent_type when available, so a reader can
trace the request back to evidence and the canonical owner.

## Remaining gaps

- The seeded work items rely on existing PQX preflight and RDX trace
  evidence; live PR / branch metadata enrichment is not yet wired into the
  detection helper.
- `pqx_execution_observation = present` for the seeded Codex item is taken
  from the preflight slice record, which proves a slice ran but not that a
  particular Codex PR was bound to that slice. Future hardening should
  attach a per-PR PQX slice reference.
- Lineage observations are seeded as `partial` because the
  `dashboard_seed/lineage_record.json` is intentionally minimal. A REP/LIN
  hardening artifact would let MET upgrade lineage_observation to `present`
  for governed items.
- The unknown_ai_agent example currently surfaces no `bypass_risk` value
  because no admission/execution evidence has been recorded for it.

## Next recommended step

Wire AEX and PQX into emitting per-PR admission and execution references so
this artifact can be regenerated from canonical evidence rather than
seed/preflight records, and add the AI Programming Governed Path block to
the contract preflight selection target so future builds cannot regress its
shape.
