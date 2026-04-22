#!/usr/bin/env bash
# scripts/srg_check.sh
# Local SRG validation — run this before pushing to catch ownership violations early.
#
# Usage:
#   ./scripts/srg_check.sh                  # check files changed vs origin/main
#   ./scripts/srg_check.sh --staged         # check only staged files
#   ./scripts/srg_check.sh --last-commit    # check files in the last commit only
#   SRG_BASE_REF=HEAD~3 ./scripts/srg_check.sh  # custom base ref

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_REF="${SRG_BASE_REF:-origin/main}"
OUTPUT="${REPO_ROOT}/outputs/system_registry_guard/local_check_result.json"

MODE="branch"
if [[ "${1:-}" == "--staged" ]]; then
  MODE="staged"
elif [[ "${1:-}" == "--last-commit" ]]; then
  MODE="last-commit"
fi

if [[ "$MODE" == "staged" ]]; then
  # Only check staged files
  STAGED_FILES=$(git -C "${REPO_ROOT}" diff --name-only --cached)
  if [[ -z "$STAGED_FILES" ]]; then
    echo "[SRG] No staged files to check." >&2
    exit 0
  fi
  echo "[SRG] Checking staged files…" >&2
  # shellcheck disable=SC2086
  python3 "${REPO_ROOT}/scripts/run_system_registry_guard.py" \
    --changed-files ${STAGED_FILES} \
    --output "${OUTPUT}"
elif [[ "$MODE" == "last-commit" ]]; then
  echo "[SRG] Checking files in last commit…" >&2
  python3 "${REPO_ROOT}/scripts/run_system_registry_guard.py" \
    --base-ref "HEAD~1" \
    --head-ref "HEAD" \
    --output "${OUTPUT}"
else
  echo "[SRG] Checking all files changed vs ${BASE_REF}…" >&2
  python3 "${REPO_ROOT}/scripts/run_system_registry_guard.py" \
    --base-ref "${BASE_REF}" \
    --head-ref "HEAD" \
    --output "${OUTPUT}"
fi

STATUS=$?
echo "[SRG] Full result: ${OUTPUT}" >&2
exit $STATUS
