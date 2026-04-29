#!/usr/bin/env bash
# sync_from_main.sh — merge origin/main and auto-resolve known generated-file conflicts.
#
# Generated files always conflict when main advances because multiple branches
# regenerate them independently. The correct resolution is always:
#   1. Accept main's version (--theirs)
#   2. Re-run the generators so the file incorporates both branches' inputs
#
# Usage:
#   bash scripts/sync_from_main.sh           # merge origin/main, resolve, regenerate
#   bash scripts/sync_from_main.sh --dry-run  # show what would conflict, no changes
#
# Exit codes:
#   0 — clean (no conflicts, or all conflicts auto-resolved and merge committed)
#   1 — unresolvable conflicts remain after auto-resolution (human review needed)
#   2 — usage/environment error

set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

DRY_RUN=0
for arg in "$@"; do [[ "$arg" == "--dry-run" ]] && DRY_RUN=1; done

# ── Known generated file patterns (accept main's version, then regenerate) ────
GENERATED_GLOBS=(
    "artifacts/tls/*.json"
    "artifacts/system_dependency_priority_report.json"
    "governance/reports/ecosystem-health.json"
    "governance/reports/ecosystem-architecture-graph.json"
    "governance/reports/contract-dependency-graph.json"
    "docs/governance-reports/ecosystem-dashboard.md"
    "docs/governance-reports/ecosystem-health-report.md"
    "docs/governance-reports/contract-compliance-report.md"
)

# ── Generators (run in order after conflict resolution) ───────────────────────
run_generators() {
    echo "[sync] Regenerating derived artifacts..."
    python3 scripts/build_tls_dependency_priority.py \
        --out artifacts/tls --top-level-out artifacts --candidates "" \
        > /dev/null
    python3 scripts/generate_ecosystem_health_report.py > /dev/null
    echo "[sync] Regeneration complete."
}

# ── Fetch ─────────────────────────────────────────────────────────────────────
echo "[sync] Fetching origin/main..."
git fetch origin main --quiet

# ── Check what would conflict ─────────────────────────────────────────────────
WOULD_CONFLICT=$(git merge-tree "$(git merge-base HEAD origin/main)" HEAD origin/main 2>/dev/null \
    | grep -E "^<<<<<<|changed in both" | wc -l || true)

if [[ "$DRY_RUN" == "1" ]]; then
    echo "[sync] DRY RUN — checking conflict surface..."
    MERGE_BASE=$(git merge-base HEAD origin/main)
    git diff --name-only "$MERGE_BASE"...origin/main | while read -r f; do
        git diff --name-only "$MERGE_BASE"...HEAD | grep -q "^${f}$" && echo "  CONFLICT: $f" || true
    done
    echo "[sync] (no changes made)"
    exit 0
fi

# ── Already up to date? ───────────────────────────────────────────────────────
if git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then
    echo "[sync] Already up to date with origin/main."
    run_generators
    git add artifacts/tls/ artifacts/system_dependency_priority_report.json \
        governance/reports/ecosystem-health.json \
        governance/reports/ecosystem-architecture-graph.json \
        governance/reports/contract-dependency-graph.json \
        docs/governance-reports/ 2>/dev/null || true
    if ! git diff --cached --quiet; then
        git commit -m "chore: refresh generated artifacts

https://claude.ai/code/session_01KW1i35DgAru1uunUu6e6SZ"
    fi
    exit 0
fi

# ── Merge ─────────────────────────────────────────────────────────────────────
echo "[sync] Merging origin/main..."
git merge origin/main --no-edit --no-commit 2>&1 || true

# ── Collect conflicting files ─────────────────────────────────────────────────
mapfile -t CONFLICTS < <(git diff --name-only --diff-filter=U 2>/dev/null || true)
if [[ "${#CONFLICTS[@]}" -eq 0 ]]; then
    echo "[sync] Merge completed with no conflicts."
    run_generators
    git add artifacts/ docs/governance-reports/ governance/reports/ 2>/dev/null || true
    git commit --no-edit -m "merge: sync with origin/main and refresh generated artifacts

https://claude.ai/code/session_01KW1i35DgAru1uunUu6e6SZ" 2>/dev/null || \
    git commit -m "merge: sync with origin/main and refresh generated artifacts

https://claude.ai/code/session_01KW1i35DgAru1uunUu6e6SZ"
    exit 0
fi

echo "[sync] Conflicts detected: ${#CONFLICTS[@]} file(s)"

# ── Classify conflicts ────────────────────────────────────────────────────────
UNRESOLVABLE=()
for f in "${CONFLICTS[@]}"; do
    MATCHED=0
    for glob in "${GENERATED_GLOBS[@]}"; do
        # shellcheck disable=SC2053
        if [[ "$f" == $glob ]]; then
            MATCHED=1
            break
        fi
    done
    if [[ "$MATCHED" -eq 1 ]]; then
        echo "[sync]   auto-resolving (generated): $f"
        git checkout --theirs "$f"
        git add "$f"
    else
        echo "[sync]   UNRESOLVABLE (not generated): $f"
        UNRESOLVABLE+=("$f")
    fi
done

if [[ "${#UNRESOLVABLE[@]}" -gt 0 ]]; then
    echo "[sync] ERROR: ${#UNRESOLVABLE[@]} conflict(s) require manual resolution:"
    for f in "${UNRESOLVABLE[@]}"; do echo "  $f"; done
    echo "[sync] Resolve these manually, then run: git add <files> && git merge --continue"
    exit 1
fi

# ── Regenerate ────────────────────────────────────────────────────────────────
run_generators
git add artifacts/tls/ artifacts/system_dependency_priority_report.json \
    governance/reports/ docs/governance-reports/ 2>/dev/null || true

# ── Commit the merge ──────────────────────────────────────────────────────────
git commit -m "merge: resolve conflicts with origin/main — regenerate derived artifacts

All conflicts were in generated files. Accepted main's version then
regenerated fresh to incorporate both branches' system registry changes.

https://claude.ai/code/session_01KW1i35DgAru1uunUu6e6SZ"
echo "[sync] Done. Branch is now up to date with origin/main."
