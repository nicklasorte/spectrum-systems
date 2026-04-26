#!/usr/bin/env bash
# TLS-GUARD-01 — TLS / dashboard priority local preflight wrapper.
#
# Runs the exact authority checks needed for TLS dependency-priority and
# dashboard changes before pushing. This is local fast-feedback. It does
# NOT replace the CI authority leak guard at scripts/run_authority_leak_guard.py
# — that gate remains the binding check.
#
# Pipeline (fail-closed):
#   1. python scripts/build_tls_dependency_priority.py \
#        --candidates H01,RFX,HOP,MET,METS \
#        --fail-if-missing
#   2. python scripts/run_authority_shape_preflight.py --suggest-only
#   3. python scripts/run_authority_leak_guard.py
#   4. pytest tests/tls_dependency_graph
#
# Configure base/head refs via environment:
#   BASE_REF (default: main)
#   HEAD_REF (default: HEAD)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

BASE_REF="${BASE_REF:-main}"
HEAD_REF="${HEAD_REF:-HEAD}"
CANDIDATES="${CANDIDATES:-H01,RFX,HOP,MET,METS}"

SHAPE_RESULT="outputs/authority_shape_preflight/authority_shape_preflight_result.json"
LEAK_RESULT="outputs/authority_leak_guard/authority_leak_guard_result.json"

mkdir -p "$(dirname "${SHAPE_RESULT}")" \
         "$(dirname "${LEAK_RESULT}")"

PRIORITY_RC=0
SHAPE_RC=0
LEAK_RC=0
PYTEST_RC=0

echo "[tls-preflight] TLS-STACK build_tls_dependency_priority (candidates=${CANDIDATES})"
python scripts/build_tls_dependency_priority.py \
    --candidates "${CANDIDATES}" \
    --fail-if-missing \
    || PRIORITY_RC=$?

echo "[tls-preflight] AGS-001 authority-shape preflight (suggest-only)"
python scripts/run_authority_shape_preflight.py \
    --base-ref "${BASE_REF}" \
    --head-ref "${HEAD_REF}" \
    --suggest-only \
    --output "${SHAPE_RESULT}" \
    || SHAPE_RC=$?

echo "[tls-preflight] authority-leak guard"
python scripts/run_authority_leak_guard.py \
    --base-ref "${BASE_REF}" \
    --head-ref "${HEAD_REF}" \
    --output "${LEAK_RESULT}" \
    || LEAK_RC=$?

echo "[tls-preflight] pytest tests/tls_dependency_graph"
python -m pytest tests/tls_dependency_graph \
    || PYTEST_RC=$?

echo "[tls-preflight] results:"
echo "  build_tls_dependency_priority: rc=${PRIORITY_RC}"
echo "  authority_shape_preflight:     rc=${SHAPE_RC}    ${SHAPE_RESULT}"
echo "  authority_leak_guard:          rc=${LEAK_RC}    ${LEAK_RESULT}"
echo "  pytest tls_dependency_graph:   rc=${PYTEST_RC}"

# If dashboard files changed, surface the dashboard-3ls test reminder.
DASHBOARD_CHANGED="$(git diff --name-only "${BASE_REF}" "${HEAD_REF}" -- \
    'apps/dashboard-3ls/' \
    'apps/dashboard/' \
    'spectrum_systems/dashboard/' \
    'components/dashboard/' \
    'src/dashboard/' \
    'app/dashboard/' \
    'app/dashboard-3ls/' \
    2>/dev/null || true)"
if [ -n "${DASHBOARD_CHANGED}" ]; then
    echo "[tls-preflight] dashboard files changed:"
    echo "${DASHBOARD_CHANGED}" | sed 's/^/  /'
    echo "Run dashboard-3ls tests before pushing."
fi

# Surface the worst non-zero return code so wrapping CI can fail-close.
WORST_RC=$(( PRIORITY_RC > SHAPE_RC ? PRIORITY_RC : SHAPE_RC ))
WORST_RC=$(( WORST_RC > LEAK_RC ? WORST_RC : LEAK_RC ))
WORST_RC=$(( WORST_RC > PYTEST_RC ? WORST_RC : PYTEST_RC ))
exit "${WORST_RC}"
