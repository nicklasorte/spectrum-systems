#!/usr/bin/env bash
# verify-changed-scope/run.sh
# Usage: PLAN_FILES="file1 file2 ..." ./run.sh
set -euo pipefail

if [ -z "${PLAN_FILES:-}" ]; then
  echo "[ERROR] PLAN_FILES is not set. Set it to a space-separated list of expected changed files." >&2
  exit 1
fi

# Always-allowed paths: AGENTS.md files (any location), .codex/ changes

changed_files=$(git diff --name-only HEAD 2>/dev/null; git diff --name-only --cached 2>/dev/null)
changed_files=$(echo "$changed_files" | sort -u)

undeclared=()
while IFS= read -r file; do
  [ -z "$file" ] && continue
  declared=false
  for allowed in $PLAN_FILES; do
    if [ "$file" = "$allowed" ]; then
      declared=true
      break
    fi
  done
  if [ "$declared" = false ]; then
    # Always allow: files named exactly AGENTS.md (at any path depth), or under .codex/
    if [[ "$file" == "AGENTS.md" || "$file" == */AGENTS.md || "$file" == .codex/* ]]; then
      declared=true
    fi
  fi
  if [ "$declared" = false ]; then
    undeclared+=("$file")
  fi
done <<< "$changed_files"

if [ ${#undeclared[@]} -gt 0 ]; then
  echo "[SCOPE VIOLATION] The following files were changed but not declared in the plan:"
  for f in "${undeclared[@]}"; do
    echo "  [UNDECLARED] $f"
  done
  echo ""
  echo "Update your plan to include these files, or revert the undeclared changes."
  exit 1
fi

echo "[OK] All changed files are within declared scope."
