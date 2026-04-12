# PLAN — DASHBOARD-NEXT-PHASE-SERIAL-01 (BUILD)

## Scope
Implement governed dashboard expansion as a read-only operator surface with explicit panel contracts, ownership mapping, read-model compilation, provenance fidelity, contract-backed normalization, certification gating, and evidence-first panels for trust/control/judgment/override/replay/coverage/trends/reconciliation/ledger/drift/scenario/mobile semantics.

## Canonical alignment
- Source authority: `README.md` and `docs/architecture/system_registry.md`.
- Runtime invariants preserved: artifact-first execution, fail-closed behavior, promotion requires certification.
- No new system ownership introduced; dashboard remains consumer-only.

## Execution steps
1. Add dashboard surface contract registry and panel capability map with exhaustive ownership metadata and fail-closed status declarations.
2. Add pure read-model compiler and contract-backed status normalization; prohibit selector-side decision logic.
3. Add field-level provenance map registry and consume it in the read model.
4. Add dashboard certification gate and tests to block uncontracted or weakly-governed panel changes.
5. Expand loader/types/selector and UI sections to render governed trust/control/judgment/override/replay/coverage/trend/reconciliation/ledger/drift/scenario/mobile surfaces.
6. Add dashboard tests for contract coverage, ownership, provenance fidelity, fail-closed unknowns, panel source fidelity, certification gate enforcement, and simulator fixture-only behavior.
7. Write delivery + red-team review artifacts (review 1, repairs, review 2, hardening summary).
8. Run dashboard build/tests and repo pytest for changed surface validation.

## Hard checkpoints
- Checkpoint 1: contracts/capability/compiler/provenance/normalization/certification gate implemented with tests.
- Checkpoint 2: trust/control/judgment/override panels evidence-backed and read-only.
- Checkpoint 3: replay/certification, weighted coverage, trend thresholds, high-risk reconciliation implemented.
- Checkpoint 4: outage/ledger/drift/simulator/mobile semantics implemented.
- Checkpoint 5: red-team artifacts + repair passes complete and certification gate enforced.
