#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODE="${1:-manual}"

python3 "${REPO_ROOT}/scripts/generate_repo_dashboard_snapshot.py" --output "${REPO_ROOT}/artifacts/dashboard/repo_snapshot.json"
python3 "${REPO_ROOT}/scripts/dashboard_refresh_publish_loop.py" --mode "${MODE}"
python3 "${REPO_ROOT}/scripts/validate_dashboard_public_artifacts.py"

echo "dashboard refresh/publish complete (mode=${MODE})"
