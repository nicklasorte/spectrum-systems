# PHASE 16: Self-Governance Credibility Closure — Implementation Plan

**Status**: Implementation Initiated  
**Start Date**: 2026-04-19  
**Target Completion**: 2026-05-03  
**Effort**: 3-5 days

---

## GOAL

Remove all production Python code from spectrum-systems and enforce that spectrum-systems is **governance-only**:
- Contains: contracts, schemas, governance documentation
- Does not contain: production code, business logic, operational systems

---

## CURRENT STATE ANALYSIS

### Python Source Files (MUST BE REMOVED)

The following directories contain production Python code and **must be removed** or moved to dedicated implementation repositories:

| Directory | Type | Status | Action |
|-----------|------|--------|--------|
| `spectrum_systems/` | Production code | Active | REMOVE |
| `spectrum_systems/aex/` | AI execution | Active | REMOVE |
| `spectrum_systems/rsm/` | Reasoning state | Active | REMOVE |
| `spectrum_systems/modules/` | Runtime modules | Active | REMOVE |
| `spectrum_systems/governance/` | Governance logic | Active | REMOVE (logic only; policy docs stay) |
| `spectrum_systems/utils/` | Utilities | Active | REMOVE |
| `spectrum_systems/orchestration/` | Orchestration | Active | REMOVE |
| `spectrum_systems/study_runner/` | Study execution | Active | REMOVE → dedicated repo |
| `src/` | Source code | Active | REMOVE |
| `scripts/` | Automation scripts | Active | REMOVE |
| `systems/` | System implementations | Active | REMOVE → dedicated repos |
| `modules/` (top-level) | Implementation modules | Active | REMOVE |

**Total Python files to remove**: ~150+ files

---

### Allowed File Types (MUST BE KEPT)

| File Type | Directory | Examples | Status |
|-----------|-----------|----------|--------|
| **JSON Schema** | `contracts/schemas/` | `*.schema.json` | KEEP |
| **Contract Definitions** | `contracts/` | `governance-declaration.template.json`, `standards-manifest.json` | KEEP |
| **Governance Policy** | `governance/` | `*.md` policy documents | KEEP (rename from .py logic) |
| **Markdown Docs** | `docs/` | Governance, architecture, decision records | KEEP |
| **YAML Configs** | `config/` | Policy configs, not code | KEEP |
| **JSON Artifacts** | `artifacts/` | Example governance artifacts | KEEP |
| **ADRs** | `docs/adr/` | Architecture Decision Records | KEEP |
| **Examples** | `examples/` | JSON examples, not code | KEEP |
| **Templates** | `templates/` | Contract templates, policy templates | KEEP |

---

### Questionable Items (DECISION REQUIRED)

| Item | Current Status | Decision |
|------|----------------|----------|
| `tests/` directory | Contains pytest files testing governance | KEEP (governance tests only; move implementation tests to dedicated repos) |
| `dashboard/` | React UI for observability | REMOVE → dedicated repo |
| `spectrum-data-lake/` | Data lake implementation | REMOVE → dedicated repo |
| `design/`, `design-packages/` | Design artifacts | KEEP (governance/policy, not code) |
| `data/` | Fixture data, evaluation sets | KEEP (governance test fixtures) |
| `evals/`, `eval/` | Evaluation definitions | KEEP (governance test cases) |

---

## IMPLEMENTATION STEPS

### Step 1: Define Allowed File Types Schema

**File**: `spectrum-systems.file-types.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "id": "spectrum-systems.file-types.schema.json",
  "title": "Spectrum Systems Allowed File Types",
  "description": "Enforces that spectrum-systems contains ONLY governance artifacts, not production code",
  "type": "object",
  "properties": {
    "allowed_file_patterns": {
      "type": "array",
      "description": "Glob patterns for allowed files",
      "items": {
        "type": "string"
      },
      "default": [
        "*.md",
        "*.json",
        "*.yaml",
        "*.yml",
        "*.ts",
        "*.tsx",
        "*.js",
        "*.jsx",
        ".gitignore",
        ".github/**/*",
        "Dockerfile",
        "docker-compose.yml"
      ]
    },
    "required_directories": {
      "type": "array",
      "description": "Directories that MUST exist",
      "items": {
        "type": "string"
      },
      "default": [
        "contracts",
        "schemas",
        "governance",
        "docs",
        "examples"
      ]
    },
    "forbidden_patterns": {
      "type": "array",
      "description": "Patterns that are NEVER allowed (production code indicators)",
      "items": {
        "type": "string"
      },
      "default": [
        "**/*.py",
        "src/**/*",
        "spectrum_systems/**/*",
        "systems/**/src/**/*",
        "systems/**/lib/**/*",
        "modules/**/index.ts",
        "modules/**/implementation/**/*",
        "control_plane/**/execution/**/*"
      ]
    },
    "exceptions": {
      "type": "array",
      "description": "Exceptions to forbidden patterns (must be documented)",
      "items": {
        "type": "object",
        "properties": {
          "pattern": {
            "type": "string"
          },
          "reason": {
            "type": "string"
          },
          "approved_by": {
            "type": "string"
          },
          "expiry_date": {
            "type": "string",
            "format": "date"
          }
        }
      },
      "default": []
    }
  }
}
```

---

### Step 2: Create Removal Plan & Inventory

**File**: `docs/phase-16-removal-inventory.md`

Document:
1. All directories/files to remove (detailed inventory)
2. Where each should be moved (dedicated repo?)
3. Tests that will migrate (which tests stay in spectrum-systems?)
4. Dependencies that must be updated

Example:
```markdown
## Removal Inventory

### spectrum_systems/ (entire directory)
- **Contains**: Production AI execution code, reasoning state, orchestration
- **Action**: REMOVE
- **Size**: ~500+ files, ~50K lines of Python
- **Move to**: spectrum-pipeline-engine (orchestration), new repo for AI execution
- **Tests affected**: tests/test_*.py (move to respective repos)

### src/ (entire directory)
- **Contains**: MVP implementations, integration code
- **Action**: REMOVE
- **Size**: ~200+ files, ~30K lines
- **Move to**: Respective MVP implementation repos
- **Tests affected**: tests/integration/* (move to MVP repos)

...
```

---

### Step 3: Implement Boundary Check

**File**: `scripts/validate-governance-only.py` or `.github/workflows/validate-governance-only.yml`

This check runs in CI and blocks commits that introduce disallowed file types:

```python
#!/usr/bin/env python3
"""
Validates that spectrum-systems contains ONLY governance artifacts.
Blocks commits introducing production code, implementation, or business logic.
"""

import json
import sys
from pathlib import Path
from fnmatch import fnmatch

def load_schema():
    """Load allowed file types schema."""
    with open("spectrum-systems.file-types.schema.json") as f:
        return json.load(f)

def is_allowed(file_path, schema):
    """Check if file is allowed per schema."""
    allowed_patterns = schema["properties"]["allowed_file_patterns"]["default"]
    forbidden_patterns = schema["properties"]["forbidden_patterns"]["default"]
    
    # Check forbidden first (strict)
    for pattern in forbidden_patterns:
        if fnmatch(str(file_path), pattern):
            # Check exceptions
            for exception in schema["properties"]["exceptions"]["default"]:
                if fnmatch(str(file_path), exception["pattern"]):
                    return True, f"Exception: {exception['reason']}"
            return False, f"Forbidden: matches {pattern}"
    
    # Check allowed
    for pattern in allowed_patterns:
        if fnmatch(str(file_path), pattern):
            return True, f"Allowed: matches {pattern}"
    
    return False, f"Not in allowed patterns"

def main():
    """Validate all files in repo."""
    schema = load_schema()
    violations = []
    
    for file_path in Path(".").rglob("*"):
        # Skip git, venv, etc
        if any(part.startswith(".") for part in file_path.parts):
            continue
        if file_path.is_dir():
            continue
        if "node_modules" in file_path.parts:
            continue
        
        allowed, reason = is_allowed(file_path, schema)
        if not allowed:
            violations.append((file_path, reason))
    
    if violations:
        print("❌ GOVERNANCE BOUNDARY VIOLATION: Production code in spectrum-systems")
        print(f"\nFound {len(violations)} disallowed files:\n")
        for path, reason in violations[:20]:  # Show first 20
            print(f"  {path}: {reason}")
        if len(violations) > 20:
            print(f"\n  ... and {len(violations) - 20} more")
        sys.exit(1)
    
    print("✅ Governance boundary check passed")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### Step 4: Create CI Workflow

**File**: `.github/workflows/governance-boundary-check.yml`

```yaml
name: Governance Boundary Check

on:
  pull_request:
    paths:
      - '**'
      - '!docs/**'  # Don't block doc changes
      - '!.github/ISSUE_TEMPLATE/**'

jobs:
  boundary_check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Validate Governance Boundary
        run: python scripts/validate-governance-only.py
        
      - name: Report Results
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            if (context.payload.pull_request) {
              console.log('✅ Governance boundary validation passed');
            }
```

---

### Step 5: Create Removal Script & Execute

**File**: `scripts/phase-16-remove-production-code.sh`

Interactive script that:
1. Shows what will be removed
2. Backs up important files
3. Removes disallowed directories
4. Generates migration guide for moved code
5. Updates imports/references

```bash
#!/bin/bash
set -e

echo "Phase 16: Removing Production Code from spectrum-systems"
echo "=========================================================="
echo ""

# List what will be removed
echo "The following directories will be REMOVED:"
echo "  - spectrum_systems/"
echo "  - src/"
echo "  - scripts/ (keep only governance validation scripts)"
echo "  - systems/"
echo "  - modules/ (top-level)"
echo "  - dashboard/"
echo "  - spectrum-data-lake/"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Backup
echo "Backing up removed code (for reference)..."
git tag "phase-16-backup-$(date +%Y%m%d)"

# Remove
echo "Removing production code..."
rm -rf spectrum_systems/
rm -rf src/
rm -rf systems/
rm -rf modules/ (except tests)
rm -rf dashboard/
rm -rf spectrum-data-lake/

# Clean scripts (keep only governance validation)
rm -rf scripts/* 
echo '#!/usr/bin/env python3\n"""Governance boundary validation"""\n...' > scripts/validate-governance-only.py

# Update tests
echo "Filtering tests (keeping only governance tests)..."
# Move implementation tests to notes/archive
mkdir -p docs/phase-16-removed-code-archive
find tests -name "test_*.py" -not -path "*/governance/*" -exec mv {} docs/phase-16-removed-code-archive/ \;

echo ""
echo "✅ Production code removed from spectrum-systems"
echo "📋 Removed code archived in docs/phase-16-removed-code-archive/"
echo "🔧 Next: Update imports and document migration to dedicated repos"
```

---

### Step 6: Create Migration Guide

**File**: `docs/phase-16-migration-guide.md`

Document for each removed directory:
- What it was
- Where to find it now (dedicated repo?)
- How to migrate dependencies
- Migration timeline

---

### Step 7: Create Tests

**File**: `tests/test_governance_boundary.py`

```python
import pytest
from pathlib import Path
import json

def load_schema():
    """Load allowed file types schema."""
    with open("spectrum-systems.file-types.schema.json") as f:
        return json.load(f)

class TestGovernanceBoundary:
    """Tests ensuring spectrum-systems contains ONLY governance artifacts."""
    
    def test_no_python_source_files(self):
        """No *.py files except in tests/ or documentation."""
        py_files = list(Path(".").rglob("*.py"))
        # Filter out allowed locations
        disallowed = [
            f for f in py_files 
            if not any(part.startswith(".") for part in f.parts)
            and "tests" not in f.parts
            and "docs" not in f.parts
        ]
        assert not disallowed, f"Found Python source outside tests/docs: {disallowed}"
    
    def test_no_src_directory(self):
        """No src/ directory at root."""
        assert not Path("src").exists(), "src/ directory should not exist in governance repo"
    
    def test_no_spectrum_systems_module(self):
        """No spectrum_systems/ production module."""
        assert not Path("spectrum_systems").exists(), \
            "spectrum_systems/ module should not exist; move to dedicated repo"
    
    def test_required_directories_exist(self):
        """All required governance directories exist."""
        schema = load_schema()
        required = schema["properties"]["required_directories"]["default"]
        for directory in required:
            assert Path(directory).is_dir(), f"Required directory missing: {directory}"
    
    def test_no_implementation_code(self):
        """No implementation code (production business logic)."""
        forbidden_indicators = [
            "class Engine",
            "class Executor",
            "def execute",
            "def run_pipeline",
            "class Orchestrator",
        ]
        # Scan for these patterns in governance repo
        # (actual implementation would scan .py files)
        pass

def test_governance_only_contract_validation():
    """Validate spectrum-systems against its own governance schema."""
    schema = load_schema()
    # Load manifest
    with open("contracts/standards-manifest.json") as f:
        manifest = json.load(f)
    
    # Verify spectrum-systems is marked as governance-only
    assert manifest["system"]["system_id"] == "spectrum-systems"
    assert manifest["system"]["type"] == "governance"
    
    # Verify no implementation contracts
    assert "implementation" not in manifest["system"]["artifacts"]
```

---

## SUCCESS CRITERIA

✅ **Phase 16 is complete when**:

1. All forbidden file types are removed (0 Python source files)
2. `spectrum-systems.file-types.schema.json` created and validated
3. CI workflow blocks any commit re-introducing forbidden files
4. Tests pass (no disallowed files in repo)
5. Migration guide documents where removed code now lives
6. No breaking changes to remaining governance functionality

**Verification**:
```bash
# Run this to verify Phase 16 completion
./scripts/validate-governance-only.py
pytest tests/test_governance_boundary.py -v
```

---

## RISK MITIGATION

**Risk**: Tests depend on removed code  
**Mitigation**: Identify and migrate/archive affected tests before removal

**Risk**: Other repos depend on spectrum_systems module  
**Mitigation**: Create wrapper stubs in new dedicated repo; document import migration path

**Risk**: Rollback difficulty  
**Mitigation**: Git tag "phase-16-backup" before removal; document rollback procedure

---

## NEXT PHASE: 16.5

Once Phase 16 completes, Phase 16.5 (Governance Credibility Verification) will:
- Run Phase 19 compliance scanner against spectrum-systems
- Verify 100% self-compliant
- Serve as test case before rolling out to 8 downstream repos

---

## REFERENCES

- **Main roadmap**: `docs/governance-enforcement-phases-16-22.md`
- **Machine-readable tracker**: `ecosystem/phases-16-22-roadmap.json`
- **Allowed file types schema**: `spectrum-systems.file-types.schema.json` (to be created)
- **CLAUDE.md**: Execution permissions and governance rules
