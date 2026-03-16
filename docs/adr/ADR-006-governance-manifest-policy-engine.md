# Governance manifest and policy engine model

Status: Accepted

Date: 2026-03-16

## Context
The ecosystem needed a way to verify that downstream implementation repositories honour the contracts, schemas, and rules published in `spectrum-systems`. Manual review checklists and documentation alone cannot scale to ten or more implementation repos without producing observable drift — contract version mismatches, schema redefinitions, and absent provenance coverage can all go undetected until runtime failures.

Reviews from 2026-03-14 through 2026-03-16 (specifically `GA-007` from `2026-03-14-governance-architecture-review`, findings `[F-1]` and `[G1]` from `2026-03-16-governance-constitution-deep-review`) repeatedly identified the absence of a machine-readable governance declaration format as the single most critical gap preventing advancement from maturity Level 2 (Structured) to Level 3 (Governed).

## Decision
Adopt a governance manifest and policy engine model that separates concerns into three layers:

1. **Governance declarations** — machine-readable files (`.governance-declaration.json`) that each downstream implementation repo authors and maintains. The canonical template is `contracts/governance-declaration.template.json`. Each declaration pins `system_id`, `architecture_source`, `contract_pins`, `schema_pins`, `rule_version`, `evaluation_manifest_path`, and `last_evaluation_date` to specific versions published in `contracts/standards-manifest.json`.

2. **Contracts and schemas** — the authoritative published specifications that declarations pin against. `contracts/schemas/` is the canonical directory for governed artifact contract schemas. `contracts/standards-manifest.json` is the versioned registry. Downstream repos import schemas from these locations and must not redefine them locally.

3. **Governance policy engine** — `governance/policies/run-policy-engine.py` evaluates any governance manifest against four policies (GOV-001 through GOV-004) and produces a machine-readable pass/fail result. The engine is the kernel of mechanical enforcement; it will be wired to CI workflows as enforcement phases advance (see `docs/governance-enforcement-roadmap.md`).

The policy engine model separates *what is declared* (governance declarations) from *what is verified* (policy checks) and from *what is authoritative* (contracts, schemas, and registries), giving each layer a clear owner and a predictable evolution path.

## Consequences
- Each implementation repo must maintain a `.governance-declaration.json` conforming to `contracts/governance-declaration.template.json`; absence constitutes a governance gap.
- The conformance checklist (`docs/governance-conformance-checklist.md`) requires a valid governance declaration before a repo can claim compliance.
- Changes to the contract or schema authority (i.e., additions to `contracts/standards-manifest.json` or `contracts/schemas/`) must be reflected in downstream declarations; the standards manifest version field enables automated detection of stale declarations.
- The policy engine can be extended with new policies without touching declarations or contracts, keeping enforcement logic decoupled.
- `system-factory` is expected to scaffold `.governance-declaration.json` files automatically for new repos, closing the governance gap from day one.

## Alternatives considered
- **Documentation-only governance** — requiring declarations in Markdown rather than a machine-readable format. Rejected because it cannot be validated programmatically and cannot be consumed by `system-factory` or CI workflows.
- **Central registry as the sole truth** — tracking compliance centrally in `spectrum-systems` without requiring per-repo declarations. Rejected because it creates a bottleneck and means the czar repo must be updated every time an implementation repo changes; distributed ownership is more scalable.
- **Inline compliance markers in README files** — quick to author but unstructured, not schema-validated, and unversioned. Rejected for the same programmatic-validation reasons as documentation-only governance.

## Related artifacts
- `contracts/governance-declaration.template.json` — canonical declaration template (Phase 1 activation artifact)
- `contracts/standards-manifest.json` — versioned contract registry
- `contracts/schemas/` — canonical governed contract schema directory
- `docs/governance-enforcement-roadmap.md` — four-phase enforcement roadmap (Phase 1: Initiated 2026-03-16)
- `docs/governance-conformance-checklist.md` — implementation repo compliance checklist
- `governance/policies/run-policy-engine.py` — governance policy engine
- `docs/reviews/2026-03-14-governance-architecture-review.md` — finding GA-007 (governance declaration template)
- `docs/reviews/2026-03-16-governance-constitution-deep-review.md` — findings F-1, G1, REC-1
- `ADR-007-phase-1-governance-enforcement.md` — Phase 1 enforcement strategy
- `ADR-008-schema-authority-designation.md` — canonical schema authority
