#!/usr/bin/env bash
# checkpoint-packager/run.sh
# Usage: ./run.sh <CHECKPOINT_ID>
# Example: ./run.sh checkpoint-P
set -euo pipefail

CHECKPOINT_ID="${1:-}"
if [ -z "$CHECKPOINT_ID" ]; then
  echo "[ERROR] Usage: $0 <CHECKPOINT_ID>" >&2
  echo "Valid IDs: checkpoint-L, checkpoint-P, checkpoint-QR, checkpoint-XZ, checkpoint-AB, checkpoint-AJ" >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
BUNDLE_DIR="$REPO_ROOT/artifacts/checkpoints/$CHECKPOINT_ID"
mkdir -p "$BUNDLE_DIR"

echo "[checkpoint-packager] Building bundle: $BUNDLE_DIR"

# 1. Run tests
echo "[1/6] Running tests..."
pytest --tb=short "$REPO_ROOT/tests/" > "$BUNDLE_DIR/test_results.txt" 2>&1 && \
  echo "[PASS] Tests passed." || \
  echo "[WARN] Some tests failed — see test_results.txt"

# 2. Contract audit
echo "[2/6] Running contract boundary audit..."
bash "$REPO_ROOT/.codex/skills/contract-boundary-audit/run.sh" > "$BUNDLE_DIR/contract_audit.txt" 2>&1 && \
  echo "[PASS] Contract audit passed." || \
  echo "[WARN] Contract audit issues found — see contract_audit.txt"

# 3. Changed files since last checkpoint tag (or recent commits as fallback)
echo "[3/6] Recording changed files..."
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || true)
if [ -n "$LAST_TAG" ]; then
  git diff --stat "$LAST_TAG" HEAD > "$BUNDLE_DIR/changed_files.txt" 2>/dev/null || true
  echo "# Diff from tag: $LAST_TAG" >> "$BUNDLE_DIR/changed_files.txt"
else
  # No tags found — use last 20 commits as a bounded fallback
  echo "# No checkpoint tag found. Showing last 20 commits of changes." > "$BUNDLE_DIR/changed_files.txt"
  git diff --stat HEAD~20 HEAD >> "$BUNDLE_DIR/changed_files.txt" 2>/dev/null || \
    echo "# (unable to compute diff — fewer than 20 commits exist)" >> "$BUNDLE_DIR/changed_files.txt"
fi

# 4. Open work items
echo "[4/6] Collecting open work items..."
grep -rn "TODO\|OPEN\|DEFERRED" "$REPO_ROOT/docs/review-actions/" > "$BUNDLE_DIR/open_work_items.md" 2>/dev/null || \
  echo "(no open work items found)" > "$BUNDLE_DIR/open_work_items.md"

# 5. Write manifest
echo "[5/6] Writing manifest..."
cat > "$BUNDLE_DIR/manifest.json" <<JSONEOF
{
  "checkpoint_id": "$CHECKPOINT_ID",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "repo": "spectrum-systems",
  "git_sha": "$(git rev-parse HEAD)",
  "bundle_path": "artifacts/checkpoints/$CHECKPOINT_ID"
}
JSONEOF

echo "[6/6] Checkpoint bundle complete: $BUNDLE_DIR"
echo ""
echo "Next step: run .codex/skills/claude-review-prep/run.sh $CHECKPOINT_ID"
