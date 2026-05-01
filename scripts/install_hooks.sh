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

# APR-01 agent PR precheck (opt-out via APR_SKIP_PRECHECK=1).
# Composes the same gate sequence CI's governed-contract-preflight runs
# (authority-shape, authority-leak, system-registry, contract-compliance,
#  build_preflight_pqx_wrapper, run_contract_preflight, generated-artifact
#  freshness, selected tests, CLP-01, CLP-02, APU) and emits
# outputs/agent_pr_precheck/agent_pr_precheck_result.json. AEX phase runs
# first to fail fast on missing required-surface mappings.
if [[ "${APR_SKIP_PRECHECK:-}" != "1" ]]; then
  echo "APR-01 agent PR precheck (pre-push)..."
  if ! python scripts/run_agent_pr_precheck.py \
      --base-ref "$BASE_REF" \
      --head-ref "$HEAD_REF" \
      --work-item-id "${APR_WORK_ITEM_ID:-pre-push}" \
      --agent-type "${APR_AGENT_TYPE:-unknown_ai_agent}" \
      --repo-mutating "${APR_REPO_MUTATING:-auto}"; then
    echo ""
    echo "Push blocked: APR-01 agent PR precheck reported readiness issues."
    echo "Inspect outputs/agent_pr_precheck/agent_pr_precheck_result.json"
    echo "and the per-phase artifacts under outputs/agent_pr_precheck/."
    echo "To bypass for an emergency: APR_SKIP_PRECHECK=1 git push"
    exit 1
  fi
fi

echo "All pre-push checks passed."
EOF

chmod +x "$HOOKS_DIR/pre-push"
echo "Pre-push hook installed at $HOOKS_DIR/pre-push"
echo "   Runs: check_protected_files.py + run_generated_artifact_git_guard.py + run_agent_pr_precheck.py before every push"
echo "   APR-01 precheck can be skipped per-push with APR_SKIP_PRECHECK=1 git push"
