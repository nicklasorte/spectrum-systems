#!/usr/bin/env bash
# HOP local preflight wrapper.
#
# Runs the three guards required to ship a HOP change against the current
# branch and writes machine-readable results under outputs/.
#
# This is local fast-feedback. It does NOT replace the CI gates; the
# binding gate remains scripts/run_authority_leak_guard.py in CI.
#
# Configure base/head refs via environment:
#   BASE_REF (default: origin/main)
#   HEAD_REF (default: HEAD)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

BASE_REF="${BASE_REF:-origin/main}"
HEAD_REF="${HEAD_REF:-HEAD}"

SHAPE_RESULT="outputs/authority_shape_preflight/authority_shape_preflight_result.json"
REGISTRY_RESULT="outputs/system_registry_guard/system_registry_guard_result.json"
LEAK_RESULT="outputs/authority_leak_guard/authority_leak_guard_result.json"

mkdir -p "$(dirname "${SHAPE_RESULT}")" \
         "$(dirname "${REGISTRY_RESULT}")" \
         "$(dirname "${LEAK_RESULT}")"

SHAPE_RC=0
REGISTRY_RC=0
LEAK_RC=0

echo "[hop-preflight] AGS-001 authority-shape preflight (suggest-only)"
python scripts/run_authority_shape_preflight.py \
    --base-ref "${BASE_REF}" \
    --head-ref "${HEAD_REF}" \
    --suggest-only \
    --output "${SHAPE_RESULT}" \
    || SHAPE_RC=$?

echo "[hop-preflight] system-registry owner-claim guard"
python scripts/run_system_registry_guard.py \
    --base-ref "${BASE_REF}" \
    --head-ref "${HEAD_REF}" \
    --output "${REGISTRY_RESULT}" \
    || REGISTRY_RC=$?

echo "[hop-preflight] authority-leak guard"
python scripts/run_authority_leak_guard.py \
    --base-ref "${BASE_REF}" \
    --head-ref "${HEAD_REF}" \
    --output "${LEAK_RESULT}" \
    || LEAK_RC=$?

echo "[hop-preflight] results:"
echo "  authority_shape_preflight: rc=${SHAPE_RC}    ${SHAPE_RESULT}"
echo "  system_registry_guard:     rc=${REGISTRY_RC} ${REGISTRY_RESULT}"
echo "  authority_leak_guard:      rc=${LEAK_RC}    ${LEAK_RESULT}"

# Surface the worst non-zero return code so wrapping CI can fail-close.
WORST_RC=$(( SHAPE_RC > REGISTRY_RC ? SHAPE_RC : REGISTRY_RC ))
WORST_RC=$(( WORST_RC > LEAK_RC ? WORST_RC : LEAK_RC ))
exit "${WORST_RC}"
