# Policy-as-Code Governance Layer

Spectrum Systems moves governance from static documentation to executable policy checks. The policy engine evaluates deterministic rules against governance manifests, the ecosystem registry, the standards manifest, and (when available) the dependency graph. This reduces schema drift, detects unsafe contract usage, and makes enforcement auditable.

## Policy registry
- Location: `governance/policies/policy-registry.json`
- Schema: `governance/policies/policy-registry.schema.json`
- Fields: `policy_id`, `title`, `description`, `severity` (`error` | `warning`), `enabled` (boolean), `scope` (`repo` | `ecosystem` | `contract`), `input_artifacts` (string array), `expected_check`.
- The registry is the single source of truth for executable governance rules. Policies are enabled/disabled here, not in code.

## Policy engine
- Location: `governance/policies/run-policy-engine.py`
- Inputs:
  - Ecosystem registry: `ecosystem/ecosystem-registry.json`
  - Standards manifest: `contracts/standards-manifest.json`
  - Governance manifests: `governance/examples/manifests/*.json`
  - Dependency graph (optional): `artifacts/ecosystem-dependency-graph.json`
  - Policy registry: `governance/policies/policy-registry.json`
- Outputs (deterministic):
  - JSON report: `artifacts/policy-engine-report.json`
  - Human-readable summary: `artifacts/policy-engine-summary.md`
- Execution: `python governance/policies/run-policy-engine.py`
- Interpretation:
  - `error` severity with `fail` status fails CI.
  - `warning` severity produces non-blocking findings; status `warning` surfaces drift without halting pipelines.

## How checks work
1. Load enabled policies from the registry.
2. Build context from the registry, standards manifest, governance manifests, and dependency graph (if present).
3. Evaluate each policy deterministically, emitting a result per subject (repo, contract, or ecosystem scope).
4. Summarize counts and group findings by repository for triage.

## Current policies
- GOV-001: Repo must exist in ecosystem registry (error)
- GOV-002: Repo must declare a governance manifest (error)
- GOV-003: Manifest system_id must match registry entry (error)
- GOV-004: Manifest contract pins must exist in standards manifest (error)
- GOV-005: Repo must not consume undeclared contracts (warning)
- GOV-006: Standards manifest intended consumers must exist in ecosystem registry (warning)
- GOV-007: Dependency graph systems must resolve to registered repos (error)
- GOV-008: Governance repo must not contain production implementation package paths (warning)

## Future direction
- Add remediation hints and recommended diffs for failing policies.
- Auto-open PRs for warning-grade hygiene fixes once lifecycle gates are defined.
- Expand contract safety checks to include version skew and provenance completeness.
- Attach provenance for each policy evaluation so downstream consumers can trace inputs and evidence.
