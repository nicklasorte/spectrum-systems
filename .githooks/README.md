# Git Hooks

## Install

Run once per clone to enable local SRG pre-push validation:

```bash
git config core.hooksPath .githooks
```

## Hooks

### pre-push

Runs `scripts/run_system_registry_guard.py` against all files changed relative
to `origin/main` before a push completes. Any `SHADOW_OWNERSHIP_OVERLAP` or
other SRG violation blocks the push and prints actionable diagnostics inline.

**To skip** (requires documented justification in the PR):
```bash
SKIP_SRG=1 git push
```

## Local validation without hooks

```bash
./scripts/srg_check.sh               # all files changed vs origin/main
./scripts/srg_check.sh --staged      # staged files only
./scripts/srg_check.sh --last-commit # files in last commit only
```

Or run the SRG directly in pytest (fastest feedback loop):

```bash
python3 -m pytest tests/test_srg_phase2_ownership.py -v
```
