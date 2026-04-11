#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DASHBOARD_DIR="${REPO_ROOT}/dashboard"
REFRESH_SCRIPT="${SCRIPT_DIR}/refresh_dashboard.sh"

if [[ ! -x "${REFRESH_SCRIPT}" ]]; then
  echo "ERROR: refresh script missing or not executable at ${REFRESH_SCRIPT}" >&2
  exit 1
fi

if [[ ! -d "${DASHBOARD_DIR}" ]]; then
  echo "ERROR: dashboard directory missing at ${DASHBOARD_DIR}" >&2
  exit 1
fi

"${REFRESH_SCRIPT}"

if [[ -f "${DASHBOARD_DIR}/package-lock.json" ]]; then
  (cd "${DASHBOARD_DIR}" && npm ci)
elif [[ -f "${DASHBOARD_DIR}/package.json" ]]; then
  (cd "${DASHBOARD_DIR}" && npm install)
else
  echo "ERROR: dashboard package manifest missing at ${DASHBOARD_DIR}/package.json" >&2
  exit 1
fi

(cd "${DASHBOARD_DIR}" && npm run dev)
