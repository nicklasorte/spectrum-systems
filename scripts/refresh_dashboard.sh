#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

GENERATOR_SCRIPT="${REPO_ROOT}/scripts/generate_repo_dashboard_snapshot.py"
SNAPSHOT_ARTIFACT="${REPO_ROOT}/artifacts/dashboard/repo_snapshot.json"
DASHBOARD_DIR="${REPO_ROOT}/dashboard"
DASHBOARD_PUBLIC_DIR="${DASHBOARD_DIR}/public"
DASHBOARD_SNAPSHOT="${DASHBOARD_PUBLIC_DIR}/repo_snapshot.json"
DASHBOARD_META="${DASHBOARD_PUBLIC_DIR}/repo_snapshot_meta.json"

if [[ ! -f "${GENERATOR_SCRIPT}" ]]; then
  echo "ERROR: snapshot generator missing at ${GENERATOR_SCRIPT}" >&2
  exit 1
fi

if [[ ! -d "${DASHBOARD_DIR}" ]]; then
  echo "ERROR: dashboard directory missing at ${DASHBOARD_DIR}" >&2
  exit 1
fi

if [[ ! -d "${DASHBOARD_PUBLIC_DIR}" ]]; then
  echo "ERROR: dashboard public directory missing at ${DASHBOARD_PUBLIC_DIR}" >&2
  exit 1
fi

mkdir -p "$(dirname "${SNAPSHOT_ARTIFACT}")"

python3 "${GENERATOR_SCRIPT}" --output "${SNAPSHOT_ARTIFACT}"

if [[ ! -f "${SNAPSHOT_ARTIFACT}" ]]; then
  echo "ERROR: snapshot artifact missing after generation at ${SNAPSHOT_ARTIFACT}" >&2
  exit 1
fi

cp "${SNAPSHOT_ARTIFACT}" "${DASHBOARD_SNAPSHOT}"

SNAPSHOT_SIZE_BYTES="$(wc -c < "${SNAPSHOT_ARTIFACT}" | tr -d '[:space:]')"
REFRESHED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
SOURCE_PATH_REL="artifacts/dashboard/repo_snapshot.json"

python3 - <<'PY' "${DASHBOARD_META}" "${REFRESHED_AT}" "${SOURCE_PATH_REL}" "${SNAPSHOT_SIZE_BYTES}"
import json
import pathlib
import sys

meta_path = pathlib.Path(sys.argv[1])
meta = {
    "last_refreshed_time": sys.argv[2],
    "snapshot_size": f"{int(sys.argv[4])} bytes",
    "data_source_state": "live",
    "snapshot_source_path": sys.argv[3],
    "snapshot_size_bytes": int(sys.argv[4]),
}
meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
PY

echo "Refresh complete: ${DASHBOARD_SNAPSHOT}"
echo "Metadata written: ${DASHBOARD_META}"
