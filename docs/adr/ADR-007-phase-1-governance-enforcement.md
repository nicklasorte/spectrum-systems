# Phase 1 governance enforcement strategy

Status: Accepted

Date: 2026-03-16

## Context
`docs/governance-enforcement-roadmap.md` describes four enforcement phases for the ecosystem. As of 2026-03-16 no enforcement phase was active: no downstream implementation repo had filed a machine-verifiable governance commitment. Findings `[F-1]` and `[G1]` in `2026-03-16-governance-constitution-deep-review.md` rated this the highest-priority governance gap — every implementation repo could enter build-out without making any verifiable promise about which contract versions or schema versions it would consume.

The 2026-03-14 governance architecture review (finding `GA-007`) explicitly requested a `contracts/governance-declaration.template.json` as the concrete Phase 1 activation artifact. The 2026-03-15 ecosystem constitution audit (finding `RC-4`) and the 2026-03-15 cross-repo audit (finding `REC-4`) both listed Phase 1 activation as a prerequisite for maturity Level 3 (Governed).

## Decision
Adopt the following Phase 1 enforcement strategy:

1. **Declare before building.** Every implementation repo must author a `.governance-declaration.json` before reaching Pilot status. The file must conform to `contracts/governance-declaration.template.json` and pin the specific `standards_version` from `contracts/standards-manifest.json` that was current at the time of declaration.

2. **Pins over promises.** Phase 1 requires concrete, machine-readable version pins — `contract_pins`, `schema_pins`, `rule_version` — rather than prose statements. Pins create a verifiable baseline; any contract upgrade requires the implementation repo to update its pin and re-declare.

3. **Declaration + contract pins are the entry gate.** Phase 1 does not require automated CI validation (that is Phase 2). It requires that the declaration file exists, is schema-valid, and references real versions in `contracts/standards-manifest.json`. Manual verification via `docs/governance-conformance-checklist.md` is sufficient to confirm Phase 1 compliance.

4. **Phase 1 is Active when:** at least two implementation repos have filed conforming `.governance-declaration.json` files and the conformance checklist has been completed for each. Until then, Phase 1 remains Initiated.

5. **Roadmap relationship.** Phase 1 feeds Phase 2 (automated schema/contract validation), which feeds Phase 3 (CI-based conformance), which feeds Phase 4 (ecosystem-level compatibility validation). Each phase builds on the declaration artifact established in Phase 1; skipping or weakening Phase 1 delays all subsequent phases.

## Consequences
- Downstream repos that reach Pilot status without a valid `.governance-declaration.json` are considered non-compliant, regardless of how well they implement the underlying contracts.
- The conformance checklist (`docs/governance-conformance-checklist.md`) requires the governance declaration as a mandatory item; repos cannot claim checklist completion without it.
- `system-factory` must be updated to scaffold `.governance-declaration.json` from `contracts/governance-declaration.template.json` when it creates a new implementation repo.
- Changes to `contracts/standards-manifest.json` (new contract version or status change) should be accompanied by a notification to all repos with active declarations so they can re-pin.
- The roadmap document (`docs/governance-enforcement-roadmap.md`) is the single authoritative source for the current status of each enforcement phase; ADRs reference it but do not duplicate phase status.

## Alternatives considered
- **Skip Phase 1, go directly to CI validation.** Rejected because CI validation requires tooling that is not yet built; requiring declarations first establishes the data model that tooling will validate, and produces value (human-readable compliance evidence) even before automation exists.
- **Accept informal prose declarations in README files.** Rejected because prose is not schema-validated, cannot be parsed by `system-factory` or compliance scanners, and provides no version-pin structure for Phase 2 tooling to consume.
- **Delay Phase 1 until three or more implementation repos are ready.** Rejected because it creates a circular dependency — repos need the template to declare, and the template only gets created when enough repos are ready. Early adoption by one or two repos validates the template structure before the ecosystem scales.

## Related artifacts
- `contracts/governance-declaration.template.json` — canonical declaration template (Phase 1 activation artifact)
- `contracts/standards-manifest.json` — versioned contract and schema registry that declarations pin against
- `docs/governance-enforcement-roadmap.md` — four-phase enforcement roadmap; Phase 1 status: Initiated (2026-03-16)
- `docs/governance-conformance-checklist.md` — mandatory checklist including governance declaration requirement
- `docs/implementation-boundary.md` — boundary rules that declarations reinforce
- `docs/reviews/2026-03-14-governance-architecture-review.md` — finding GA-007
- `docs/reviews/2026-03-15-ecosystem-constitution-audit.md` — finding RC-4
- `docs/reviews/2026-03-15-cross-repo-ecosystem-architecture-review.md` — finding REC-4
- `docs/reviews/2026-03-16-governance-constitution-deep-review.md` — findings F-1, G1, REC-1
- `ADR-006-governance-manifest-policy-engine.md` — governance manifest and policy engine model
