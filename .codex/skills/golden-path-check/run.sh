#!/usr/bin/env bash
# golden-path-check/run.sh
# Usage: ./run.sh <CONTRACT_NAME>
set -euo pipefail

CONTRACT_NAME="${1:-}"
if [ -z "$CONTRACT_NAME" ]; then
  echo "[ERROR] Usage: $0 <CONTRACT_NAME>" >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
FIXTURE="$REPO_ROOT/contracts/examples/${CONTRACT_NAME}.example.json"

if [ ! -f "$FIXTURE" ]; then
  echo "[ERROR] Golden-path fixture not found: $FIXTURE"
  echo "Create the fixture in contracts/examples/ before running VALIDATE."
  exit 1
fi

python3 - "$REPO_ROOT" "$CONTRACT_NAME" "$FIXTURE" <<'PYEOF'
import json, sys
from pathlib import Path

repo_root = sys.argv[1]
contract_name = sys.argv[2]
fixture_path = Path(sys.argv[3])

sys.path.insert(0, repo_root)
from spectrum_systems.contracts import load_schema, validate_artifact

with fixture_path.open() as f:
    instance = json.load(f)

try:
    validate_artifact(instance, contract_name)
    print(f"[GOLDEN PATH OK] {contract_name} — fixture is schema-valid.")
except Exception as e:
    print(f"[GOLDEN PATH FAIL] {contract_name} — validation error:")
    print(f"  {e}")
    sys.exit(1)
PYEOF
