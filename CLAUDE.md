# CLAUDE.md

## System Identity

Spectrum Systems is a governed execution runtime for artifact-first, policy-controlled AI work.

It is not a chat system, agent framework, or prompt wrapper. Every input, decision, execution
step, and output is a versioned, schema-bound artifact. There are no shadow paths.

## Operational Loop

```
input → RIL (structure) → CDE (decide) → TLC (orchestrate)
     → PQX (execute) → eval gates → control decision
     → SEL (enforce) → certification → promotion
```

Non-determinism is logged. Promotion only follows a `control_decision` with `action = allow`.
Subsystem ownership is canonical in `docs/architecture/system_registry.md`.

## Module Boundaries

Modules are hard-separated. No module may cross-write another module’s artifact types.

|Module         |Authority                                    |
|---------------|---------------------------------------------|
|`agent/*`      |Produces output artifacts                    |
|`judgment/*`   |Interprets evidence, writes `judgment_record`|
|`evals/*`      |Assesses artifacts, writes eval artifacts    |
|`control/*`    |Emits `allow / warn / freeze / block`        |
|`enforcement/*`|Executes enforcement actions                 |

- CDE is the sole decision authority.
- TLC is the sole orchestration authority.
- PQX is the sole execution authority.
- SEL is the sole enforcement authority.

## Hard Rules

- All work runs through the governed runtime. No exceptions.
- No repo mutation outside PQX-equivalent execution.
- No decision logic outside CDE.
- No orchestration outside TLC.
- No promotion without a passing `done_certification_record`.
- Fail-closed always. Missing artifact = halt. Missing eval gate = block.
- `branch_update_allowed = (terminal_state == "ready_for_merge")`. No exceptions.

## Promotion Rule

`branch_update_allowed = (terminal_state == "ready_for_merge")`

No exceptions. All changes ship via Pull Request. PRs are the promotion mechanism.

## Failure Handling

```
failure → evidence artifact → FRE diagnosis → CDE decision
       → bounded repair (TLC) → retest → eval gate
```

Every failure produces a `failure_classification` artifact. Silent failures are prohibited.

## Learning Loop

```
failure → classified → eval candidate → governed adoption → roadmap signal
```

Failures feed the versioned eval dataset. Policy and prompt template updates require governed
adoption — no ad hoc fixes.

## Execution Permissions

Claude operates in autonomous execution mode within this repo. The governance boundary is the
PR gate, not the interactive prompt.

**Pre-authorized actions — no confirmation needed:**

- Read any file in the repo
- Write files to a feature branch
- Run tests, linters, and build commands (`python -m pytest -q`, `npm test`, `npm run lint`)
- Commit and push to feature branches
- Open PRs with descriptions referencing the governed artifact or work item

**Not permitted — halt and emit a finding instead of asking:**

- Direct writes to `main`
- Any action outside this surface

If an action falls outside the pre-authorized surface, halt and emit a finding artifact.
Do not ask interactively. Do not proceed on ambiguous scope.

## Claude’s Role

Claude performs reasoning, review, and implementation tasks within the governed runtime.

**Claude is permitted to:**

- Produce explicit findings, risk calls, and boundary checks as artifacts.
- Recommend remediation paths with evidence.
- Execute bounded, deterministic implementation changes via PR (PQX-equivalent).
- Interpret governed artifacts and declared ownership.
- Escalate contradictions to canonical references.

**Claude is forbidden to:**

- Bypass CDE, TLC, PQX, or SEL.
- Make implicit decisions or infer missing approval signals.
- Execute direct repo mutations outside the PR flow.
- Redefine ownership or extend scope beyond the requested artifact.
- Reproduce decision logic, orchestration, or enforcement inline.

## Implementation Discipline

- All changes ship via Pull Request. No direct file edits to `main`.
- Scope is bounded to the requested artifact. Do not expand.
- Contradictions escalate — they are not resolved by inference.
- Rules are explicit. Descriptive drift is a defect.
- Every PR must be traceable to a governed artifact or declared work item.
- Keep scope bounded; remove contradictions and duplicate instruction surfaces.

## Review Behavior

State evidence, decision boundary, and blocking condition explicitly.

Do not interpret silence as approval. Do not proceed when required artifacts are missing.
Do not infer schema alignment — validate it.

## Interpretation Boundaries

- Interpret artifacts; do not redefine ownership.
- Recommend remediation; do not execute remediation outside the governed flow.
- Escalate contradictions to canonical references.

## Prohibited Behavior

- No direct file edits outside governed flow.
- No implicit decisions.
- No hidden execution paths.
- No bypass of SEL / CDE / TLC.
- No interactive permission prompts — halt and emit a finding instead.

## References

- `README.md`
- `docs/architecture/system_registry.md`
