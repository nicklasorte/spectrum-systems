#!/usr/bin/env bash
# 3LS Authority Boundary Firewall — local preflight wrapper.
#
# Runs the structured authority preflight on the current branch and emits
# repair suggestions for any non-owner authority vocabulary leaks.
#
# This is local fast-feedback. It does NOT replace the CI authority leak guard
# at scripts/run_authority_leak_guard.py — that gate remains the binding check.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

BASE_REF="${BASE_REF:-origin/main}"
HEAD_REF="${HEAD_REF:-HEAD}"
PREFLIGHT_RESULT="outputs/3ls_authority_preflight/3ls_authority_preflight_result.json"

PREFLIGHT_RC=0
python scripts/run_3ls_authority_preflight.py \
    --base-ref "${BASE_REF}" \
    --head-ref "${HEAD_REF}" \
    --output "${PREFLIGHT_RESULT}" \
    || PREFLIGHT_RC=$?

# Always emit suggestions (even if preflight passed; it will simply be empty).
python scripts/suggest_3ls_authority_repairs.py \
    --input "${PREFLIGHT_RESULT}"

exit "${PREFLIGHT_RC}"
