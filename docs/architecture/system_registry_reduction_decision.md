# System Registry Reduction Decision — SYS-REDUCE-01

## Prompt type
BUILD

## Decision summary
The previous 3-letter registry was over-expanded, duplicative, and drifted from executable ownership. This decision reduces active top-level systems to authorities with real runtime control surfaces and explicit justification fields (purpose, prevented failure, improved signal, owned artifacts, executable paths, status).

## Why reduction was required
1. Duplicate acronym definitions (`DEP`, `JDX`) corrupted canonical trust.
2. Placeholder systems were mixed with executable owners, creating authority ambiguity.
3. Weak conceptual seams were treated as top-level systems, obscuring the execution → eval → control → enforcement loop.
4. Registry-to-code drift made ownership unverifiable for new contributors.

## What changed

### Active systems retained
AEX, PQX, EVL, TPA, CDE, SEL, REP, LIN, OBS, SLO, CTX, PRM, POL, TLC, RIL, FRE, RAX, RSM, CAP, SEC, JDX, JSX, PRA, GOV, MAP.

### Merged systems
- SUP + RET → JSX
- QRY + NRM + TRN → CTX
- CMP + RSK → EVL

### Demoted systems
- MCL, DCL, DEM moved to artifact-family/review-label status.

### Future-only placeholders
- ABX, DBB, LCE, SAL, SAS, SHA, SIV moved to explicit future/placeholder section.

## Why fewer systems strengthen the loop
- Reduced active set makes control handoff clear and auditable.
- Removes ambiguous pseudo-authorities that diluted ownership boundaries.
- Improves onboarding: engineers can map failures directly to owning authority.
- Prevents policy/control leakage across conceptual seams.

## Debuggability and trust improvements
- Every active system now links to executable code paths.
- Every active system declares the specific failure it prevents and signal it improves.
- Registry validation script detects duplicate acronyms, metadata gaps, missing code paths, placeholder contradictions, and runtime drift.

## Sprawl prevention controls
The new `scripts/validate_system_registry.py` enforces:
1. no duplicate active acronyms,
2. required justification metadata on every active system,
3. existence checks for every declared primary code path,
4. contradiction checks (future placeholder with live runtime prefix evidence),
5. runtime drift checks for significant unmanaged 3-letter runtime prefixes.

This makes casual addition of new top-level 3-letter systems fail local validation/CI unless justification and executable ownership are explicit.
