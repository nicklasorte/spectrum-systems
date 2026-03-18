# SKILL.md — verify-changed-scope

## Metadata
- **Skill ID**: verify-changed-scope
- **Type**: VALIDATE
- **Trigger**: After every BUILD or WIRE prompt, before commit
- **Output**: Console diff summary + pass/fail exit code

## Purpose
Confirm that only the files declared in the current plan were changed.
Catches unintended side effects, accidental refactors, and scope creep before they are committed.

## Inputs
- `PLAN_FILES` — space-separated list of file paths declared in the plan (passed as env var or argument)
- Git working tree (unstaged + staged changes)

## Workflow

1. Collect all changed files in the working tree:
   ```
   git diff --name-only HEAD
   git diff --name-only --cached
   ```

2. Compare the changed file list against `PLAN_FILES`.

3. Identify any file that is changed but not declared in the plan.

4. If undeclared changes exist:
   - Print each undeclared file with a `[UNDECLARED]` prefix.
   - Exit non-zero (exit code 1).

5. If all changed files are declared:
   - Print `[OK] All changed files are within declared scope.`
   - Exit zero.

## Usage
```bash
PLAN_FILES="contracts/schemas/foo.schema.json spectrum_systems/modules/foo.py tests/test_foo.py" \
  .codex/skills/verify-changed-scope/run.sh
```

## Notes
- If a change outside declared scope is genuinely required, update the plan first, then re-run.
- AGENTS.md files and `.codex/` changes are always considered in-scope.
- Generated files (e.g., `docs/governance-reports/`) may be excluded from scope checks with `--ignore-generated`.
