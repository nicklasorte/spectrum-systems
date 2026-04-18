# System Registry — Support Families

This document is an additive explanatory view. Canonical compatibility and enforcement source remains `docs/architecture/system_registry.md` until dedicated tooling migration is completed.

This document groups non-core surfaces as support families.

These families are important, but they are not peer canonical runtime authorities.

## 1) Judgment subsystem family

Purpose: govern judgment artifact lifecycle and interpretation support.

Includes grouped surfaces such as:
- JDX, JSX, SUP, RET, RUX, PRX, DEX, XPL

Rules:
- Must produce explicit artifact records.
- Must not issue final closure/promotion decisions.
- Must not bypass EVL/TPA/CDE/SEL gates.

## 2) Contract and integrity subsystem family

Purpose: maintain contract validity, schema integrity, migration safety, and cross-artifact consistency.

Includes grouped surfaces such as:
- CON, SCH, MIG, CRS, DAG, DEP

Rules:
- Contract/schema failure is blocking input to runtime gates.
- Integrity signals feed EVL/TPA/CDE/SEL; they do not replace them.

## 3) Intelligence and drift subsystem family

Purpose: provide non-authoritative analysis, drift detection, and recommendation signals.

Includes grouped surfaces such as:
- DRT, DRX, ENT, AIL, QRY, SYN, RSM, DEM, MCL, BRM, DCL, XRL

Rules:
- Outputs are support evidence and governance inputs.
- Drift threshold breach can trigger FREEZE via authoritative enforcement.
- Family members are not independent promotion authorities.

## 4) Dataset and test governance family

Purpose: govern evaluation dataset/test quality as EVL support.

Includes grouped surfaces such as:
- DAT, TST

Rules:
- Dataset/test integrity feeds required eval outcomes.
- Missing or stale required eval assets can trigger BLOCK.
- Family members are subordinate to EVL authority.

## 5) Human override and audit family

Purpose: governed human override/correction and audit traceability.

Includes grouped surfaces such as:
- HIT, HIX (unified as one family)

Rules:
- Human intervention must be explicit, auditable, and artifact-backed.
- Human signals do not bypass fail-closed runtime gates.

## 6) Routing, prompt, and context support family

Purpose: support admissibility and evaluation preparation without independent final authority.

Includes grouped surfaces such as:
- CTX, PRM, ROU

Rules:
- CTX is admission/policy/eval support, not peer runtime authority.
- PRM and ROU are policy admissibility governance support unless elevated by canonical proof.
- Missing required routing/prompt/context artifacts can block via AEX/TPA/EVL contracts.

## Policy and evidence input grouping

The following are treated as policy/evidence inputs, not peer runtime authorities:
- RSK, EVD

They must feed admissibility and decision evidence bundles.
