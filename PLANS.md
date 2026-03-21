# PLANS.md

## Purpose
Define when a written execution plan is required and provide the standard template.
Plans prevent scope creep, unintended side effects, and mixed-type prompts.

---

## When a plan is required

A written plan is required before any `BUILD` or `WIRE` prompt that meets **any** of the following criteria:

| Condition | Threshold |
| --- | --- |
| Multi-file change | More than 2 files changed |
| New module | Introducing any new module, package, or directory |
| New contract or schema | Adding or modifying a JSON Schema in `contracts/schemas/` |
| Contract version bump | Incrementing any version in `contracts/standards-manifest.json` |
| Roadmap milestone | Implementing any A, B, or C slice of the H–AJ roadmap |
| Shared truth layer | Touching lifecycle definitions, artifact envelope, or shared provenance |
| Checkpoint bundle | Preparing any major checkpoint (L, P, Q+R, X+Z, AB, AJ) |

If the change is a single-file documentation fix or a trivial test addition, a plan is not required.
When in doubt, write a plan.

---

## How to write a plan

1. Create a file named `PLAN-<ITEM>-<DATE>.md` in `docs/review-actions/`.
   Example: `docs/review-actions/PLAN-M-2026-03-18.md`

2. Fill in the plan template below.

3. Submit the plan as a `PLAN` prompt to Codex or Claude for review before proceeding to `BUILD` or `WIRE`.

4. Reference the plan file in every subsequent `BUILD`, `WIRE`, `VALIDATE`, and `REVIEW` prompt for this item.

---

## Plan template

```markdown
# Plan — <ROADMAP ITEM> — <DATE>

## Prompt type
PLAN

## Roadmap item
<Item label from docs/roadmaps/codex-prompt-roadmap.md, e.g., M-B>

## Objective
<One sentence: what will be true after this plan is executed>

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| path/to/file.py | CREATE | ... |
| path/to/other.md | MODIFY | ... |

## Contracts touched
List any contracts that will be created, modified, or version-bumped.
If none, write "None".

## Tests that must pass after execution
List the specific test commands to run to validate this plan.

1. `pytest tests/test_<foo>.py`
2. `.codex/skills/golden-path-check/run.sh <CONTRACT_NAME>`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.
This prevents accidental expansion.

- Do not modify X
- Do not refactor Y
- Do not touch Z

## Dependencies
List any prior roadmap items that must be complete before this plan can execute.

- <Item label> must be complete
```

---

## Active plans

| Plan file | Item | Status |
| --- | --- | --- |
| docs/review-actions/PLAN-BB-2026-03-19.md | Prompt BB — Failure-First Observability | Active |
| docs/review-actions/PLAN-BB-PLUS-1-2026-03-19.md | Prompt BB+1 — Failure Enforcement & Control Layer | Active |
| docs/review-actions/PLAN-BN.6-2026-03-20.md | BN.6 — Control Signal Consumption Layer | Active |
| docs/review-actions/PLAN-BPA-2026-03-20.md | Prompt BPA — Strategic Knowledge Layer Foundation | Active |
| docs/review-actions/PLAN-BPA-FIX-2026-03-20.md | Prompt BPA — CI/Registry/Contract Hardening Fixes | Active |
| docs/review-actions/PLAN-BPB-2026-03-21.md | Prompt BPB — Strategic Knowledge Validation Gate | Active |
| docs/review-actions/PLAN-BPB-BOUNDARY-FIX-2026-03-21.md | Prompt BPB — Boundary Compliance Fix | Active |
| docs/review-actions/PLAN-BAB-2026-03-21.md | Prompt BAB — Trace Context Injection | Active |
| docs/review-actions/PLAN-BAC-2026-03-21.md | Prompt BAC — Trace Span Emission and Event Flow | Active |

Update this table when plans are created or completed.

---

## Plan lifecycle

```
PLAN written → Codex/Claude review → BUILD/WIRE executes → VALIDATE passes → plan closed
```

A plan is **closed** when its VALIDATE slice passes and the result is committed.
Closed plans are not deleted — they remain as execution history.
