# Governance Enforcement Roadmap

## Current state (manual enforcement)
- Governance rules, schemas, and contracts are published in this repository, but adherence is enforced through manual reviews and checklists (`docs/governance-conformance-checklist.md`, `docs/implementation-boundary.md`).
- Implementation repos self-assert compliance; there is no mechanical validation of declared contract versions, schema compatibility, or provenance coverage.
- Cross-repo consistency relies on human diligence rather than deterministic signals or CI.

## Future enforcement model
### Phase 1 — Declared identity and contract pins
- Every implementation repo must declare `system_id` and pin the contract and schema versions it implements (from `contracts/standards-manifest.json` and system interface docs).
- Declarations live in repo metadata (README/system overview) and machine-readable manifests to enable downstream automation.
- Outputs: consistent identity and version pins across the ecosystem; inputs: contract registry and interface specs; tests: manual verification via conformance checklist.

### Phase 2 — Automated validation of schema and contract versions
- Tooling validates manifests against the authoritative contract registry and schema governance rules (version format, allowed statuses, intended consumers).
- Validation runs locally and in pre-merge hooks to block drift (no local schema redefinition, no unpinned contract consumption).
- Outputs: validation reports and failure reasons; inputs: manifest + registry; tests: deterministic validation harness seeded with registry fixtures.

### Phase 3 — CI-based conformance checks across repos
- CI workflows execute the validation harness plus required evaluation tests for the declared system (inputs, outputs, and evaluation tests are mandatory per system).
- CI artifacts capture provenance (commit, manifest hash, seed, contract versions) to make conformance auditable.
- Outputs: CI pass/fail with traceable artifacts; inputs: manifests, declared contract versions, evaluation fixtures; tests: per-system conformance suites.

### Phase 4 — Ecosystem-level contract compatibility validation
- Cross-repo checks ensure that interacting systems declare mutually compatible contract versions and interface expectations.
- Compatibility matrix derived from `contracts/standards-manifest.json`, system interfaces, and dependency graph (`docs/ecosystem-map.md`, `SYSTEMS.md`).
- Outputs: ecosystem compatibility reports and upgrade guidance; inputs: per-repo manifests and dependency graph; tests: simulated upgrade/downgrade scenarios.

## System-factory path to automatic conformance
- `system-factory` will scaffold new implementation repos with required governance primitives: `system_id` declaration, contract pins pulled from the standards manifest, manifest templates, and pre-wired validation hooks.
- Scaffolded repos will include baseline CI jobs that run the validation harness and per-system evaluation tests, giving deterministic enforcement from day one.
- As manifests and contracts evolve, `system-factory` updates will deliver compatible scaffolds and migration notes, reducing manual retrofits and preserving governance alignment across the ecosystem.
