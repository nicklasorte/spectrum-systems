# System Registry — Core

This document defines only:
- core runtime authorities
- support planes

## Core runtime authorities

### AEX
- **acronym:** `AEX`
- **full_name:** Admission and Execution Exchange
- **role:** Admission boundary for execution requests.
- **owns:** admission decision, request normalization, intake artifact emission.
- **consumes:** execution request artifacts, request metadata.
- **produces:** admission record, normalized execution request, rejection record.
- **must_not_do:** execute work, evaluate outputs, make policy admissibility decisions, issue final decisions, enforce runtime actions.

### PQX
- **acronym:** `PQX`
- **full_name:** Prompt Queue Execution
- **role:** Bounded execution authority.
- **owns:** governed execution, execution state transitions, execution trace emission.
- **consumes:** admitted execution requests, scoped execution artifacts.
- **produces:** execution result artifacts, execution traces.
- **must_not_do:** admit requests, perform required evaluations, decide policy admissibility, issue final decisions, enforce gates.

### EVL
- **acronym:** `EVL`
- **full_name:** Evaluation Authority
- **role:** Required evaluation authority and required evaluation gate.
- **owns:** required eval registry, eval execution requirements, eval pass/fail/indeterminate outcomes.
- **consumes:** execution outputs, eval datasets/tests, eval policy requirements.
- **produces:** required eval results, eval coverage records, indeterminate/block records.
- **must_not_do:** override policy admissibility, issue final closure/promotion decisions, bypass missing evidence.

### TPA
- **acronym:** `TPA`
- **full_name:** Trust and Policy Admissibility
- **role:** Policy admissibility gate.
- **owns:** policy admissibility decisioning, trust boundary checks, policy result artifacts.
- **consumes:** admitted requests, eval results, evidence/risk inputs.
- **produces:** policy admissibility result, deny/block artifacts.
- **must_not_do:** execute work, issue final closure/promotion decisions, suppress policy failures.

### CDE
- **acronym:** `CDE`
- **full_name:** Closure Decision Engine
- **role:** Final decision authority for closure/readiness/promotion outcomes.
- **owns:** closure decisions, promotion-readiness decisions, decision artifacts.
- **consumes:** required evidence bundle from PQX/EVL/TPA/REP/LIN/OBS and support planes.
- **produces:** closure decision artifact, promotion readiness decision artifact.
- **must_not_do:** execute work, enforce actions directly, bypass required evidence.

### SEL
- **acronym:** `SEL`
- **full_name:** Safety Enforcement Layer
- **role:** Runtime enforcement authority.
- **owns:** block/freeze/allow enforcement actions, fail-closed actioning.
- **consumes:** CDE decisions, gate outcomes, policy and control thresholds.
- **produces:** enforcement action artifacts, blocked/frozen progression states.
- **must_not_do:** invent decision authority, issue policy decisions, ignore authoritative gate failures.

### REP
- **acronym:** `REP`
- **full_name:** Replay Integrity
- **role:** Replay gate overlay.
- **owns:** replay requirement checks, replay match/mismatch outcomes.
- **consumes:** execution artifacts, replay artifacts.
- **produces:** replay gate result, replay mismatch failure artifact.
- **must_not_do:** waive replay requirements when replay is mandatory.

### LIN
- **acronym:** `LIN`
- **full_name:** Lineage Integrity
- **role:** Lineage gate overlay.
- **owns:** lineage completeness checks and lineage blocking outcomes.
- **consumes:** artifact lineage records, provenance links.
- **produces:** lineage gate result, lineage incompleteness failure artifact.
- **must_not_do:** permit progression with broken lineage.

### OBS
- **acronym:** `OBS`
- **full_name:** Observability Completeness
- **role:** Observability/trace completeness gate overlay.
- **owns:** required trace/telemetry completeness checks.
- **consumes:** runtime traces, required observability contracts.
- **produces:** observability gate result, trace incompleteness failure artifact.
- **must_not_do:** permit progression when required observability evidence is missing.

## Support planes (non-spine)

### TLC
- **acronym:** `TLC`
- **full_name:** Top-Level Conductor
- **role:** Orchestration and routing across runtime components.
- **owns:** execution ordering, routing plans, orchestration records.
- **consumes:** admitted work and runtime status artifacts.
- **produces:** orchestration artifacts, routing decisions.
- **must_not_do:** override core authority outcomes.

### FRE
- **acronym:** `FRE`
- **full_name:** Failure and Repair Engine
- **role:** Failure diagnosis and bounded repair planning.
- **owns:** failure classification, repair plan artifacts.
- **consumes:** failure evidence, eval failures, enforcement failures.
- **produces:** diagnosis artifacts, bounded repair candidates.
- **must_not_do:** grant promotion or bypass failed gates.

### RIL
- **acronym:** `RIL`
- **full_name:** Review Interpretation Layer
- **role:** Interprets review outputs into governed integration artifacts.
- **owns:** interpretation contracts, review integration outputs.
- **consumes:** review artifacts and evidence bundles.
- **produces:** normalized interpretation artifacts.
- **must_not_do:** become final decision or enforcement authority.

### PRG
- **acronym:** `PRG`
- **full_name:** Program Governance
- **role:** Program-level sequencing and governance constraints.
- **owns:** governance thresholds, sequencing constraints, program-level controls.
- **consumes:** roadmap, budget, drift, and governance telemetry artifacts.
- **produces:** governance constraint artifacts, threshold states.
- **must_not_do:** bypass runtime spine authorities.
