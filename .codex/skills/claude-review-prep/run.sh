#!/usr/bin/env bash
# claude-review-prep/run.sh
# Usage: ./run.sh <CHECKPOINT_ID>
set -euo pipefail

CHECKPOINT_ID="${1:-}"
if [ -z "$CHECKPOINT_ID" ]; then
  echo "[ERROR] Usage: $0 <CHECKPOINT_ID>" >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
BUNDLE_DIR="$REPO_ROOT/artifacts/checkpoints/$CHECKPOINT_ID"
MANIFEST="$BUNDLE_DIR/manifest.json"

if [ ! -f "$MANIFEST" ]; then
  echo "[ERROR] Checkpoint bundle not found: $BUNDLE_DIR"
  echo "Run .codex/skills/checkpoint-packager/run.sh $CHECKPOINT_ID first."
  exit 1
fi

DATE=$(date +%Y-%m-%d)
OUTPUT="$REPO_ROOT/docs/review-actions/${DATE}-${CHECKPOINT_ID}-review-prep.md"

TEST_RESULTS=$(cat "$BUNDLE_DIR/test_results.txt" 2>/dev/null || echo "(not available)")
CONTRACT_AUDIT=$(cat "$BUNDLE_DIR/contract_audit.txt" 2>/dev/null || echo "(not available)")
CHANGED_FILES=$(cat "$BUNDLE_DIR/changed_files.txt" 2>/dev/null || echo "(not available)")
OPEN_ITEMS=$(cat "$BUNDLE_DIR/open_work_items.md" 2>/dev/null || echo "(none)")
GIT_SHA=$(python3 -c "import json; d=json.load(open('$MANIFEST')); print(d.get('git_sha',''))" 2>/dev/null || true)
if [ -z "$GIT_SHA" ]; then
  echo "[WARN] Could not determine git SHA from checkpoint manifest. Using HEAD."
  GIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
fi

cat > "$OUTPUT" <<MDEOF
# Claude Review Prep — $CHECKPOINT_ID

**Date:** $DATE
**Checkpoint:** $CHECKPOINT_ID
**Git SHA:** $GIT_SHA
**Bundle:** artifacts/checkpoints/$CHECKPOINT_ID/

---

## Request

Please conduct a structured design review of this checkpoint using the format defined in
\`docs/design-review-standard.md\`. Produce findings and an action tracker stub using
\`docs/review-actions/action-tracker-template.md\`.

This checkpoint blocks advancement to the next roadmap stage until findings are addressed
or formally deferred with documented rationale.

---

## Summary of work completed in this stage

(Fill in: which roadmap items H–AJ were completed, what was built/wired/validated)

---

## Test results

\`\`\`
$TEST_RESULTS
\`\`\`

---

## Contract audit

\`\`\`
$CONTRACT_AUDIT
\`\`\`

---

## Changed files

\`\`\`
$CHANGED_FILES
\`\`\`

---

## Open work items

$OPEN_ITEMS

---

## Review questions

(Fill in stage-specific review questions from .codex/skills/claude-review-prep/SKILL.md)

---

## Required outputs from Claude

1. Structured findings (using \`docs/design-review-standard.md\` format)
2. Action tracker stub (using \`docs/review-actions/action-tracker-template.md\`)
3. Explicit advancement recommendation: ADVANCE / DEFER / BLOCK
MDEOF

echo "[claude-review-prep] Review prep written to: $OUTPUT"
echo "Submit this file to Claude for the structured review."
