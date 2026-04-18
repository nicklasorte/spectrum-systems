# Runtime Spine

## Purpose

Define the minimal canonical runtime control architecture and hard enforcement semantics.

## Authoritative runtime chain

The only authoritative runtime chain is:

**AEX → PQX → EVL → TPA → CDE → SEL**

Mandatory gate overlays:

- **REP** (replay)
- **LIN** (lineage)
- **OBS** (observability)

No other system is a peer runtime authority unless promoted through canonical system-addition rules.

## Authoritative vs supportive

### Authoritative
- AEX, PQX, EVL, TPA, CDE, SEL, REP, LIN, OBS

### Supportive (non-peer)
- TLC, FRE, RIL, PRG
- grouped support families in `system_registry_support.md`

Supportive systems can provide artifacts and recommendations but cannot override authoritative gate outcomes.

## Hard gate semantics

### BLOCK when
- required artifact missing
- required eval missing
- schema invalid
- lineage incomplete
- required trace/observability incomplete
- policy result missing
- replay result missing where required
- certification evidence missing where required

### FREEZE when
- replay mismatch
- required eval outcome is indeterminate
- drift threshold exceeded
- budget burn threshold exhausted
- governance threshold exhausted

### ALLOW only when
- required artifacts exist
- required evals pass
- policy admissibility passes
- lineage is complete
- observability completeness passes
- replay passes where required
- certification evidence is present where required

## Promotion semantics

Promotion is allowed only when CDE issues a promotion-readiness decision backed by complete required evidence and SEL enforces ALLOW.

No promotion is valid if any mandatory gate is BLOCK or FREEZE.

## Bypass definition

A bypass is any downstream progression that occurs without one or more required authoritative outcomes or without required evidence artifacts.

Bypasses include:
- skipping required eval/policy/replay/lineage/observability checks
- using advisory analysis as if it were authority
- proceeding on missing certification evidence
- using hidden or undocumented execution paths

Any detected bypass is a blocking defect.

## Blocking defect definition

A blocking defect is any condition that invalidates governed progression, including:
- authority ambiguity or ownership duplication
- missing or invalid required contracts/schemas
- missing required evidence artifacts
- violations of no-hidden-execution rules
- policy/eval/replay/lineage/observability gate failures
- attempted promotion without certification evidence

## Canonical system-addition rule

No new canonical system may be added unless it has:
1. one unique authority
2. one clear blocking failure it prevents
3. one enforced contract surface
4. one tested fail-closed boundary
5. explicit proof it should not be a subsystem group or artifact family
