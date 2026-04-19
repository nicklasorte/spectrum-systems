# Protected File Registry (TLC)

Source of truth for which files require a **dedicated governance PR** to modify.

## Protected Files

| File / Path | Reason | Change Requires |
|-------------|--------|-----------------|
| `CLAUDE.md` | Agent authority document | governance_pr |
| `AGENTS.md` | Agent standards document | governance_pr |
| `scripts/run_system_registry_guard.py` | Registry guard enforcement | governance_pr |
| `.github/workflows/` | CI/CD pipelines | governance_pr |
| `contracts/schemas/` | Core artifact schemas | governance_pr |

## What Is NOT Protected

- `scripts/check_protected_files.py` — safe to ship in feature PRs
- `src/tlc/` — TLC source files are safe in feature PRs
- `docs/`, `tests/`, `src/` (non-schema) — all safe in feature PRs

## Bootstrap Rule

The protected file check **script** ships in feature PRs.
The **CI workflow** that wires it into GitHub Actions ships in a governance PR.
This prevents the script from blocking its own introduction.

## Detection Layers (Earliest to Latest)

```
1. pre-push hook (local)     → catches before network call
2. CI protected-file-check   → catches in GitHub Actions (governance PR ships this)
3. System registry guard     → final authority, always runs
```

## To Install the Pre-Push Hook

```bash
bash scripts/install_hooks.sh
```

This installs `.git/hooks/pre-push` which runs `check_protected_files.py` before every push.

## To Modify a Protected File

1. Open a PR titled `[GOVERNANCE] <description>`
2. Include justification for the change
3. Requires review from system-authority owner
4. Cannot be auto-merged

## To Add a New Protected File

Update both:

- `src/tlc/protected-file-registry.ts` (TypeScript, used by hooks)
- `scripts/check_protected_files.py` (Python, used by CI and hooks)

Open a governance PR to add the new entry.

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
