# PLAN — CDX-01 Next-Phase Full Roadmap Build

## Prompt type
`BUILD`

## Intent
Implement a repo-native, fail-closed hardening slice spanning registry expansion, contract additions, runtime validators, conformance checks, regression tests, and review artifacts for NXT-01..NXT-31.

## Step mapping
| Step | Owner system(s) | Files/seams to touch | Artifacts/schemas | Tests | Fail-closed addition | Primary risk |
|---|---|---|---|---|---|---|
| NXT-01 | CON + PRG | `docs/architecture/system_registry.md`, `contracts/examples/system_registry_artifact.json`, `scripts/validate_system_registry_boundaries.py` | registry entries + ownership markers | `tests/test_system_registry_boundary_enforcement.py` | missing/new owner markers block | ownership marker collisions |
| NXT-02 | CON | `contracts/schemas/*.schema.json` (next-phase contracts), `contracts/standards-manifest.json` | strict schemas for next-phase artifacts | `tests/test_next_phase_contracts.py` | schema validation blocks malformed artifacts | schema/example drift |
| NXT-03..NXT-07 | TRN/NRM/CTX/ABS/EVD | `spectrum_systems/modules/runtime/next_phase_governance.py` | translation, normalization, context preflight, abstention/evidence outputs | `tests/test_next_phase_governance.py` | simulated evidence quarantine + context insufficiency abstention | over-broad gating false positives |
| NXT-08..NXT-18 | EVL/DAT/TST/JDG/SEC/CAP/SLO/REP/OBS/LIN/CRS | `spectrum_systems/modules/runtime/next_phase_governance.py` + schema layer | eval/dataset/judgment/control/replay-related records and promotion lock checks | `tests/test_next_phase_governance.py` | promotion lock requires evidence/context/replay/consistency | incomplete legacy coverage |
| NXT-19..NXT-24 | HND/CRS/RSK/MIG/RET/SUP/QRY | same runtime module + schemas | handoff validation, consistency report, risk/migration/retire/supersession/query manifests | `tests/test_next_phase_governance.py` | semantically incomplete handoff blocks | semantic completeness heuristics |
| NXT-25..NXT-26 | PRG + SEC + CON | `docs/reviews/CDX-01_redteam_round_1.md`, tests/validators updates | red-team findings + fixes mapped to tests | `tests/test_next_phase_governance.py` | exploit classes converted to blocking reasons | finding-to-test mapping gaps |
| NXT-27..NXT-28 | ENT/SYN/QRY | runtime module + docs | trust posture snapshot + synthesized signal | `tests/test_next_phase_governance.py` | trust freeze trigger produced on low confidence | signal calibration drift |
| NXT-29..NXT-30 | PRG + SEC + CON | `docs/reviews/CDX-01_redteam_round_2.md`, tests/validators | second adversarial pass + regression hardening | `tests/test_next_phase_governance.py` | migration/handoff/replay budget blockers | latent cross-artifact edge cases |
| NXT-31 | CDE + SEL + CON | runtime module + review artifact | final trust-envelope lock + reason codes | `tests/test_next_phase_governance.py` | no-promotion path without mandatory envelope | integration coverage gaps |

## Risk and regression focus
- Registry parser currently ignores `consumes`/`produces`; updated parsing can regress existing tests.
- Standards manifest changes can drift from schema/example entries.
- Promotion-lock hardening may affect existing implicit assumptions in legacy paths; this slice keeps wiring additive and deterministic.

## Explicit non-ready handling
If a full seam cannot be safely wired to legacy runtime in this slice, add machine-readable blocking reasons and mark final verdict `NOT READY` in review artifact.
