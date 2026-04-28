#!/usr/bin/env bash
# Install git hooks for protected file checking and the generated-artifact
# merge driver.
# Run once after cloning: bash scripts/install_hooks.sh

set -euo pipefail

HOOKS_DIR=".git/hooks"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Register the `generated-artifact` merge driver referenced by .gitattributes.
# `true` resolves the merge by keeping the current branch's content for
# run-specific generated outputs whose timestamps and trace IDs diverge across
# branches. The matching CI guard (scripts/run_generated_artifact_git_guard.py)
# still enforces that the artifacts are regenerated before merge.
git config merge.generated-artifact.name "Run-specific generated artifact (no hand-merge; regenerate via script)"
git config merge.generated-artifact.driver "true"
echo "Registered git merge driver: generated-artifact (keep ours; regenerate after merge)"

cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/usr/bin/env bash
# Pre-push hook: check for protected file violations and generated-artifact
# hand-merge violations before pushing.
set -euo pipefail

BASE_REF="origin/main"
HEAD_REF="HEAD"

echo "Protected file check (pre-push)..."

if ! python scripts/check_protected_files.py \
    --base-ref "$BASE_REF" \
    --head-ref "$HEAD_REF"; then
  echo ""
  echo "Push blocked. Fix violations before pushing."
  echo "To bypass (emergencies only): git push --no-verify"
  exit 1
fi

echo "Generated-artifact git guard (pre-push)..."

if ! python scripts/run_generated_artifact_git_guard.py \
    --base-ref "$BASE_REF" \
    --head-ref "$HEAD_REF"; then
  echo ""
  echo "Push blocked: generated run-specific artifacts cannot be hand-merged."
  echo "Regenerate via the script declared in config/generated_artifact_policy.json,"
  echo "or add a regeneration_exceptions entry with justification."
  exit 1
fi

echo "All pre-push checks passed."
EOF

chmod +x "$HOOKS_DIR/pre-push"
echo "Pre-push hook installed at $HOOKS_DIR/pre-push"
echo "   Runs: check_protected_files.py + run_generated_artifact_git_guard.py before every push"
