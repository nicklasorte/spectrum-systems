#!/usr/bin/env bash
# contract-boundary-audit/run.sh
# Usage: ./run.sh [CONTRACT_NAME] [--strict]
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
CONTRACT_NAME=""
STRICT_MODE=0
for arg in "$@"; do
  if [ "$arg" = "--strict" ]; then
    STRICT_MODE=1
  elif [ -z "$CONTRACT_NAME" ]; then
    CONTRACT_NAME="$arg"
  else
    echo "[ERROR] unexpected argument: $arg" >&2
    exit 2
  fi
done
SCHEMAS_DIR="$REPO_ROOT/contracts/schemas"
MANIFEST="$REPO_ROOT/contracts/standards-manifest.json"
ERRORS=0
WARNINGS=0

if [ ! -f "$MANIFEST" ]; then
  echo "[ERROR] standards-manifest.json not found at $MANIFEST" >&2
  exit 1
fi

echo "[contract-boundary-audit] Starting audit..."
echo "  Schemas dir : $SCHEMAS_DIR"
echo "  Manifest    : $MANIFEST"
echo "  Strict mode : $STRICT_MODE"
echo ""

# Collect schema files to audit
if [ -n "$CONTRACT_NAME" ]; then
  SCHEMA_FILES=("$SCHEMAS_DIR/${CONTRACT_NAME}.schema.json")
else
  SCHEMA_FILES=("$SCHEMAS_DIR"/*.schema.json)
fi

# Precompute manifest artifact types once.
MANIFEST_ARTIFACT_TYPES=$(python3 - <<PY
import json
from pathlib import Path
manifest = json.loads(Path("$MANIFEST").read_text(encoding="utf-8"))
types = set()
for row in manifest.get("contracts", []):
    if isinstance(row, dict) and isinstance(row.get("artifact_type"), str):
        types.add(row["artifact_type"])
for t in sorted(types):
    print(t)
PY
)

for schema_file in "${SCHEMA_FILES[@]}"; do
  [ -f "$schema_file" ] || { echo "[SKIP] $schema_file not found"; continue; }
  contract=$(basename "$schema_file" .schema.json)

  # Check manifest has this contract (proper JSON key lookup)
  if ! printf '%s\n' "$MANIFEST_ARTIFACT_TYPES" | grep -qx "$contract"; then
    echo "[WARN] $contract — not referenced in standards-manifest.json (may be unpublished)"
    WARNINGS=$((WARNINGS + 1))
  fi

  # List consumers
  consumers=$(grep -rl "load_schema\|validate_artifact" "$REPO_ROOT/spectrum_systems/" "$REPO_ROOT/scripts/" --include="*.py" 2>/dev/null | \
    xargs grep -l "$contract" 2>/dev/null | head -10 || true)
  if [ -z "$consumers" ]; then
    echo "[INFO] $contract — no consumers found (may be unused or consumed externally)"
  fi
done

# Global checks executed once to avoid noisy duplicated output.
local_defs=$(grep -rl '"\$schema"' "$REPO_ROOT/spectrum_systems/" --include="*.py" 2>/dev/null | head -10 || true)
if [ -n "$local_defs" ]; then
  echo "[WARN] inline JSON Schema (\$schema) found in Python source:"
  echo "$local_defs" | sed 's/^/    /'
  WARNINGS=$((WARNINGS + 1))
fi

direct_reads=$(grep -rl "\.schema\.json" "$REPO_ROOT/spectrum_systems/" --include="*.py" 2>/dev/null | \
  xargs grep -l "open\|read\|load" 2>/dev/null | head -10 || true)
if [ -n "$direct_reads" ]; then
  echo "[WARN] direct schema file reads detected (use load_schema instead):"
  echo "$direct_reads" | sed 's/^/    /'
  WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo "[contract-boundary-audit] summary: errors=$ERRORS warnings=$WARNINGS"
if [ "$ERRORS" -gt 0 ]; then
  echo "[contract-boundary-audit] FAIL — $ERRORS error(s) found."
  exit 1
fi
if [ "$WARNINGS" -gt 0 ] && [ "$STRICT_MODE" -eq 1 ]; then
  echo "[contract-boundary-audit] FAIL — warnings treated as errors in strict mode."
  exit 1
else
  if [ "$WARNINGS" -gt 0 ]; then
    echo "[contract-boundary-audit] PASS-WARN — no blocking violations detected."
  else
    echo "[contract-boundary-audit] PASS — no contract boundary violations detected."
  fi
fi
