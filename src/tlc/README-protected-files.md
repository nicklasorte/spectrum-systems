# Protected File Registry (TLC)

The TLC system maintains a registry of files that cannot be modified via feature PRs.

## Why

The system registry guard enforces SHADOW_OWNERSHIP_OVERLAP to prevent feature PRs from silently modifying files that define system authority, agent behavior, and governance rules.

## Protected Files

| File | Reason | Change Requires |
|------|--------|-----------------|
| CLAUDE.md | Agent authority document | governance_pr |
| AGENTS.md | Agent standards document | governance_pr |
| scripts/run_system_registry_guard.py | Registry guard enforcement | governance_pr |
| contracts/schemas/ | Core artifact schemas | governance_pr |
| .github/workflows/ | CI/CD pipelines | governance_pr |

## How to Change a Protected File

1. Open a **dedicated governance PR** (not a feature PR)
2. PR title must start with `[GOVERNANCE]`
3. PR must include justification for the change
4. Requires explicit review from system authority owner
5. Cannot be auto-merged

## How to Catch This Early (Pre-Commit)

```bash
python scripts/check_protected_files.py --base-ref main --head-ref HEAD
```

This runs automatically via the pre-commit hook and GitHub Actions workflow.

## How to Add a Protected File

1. Add to `PROTECTED_FILES` in `src/tlc/protected-file-registry.ts`
2. Add to `PROTECTED_FILES` in `scripts/check_protected_files.py`
3. Open governance PR to add the new entry

## How It Works

```
Developer makes changes
        ↓
Pre-commit hook runs check_protected_files.py
        ↓ (catches early)
GitHub Actions protected-file-check.yml
        ↓ (catches in CI)
System registry guard
        ↓ (final authority)
PR merges or fails
```

Each layer provides earlier, more specific feedback than the registry guard's opaque `SHADOW_OWNERSHIP_OVERLAP` error.
