# System Factory Integration — Governed Scaffolding

This document describes how spectrum-systems supports governance-compliant repository creation via the `scaffold_governed_repo.py` tool.

---

## Purpose

Every new repository in the spectrum ecosystem should be **born governance-compliant**.  This means the repo ships with:

- A pinned governance manifest (`.spectrum-governance.json`)
- A machine-readable governance declaration (`governance/governance-declaration.json`)
- Baseline CI workflows that validate governance artifacts
- A stub README referencing governance expectations
- A ready-to-add ecosystem registry entry (`registry-entry.json`)

The `scripts/scaffold_governed_repo.py` tool automates generation of all these artifacts.  It reads authoritative data from spectrum-systems itself (contract versions, schema locations) so the output is always aligned to the current governance baseline.

---

## Quick start

```bash
python scripts/scaffold_governed_repo.py \
  --repo-name my-new-engine \
  --repo-type operational_engine \
  --system-id my-new-engine \
  --owner nicklasorte \
  --output-dir /path/to/new/repo
```

No network calls are made.  All output is deterministic for a given set of inputs.

---

## Required inputs

| Argument | Description | Example |
|----------|-------------|---------|
| `--repo-name` | Repository slug (lowercase, hyphens allowed) | `my-new-engine` |
| `--repo-type` | Architecture archetype (see table below) | `operational_engine` |
| `--system-id` | Canonical system ID — must equal `repo-name` | `my-new-engine` |
| `--owner` | GitHub organization or username | `nicklasorte` |
| `--output-dir` | Directory to write scaffold into (created if absent) | `/tmp/my-new-engine` |
| `--declared-at` | ISO 8601 date override (optional, default: today) | `2026-03-17` |

---

## Supported repo types

| `--repo-type` | Ecosystem layer | Description |
|---------------|-----------------|-------------|
| `governance` | Layer 2 | Governance/control-plane repository |
| `factory` | Layer 1 | Scaffolding/factory repository |
| `operational_engine` | Layer 3 | Operational engine that consumes and emits governed artifacts |
| `pipeline` | Layer 4 | Orchestration layer that sequences governed artifacts |
| `advisory` | Layer 5 | Advisory outputs derived from readiness bundles |

Default contract sets per type are defined in `scaffold-templates/repo-type-contracts.json`.

---

## What gets generated automatically

| File | Description |
|------|-------------|
| `.spectrum-governance.json` | Governance manifest with `system_id`, `repo_type`, pinned contracts |
| `governance/governance-declaration.json` | Full governance declaration: contract pins, schema pins, declared_at, architecture source |
| `.github/workflows/validate-governance.yml` | CI workflow: validates manifest, declaration, and contract examples |
| `README.md` | Stub README with governance table and next-steps checklist |
| `registry-entry.json` | Ready-to-add entry for `ecosystem/ecosystem-registry.json` in spectrum-systems |

---

## What still must be filled in manually

After running the scaffold tool, complete the following before the repo is fully governed:

1. **`governance/governance-declaration.json`** — fill in:
   - `last_evaluation_date` — date of first successful evaluation harness run
   - `evaluation_manifest_path` — path to the eval README or manifest in the implementation repo
   - `rule_version` — if the repo uses a rules pack from spectrum-systems
   - `prompt_set_hash` — if the repo depends on versioned prompts
   - `external_storage_policy` — describe how external inputs/outputs are stored at runtime

2. **`registry-entry.json`** — add the entry to `ecosystem/ecosystem-registry.json` in spectrum-systems.

3. **Design package** — create `design-packages/<system-id>.design-package.json` in spectrum-systems.

4. **Governance manifest** in spectrum-systems — add a manifest at `governance/examples/manifests/<system-id>.spectrum-governance.json`.

5. **Validate** — run the governance manifest validator:
   ```bash
   python spectrum-systems/scripts/validate_governance_manifest.py .spectrum-governance.json
   ```

---

## Contract pinning

Contracts in `.spectrum-governance.json` are pinned to the versions declared in `contracts/standards-manifest.json` **at the time the scaffold is run**.

The mapping of repo type to default contracts lives in `scaffold-templates/repo-type-contracts.json`.  Only contracts relevant to the repo type are included.  Extend `contracts` in `.spectrum-governance.json` once the repo is consuming additional artifact types.

---

## CI workflows

The generated `.github/workflows/validate-governance.yml` performs three checks on every push to `main` and on pull requests:

| Job | What it checks |
|-----|---------------|
| `validate-governance-manifest` | `.spectrum-governance.json` passes schema + registry + standards-manifest validation |
| `validate-governance-declaration` | `governance/governance-declaration.json` exists and contains all required fields |
| `validate-contract-examples` | Any files in `contracts/examples/*.json` validate against the canonical schemas in spectrum-systems |

---

## Ecosystem registry alignment

After scaffolding, add the contents of `registry-entry.json` into `ecosystem/ecosystem-registry.json` in spectrum-systems.  The generated entry pre-populates:

- `repo_name` / `repo_url` / `repo_type` / `layer`
- `system_id`
- `manifest_required: true`
- `contracts` list (alphabetically sorted)
- `description`

Set `status` to `active` once the repo is live, replacing the default `planned`.

---

## Governance declaration fields reference

| Field | Required | Description |
|-------|----------|-------------|
| `governance_declaration_version` | yes | Schema version for this declaration format (`"1.0.0"`) |
| `architecture_source` | yes | Always `"nicklasorte/spectrum-systems"` |
| `standards_manifest_version` | yes | Value of `standards_version` from `contracts/standards-manifest.json` |
| `system_id` | yes | Canonical identifier matching ecosystem registry |
| `implementation_repo` | yes | GitHub slug `owner/repo-name` |
| `declared_at` | yes | ISO 8601 date this declaration was filed |
| `contract_pins` | yes | Map `artifact_type → schema_version` for every consumed contract |
| `schema_pins` | yes | Map `path/to/schema.json → version` for imported schemas |
| `rule_version` | yes (nullable) | Rule-pack version imported from `rules/` in spectrum-systems |
| `prompt_set_hash` | yes (nullable) | SHA-256 of prompt files this system depends on |
| `evaluation_manifest_path` | yes | Repo-relative path to the evaluation README or manifest |
| `last_evaluation_date` | yes (nullable) | ISO 8601 date of the most recent evaluation run |
| `external_storage_policy` | yes | How external artifacts are stored at runtime |

---

## Testing

Tests for the governed scaffolding live in `tests/test_scaffold_governed_repo.py`.  They verify:

- All required output files are generated
- `.spectrum-governance.json` conforms to `governance/schemas/spectrum-governance.schema.json`
- All pinned contract versions match `contracts/standards-manifest.json`
- Every supported repo type produces valid output
- Output is deterministic for identical inputs
- Invalid repo types raise a clear error

Run tests with:

```bash
python -m pytest tests/test_scaffold_governed_repo.py -v
```

---

## Example generated structure

For `--repo-type operational_engine`:

```
my-new-engine/
├── .github/
│   └── workflows/
│       └── validate-governance.yml   # CI: governance compliance checks
├── governance/
│   └── governance-declaration.json   # Full governance declaration
├── .spectrum-governance.json          # Pinned manifest
├── README.md                          # Stub with governance table
└── registry-entry.json                # Add this to spectrum-systems ecosystem registry
```

---

## Follow-on recommendations for spectrum-systems alignment

1. **Extend `scaffold-templates/repo-type-contracts.json`** as new contract types are published to `contracts/standards-manifest.json`.

2. **Update the CI workflow template** at `scaffold-templates/ci-workflows/validate-governance.yml` when new governance checks are required for all ecosystem repos.

3. **Automate registry addition** — consider a CI step in spectrum-systems that validates any new `registry-entry.json` files submitted via PR.

4. **Design package validation** — the scaffold does not create a design package in spectrum-systems; consider a follow-up script that pre-creates the design package stub.

5. **Governance declaration schema** — once `contracts/governance-declaration.template.json` is versioned as a formal schema, add declaration validation to the generated CI workflow.
