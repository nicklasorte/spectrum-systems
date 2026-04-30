#!/usr/bin/env bash
# check_main_drift.sh — stop hook: warn when the feature branch has fallen behind origin/main.
#
# Runs silently when up-to-date. Prints a structured warning (JSON) when main
# has advanced so that Claude Code surfaces it before the session ends.
# Never modifies files — diagnosis only.

set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$REPO_ROOT"

# Only meaningful on a feature branch.
BRANCH="$(git branch --show-current 2>/dev/null || true)"
[[ -z "$BRANCH" || "$BRANCH" == "main" || "$BRANCH" == "master" ]] && exit 0

# Fetch quietly; if network unavailable skip silently.
git fetch origin main --quiet 2>/dev/null || exit 0

BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
[[ "$BEHIND" -eq 0 ]] && exit 0

# Count how many of those commits touched known generated/conflict-prone files.
CONFLICT_PRONE_PATHS=(
    "artifacts/tls/"
    "artifacts/system_dependency_priority_report.json"
    "governance/reports/ecosystem-health.json"
    "governance/reports/ecosystem-architecture-graph.json"
    "docs/governance-reports/"
    "docs/architecture/system_registry.md"
    "contracts/governance/authority_shape_vocabulary.json"
    "contracts/governance/authority_registry.json"
    "contracts/standards-manifest.json"
)

CHANGED_GOVERNED=""
for path in "${CONFLICT_PRONE_PATHS[@]}"; do
    if git diff --name-only HEAD..origin/main -- "$path" 2>/dev/null | grep -q .; then
        CHANGED_GOVERNED="$CHANGED_GOVERNED $path"
    fi
done

NEW_SCHEMAS=$(git diff --name-only HEAD..origin/main -- "docs/architecture/system_registry.md" 2>/dev/null | wc -l || echo 0)
NEW_ARTIFACTS=$(git diff --name-only HEAD..origin/main -- "contracts/schemas/" 2>/dev/null | wc -l || echo 0)

cat <<EOF
[check_main_drift] WARNING: branch '$BRANCH' is $BEHIND commit(s) behind origin/main.
[check_main_drift] Conflict-prone paths changed on main:$(echo "$CHANGED_GOVERNED" | tr ' ' '\n' | grep -v '^$' | sed 's/^/  /')
[check_main_drift] To auto-resolve: bash scripts/sync_from_main.sh
[check_main_drift] To preview conflicts: bash scripts/sync_from_main.sh --dry-run
EOF

# Exit 0 — this is advisory only; do not block the stop hook.
exit 0
