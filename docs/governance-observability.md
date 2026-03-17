# Governance Observability

This document explains the ecosystem observability layer for the spectrum-systems governance architecture.

## What Is Ecosystem Observability?

Ecosystem observability means the ability to inspect the health, compliance status, and maturity of every repository in the governed ecosystem — deterministically, without manual inspection.

The observability layer produces:

- a **machine-readable health artifact** that is easy to diff and suitable for CI gates
- **human-readable reports** that provide a quick health snapshot
- an **architecture/dependency graph** that maps repositories, contracts, and layer relationships
- a **lightweight dashboard** for at-a-glance visibility

All artifacts are generated from local sources (no network calls required) and are reproducible given the same inputs.

---

## Generated Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Ecosystem health JSON | `governance/reports/ecosystem-health.json` | Machine-readable per-repo health snapshot |
| Ecosystem health report | `docs/governance-reports/ecosystem-health-report.md` | Human-readable health summary with tables |
| Ecosystem dashboard | `docs/governance-reports/ecosystem-dashboard.md` | Lightweight dashboard for quick visibility |
| Architecture graph JSON | `governance/reports/ecosystem-architecture-graph.json` | Machine-readable dependency/architecture graph |
| Architecture graph diagram | `governance/reports/ecosystem-architecture-graph.mmd` | Mermaid diagram of ecosystem architecture |

### Ecosystem Health JSON Schema

`governance/schemas/ecosystem-health.schema.json` — validates the structure of `ecosystem-health.json`.

### Architecture Graph JSON Schema

`governance/schemas/ecosystem-architecture-graph.schema.json` — validates the structure of `ecosystem-architecture-graph.json`.

---

## Maturity Scoring

Each repository receives a maturity score based on six categories:

| Category | Weight | Description |
|----------|--------|-------------|
| `governance_artifacts` | 2 | Governance manifest present when `manifest_required=true` |
| `contract_compliance` | 2 | Contract enforcement status from cross-repo validation |
| `schema_alignment` | 1 | All declared contract versions match canonical versions |
| `ci_enforcement` | 2 | CI workflows active and enforcing governance gates |
| `evaluation_evidence` | 2 | Evidence captured; maturity level ≥ 3 (per system registry) |
| `documentation` | 1 | Repository description present and substantive |

### Category States

Each category returns one of three states:

| State | Score | Meaning |
|-------|-------|---------|
| `compliant` | 2 | Requirement fully satisfied |
| `partial` | 1 | Partially satisfied or deferred (e.g., planned/experimental) |
| `missing` | 0 | Requirement not met |

### Aggregate Maturity Level (L1–L10)

The raw weighted score is mapped to a maturity level:

```
maturity_level = round( (raw_score / max_score) × 10 )
```

The result is clamped to the range L1–L10. This provides a coarse estimate aligned with the L0–L20 maturity model defined in `docs/system-maturity-model.md`.

> Note: The L1–L10 estimate produced here is a **governance-layer proxy**, not a full operational maturity assessment. Full maturity assessments follow the evidence-based process in `docs/level-0-to-20-playbook.md`.

---

## Architecture / Dependency Graph

The architecture graph captures:

- **Repository nodes** — each repo in the ecosystem registry with its type and layer
- **Contract nodes** — each governed contract from the standards manifest
- **Edges** — `consumes`, `produces`, and `layer_depends_on` relationships

Layer dependency edges follow the governance architecture:

```
Layer 1 (Factory)  →  Layer 2 (Governance)
Layer 3 (Engines)  →  Layer 2 (Governance)
Layer 4 (Pipeline) →  Layer 3 (Engines)
Layer 5 (Advisory) →  Layer 4 (Pipeline)
```

The Mermaid diagram (`ecosystem-architecture-graph.mmd`) can be rendered in GitHub Markdown, VS Code, or any Mermaid-compatible viewer.

---

## Input Sources

All observability generators read from these local files:

| Input | Path | Purpose |
|-------|------|---------|
| Ecosystem registry | `ecosystem/ecosystem-registry.json` | Repository list and metadata |
| System registry | `ecosystem/system-registry.json` | System roles and maturity levels |
| Maturity tracker | `ecosystem/maturity-tracker.json` | Maturity levels and evidence |
| Contract graph | `governance/reports/contract-dependency-graph.json` | Enforcement validation results |
| Policy engine report | `artifacts/policy-engine-report.json` | Policy pass/fail/warn per repo |
| Standards manifest | `contracts/standards-manifest.json` | Canonical contract versions |
| Governance manifests | `governance/examples/manifests/*.json` | Per-repo governance declarations |

---

## CI Integration

Observability reports are generated automatically in CI via the `observability-reports` job in `.github/workflows/cross-repo-compliance.yml`.

### Workflow Behavior

- Runs on every push to `main` and on `workflow_dispatch`
- Generates all observability artifacts after the `contract-enforcement` job completes
- Uploads artifacts as workflow outputs (`ecosystem-observability-reports`)
- **Does not fail CI** for `warning` or `not_yet_enforceable` states — only real governance failures cause CI failure

### Running Locally

```bash
# Run policy engine first (produces artifacts/policy-engine-report.json)
python governance/policies/run-policy-engine.py

# Run contract enforcement (produces governance/reports/contract-dependency-graph.json)
python scripts/run_contract_enforcement.py

# Generate ecosystem health report
python scripts/generate_ecosystem_health_report.py

# Generate architecture/dependency graph
python scripts/generate_ecosystem_architecture_graph.py
```

---

## Report Locations in CI

After a successful CI run, reports are available as workflow artifacts:

- `governance-compliance-report` — cross-repo compliance scan result
- `contract-enforcement-report` — per-repo contract validation
- `policy-engine-report` — policy engine findings
- `ecosystem-dependency-graph` — dependency graph from `build_dependency_graph.py`
- `ecosystem-observability-reports` — health report, dashboard, and architecture graph

---

## Related Documents

- `docs/system-maturity-model.md` — full L0–L20 maturity model definition
- `docs/level-0-to-20-playbook.md` — evidence-based progression guide
- `docs/governance-manifest.md` — governance manifest requirements
- `docs/governance-conformance-checklist.md` — compliance checklist
- `docs/cross-repo-compliance.md` — cross-repo validation overview
- `docs/policy-as-code.md` — policy engine design
- `CONTRACTS.md` — contract authority statement
