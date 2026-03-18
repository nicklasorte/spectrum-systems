#!/usr/bin/env bash
# contract-boundary-audit/run.sh
# Usage: ./run.sh [CONTRACT_NAME]
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
CONTRACT_NAME="${1:-}"
SCHEMAS_DIR="$REPO_ROOT/contracts/schemas"
MANIFEST="$REPO_ROOT/contracts/standards-manifest.json"
VIOLATIONS=0

if [ ! -f "$MANIFEST" ]; then
  echo "[ERROR] standards-manifest.json not found at $MANIFEST" >&2
  exit 1
fi

echo "[contract-boundary-audit] Starting audit..."
echo "  Schemas dir : $SCHEMAS_DIR"
echo "  Manifest    : $MANIFEST"
echo ""

# Collect schema files to audit
if [ -n "$CONTRACT_NAME" ]; then
  SCHEMA_FILES=("$SCHEMAS_DIR/${CONTRACT_NAME}.schema.json")
else
  SCHEMA_FILES=("$SCHEMAS_DIR"/*.schema.json)
fi

for schema_file in "${SCHEMA_FILES[@]}"; do
  [ -f "$schema_file" ] || { echo "[SKIP] $schema_file not found"; continue; }
  contract=$(basename "$schema_file" .schema.json)

  # Check manifest has this contract (proper JSON key lookup)
  if ! python3 -c "
import json, sys
with open('$MANIFEST') as f:
    m = json.load(f)
# Manifest may be a dict with a 'contracts' or 'schemas' key, or a flat dict
keys = set()
if isinstance(m, dict):
    for section in m.values():
        if isinstance(section, dict):
            keys.update(section.keys())
    keys.update(m.keys())
if '$contract' not in keys:
    sys.exit(1)
" 2>/dev/null; then
    echo "[WARN] $contract — not referenced in standards-manifest.json (may be unpublished)"
  fi

  # Check for local schema definitions in Python source
  # Look for JSON Schema-specific markers: '\$schema' keyword inside Python string literals
  local_defs=$(grep -rl '"\$schema"' "$REPO_ROOT/spectrum_systems/" --include="*.py" 2>/dev/null | head -5 || true)
  if [ -n "$local_defs" ]; then
    echo "[WARN] $contract — inline JSON Schema (\$schema) found in Python source:"
    echo "$local_defs" | sed 's/^/    /'
    VIOLATIONS=$((VIOLATIONS + 1))
  fi

  # Check for direct .schema.json file reads bypassing load_schema
  direct_reads=$(grep -rl "\.schema\.json" "$REPO_ROOT/spectrum_systems/" --include="*.py" 2>/dev/null | \
    xargs grep -l "open\|read\|load" 2>/dev/null | head -5 || true)
  if [ -n "$direct_reads" ]; then
    echo "[WARN] $contract — direct schema file reads detected (use load_schema instead):"
    echo "$direct_reads" | sed 's/^/    /'
    VIOLATIONS=$((VIOLATIONS + 1))
  fi

  # List consumers
  consumers=$(grep -rl "load_schema\|validate_artifact" "$REPO_ROOT/spectrum_systems/" "$REPO_ROOT/scripts/" --include="*.py" 2>/dev/null | \
    xargs grep -l "$contract" 2>/dev/null | head -10 || true)
  if [ -z "$consumers" ]; then
    echo "[INFO] $contract — no consumers found (may be unused or consumed externally)"
  fi
done

echo ""
if [ "$VIOLATIONS" -gt 0 ]; then
  echo "[contract-boundary-audit] FAIL — $VIOLATIONS violation(s) found."
  exit 1
else
  echo "[contract-boundary-audit] PASS — no contract boundary violations detected."
fi
