#!/usr/bin/env bash
# Install git hooks for protected file checking
# Run once after cloning: bash scripts/install_hooks.sh

set -euo pipefail

HOOKS_DIR=".git/hooks"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/usr/bin/env bash
# Pre-push hook: check for protected file violations before pushing
set -euo pipefail

BASE_REF="origin/main"
HEAD_REF="HEAD"

echo "🔒 Protected file check (pre-push)..."

if ! python scripts/check_protected_files.py \
    --base-ref "$BASE_REF" \
    --head-ref "$HEAD_REF"; then
  echo ""
  echo "Push blocked. Fix violations before pushing."
  echo "To bypass (emergencies only): git push --no-verify"
  exit 1
fi

echo "✅ Protected file check passed — pushing."
EOF

chmod +x "$HOOKS_DIR/pre-push"
echo "✅ Pre-push hook installed at $HOOKS_DIR/pre-push"
echo "   Runs: python scripts/check_protected_files.py before every push"
