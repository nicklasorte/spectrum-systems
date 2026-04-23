# System Inventory Audit — SYS-REDUCE-01

## Prompt type
BUILD

## Scope and method
This audit enumerates 3-letter systems discovered in canonical registry surfaces and runtime executable surfaces, then classifies each as executable system role, merged capability, artifact family, review label, or placeholder.

Evidence sources inspected:
- `docs/architecture/system_registry.md` (canonical post-cleanup)
- `docs/architecture/system_registry_core.md`, `docs/architecture/system_registry_support.md`, `docs/architecture/system_registry_reserved.md`
- `spectrum_systems/modules/runtime/*.py`
- selected architecture/review documents referencing legacy acronyms

Runtime-prefix evidence command:
- `python - <<'PY' ...` extracting 3-letter filename prefixes from `spectrum_systems/modules/runtime`.

## Inventory classification

| System | Evidence (repo) | Actual roleship status | Class | Action | Rationale |
| --- | --- | --- | --- | --- | --- |
| AEX | runtime admission/execution files | Executable implementation present | Active system | keep | Explicit bounded execution intake boundary. |
| PQX | `pqx_*` runtime modules | Executable implementation present | Active system | keep | Primary execution engine and trace emitter. |
| EVL | eval registry/control/coverage modules | Executable implementation present | Active system | keep | Required eval gate and risk/comparison absorption role. |
| TPA | trust/policy governance modules | Executable implementation present | Active system | keep | Trust/policy adjudication boundary. |
| CDE | closure decision engine modules | Executable implementation present | Active system | keep | Closure/readiness control decision role. |
| SEL | enforcement runtime modules | Executable implementation present | Active system | keep | Fail-closed enforcement execution role. |
| REP | replay engine/governance modules | Executable implementation present | Active system | keep | Deterministic replay and replay gate system role. |
| LIN | lineage issuance/authenticity modules | Executable implementation present | Active system | keep | Promotion lineage completeness role. |
| OBS | observability metrics/trace modules | Executable implementation present | Active system | keep | Measurability and telemetry completeness role. |
| SLO | slo control/enforcement modules | Executable implementation present | Active system | keep | Error-budget and reliability control role. |
| CTX | `ctx.py`, context flow/normalizer | Executable implementation present | Active system | keep | Context admission, retrieval adaptation, normalization. |
| PRM | task/prompt registry runtime modules | Executable implementation present | Active system | keep | Prompt/task admissibility governance. |
| POL | policy registry/rollout modules | Executable implementation present | Active system | keep | Policy lifecycle and rollout governance. |
| TLC | top-level conductor/routing modules | Executable implementation present | Active system | keep | Orchestration and routing (distinct from execution). |
| RIL | interpretation/parsing modules | Executable implementation present | Active system | keep | Structured interpretation layer for control surfaces. |
| FRE | failure diagnosis/repair modules | Executable implementation present | Active system | keep | Failure diagnosis and repair planning system role. |
| RAX | `rax_model.py`, `rax_eval_runner.py` | Executable implementation present | Active system | keep | Implemented bounded runtime candidate-signal layer. |
| RSM | drift/reconciliation modules | Executable implementation present | Active system | keep | Desired-vs-actual reconciliation state roleship. |
| CAP | qos/reliability ops modules | Supporting with executable control | Active system | keep | Capacity/cost budget governance role remains distinct. |
| SEC | permission/identity/downstream guard modules | Executable implementation present | Active system | keep | Security boundary governance and control integration. |
| JDX | judgment engine and policy-candidate modules | Executable implementation present | Active system | keep | Judgment artifact semantics and application. |
| JSX | `jsx.py`, judgment lifecycle modules | Executable implementation present | Active system | keep | Supersession/retirement/active-set lifecycle roleship. |
| PRA | promotion readiness checkpoint modules | Executable implementation present | Active system | keep | Promotion-readiness gate system role. |
| GOV | governance chain/continuous governance modules | Executable implementation present | Active system | keep | Certification and governance gate system role. |
| MAP | projection/meta-governance modules | Executable implementation present | Active system | keep | Metadata/topology/system-map projection system role. |
| SUP | no dedicated runtime system role; overlaps JSX | No unique implementation surface | Legacy system | merge | Active-set and supersession absorbed by JSX. |
| RET | no dedicated runtime system role; overlaps JSX | No unique implementation surface | Legacy system | merge | Retirement lifecycle absorbed by JSX. |
| QRY | no distinct system role modules | No unique implementation surface | Legacy system | merge | Query integrity folded into CTX retrieve/admission governance. |
| NRM | normalizer support path only | No unique implementation surface | Legacy system | merge | Canonicalization under CTX admission flow. |
| TRN | transform support path only | No unique implementation surface | Legacy system | merge | Translation/transformation under CTX governance. |
| CMP | comparison artifacts in eval workflow | No unique implementation surface | Legacy system | merge | Comparison runs absorbed under EVL artifact families. |
| RSK | risk artifacts in eval workflow | No unique implementation surface | Legacy system | merge | Risk classification absorbed under EVL gating. |
| MCL | documentation-only memory concept | Non-executable | Artifact family | demote | Method-level support, no top-level system role boundary. |
| DCL | documentation-only doctrine concept | Non-executable | Artifact family | demote | Doctrine compilation is support documentation capability. |
| DEM | recommendation/economics review concept | Non-executable | Review label | demote | Advisory scoring without executable system role rights. |
| ABX/DBB/LCE/SAL/SAS/SHA/SIV | registry/docs placeholder references | Placeholder-only | Placeholder | remove(active)/future | Preserve as future appendix only, not active roles. |

## Additional observed 3-letter runtime prefixes (non-active authorities)

Observed in runtime filenames and retained as supporting modules, method labels, or legacy seams: `AIL`, `CAL`, `CAX`, `CHX`, `CVX`, `DAG`, `DEP`, `DEX`, `DRT`, `DRX`, `ENT`, `EXT`, `HIX`, `HND`, `HNX`, `NSX`, `PRG`, `PRX`, `QOS`, `RCA`, `RDX`, `REL`, `RQX`, `RUX`, `SCH`, `SIM`, `TLX`, `XPL`, and others with low-count prefix evidence.

These are **not** elevated to active top-level authorities in the canonical registry because they fail one or more system role tests:
1. no unique failure prevented,
2. no unique measurable signal improvement,
3. no unique canonical artifact roleship distinct from active authorities.

## Duplicate acronym corrections validated
- `DEP` duplicate definitions removed from active canonical roleship.
- `JDX` duplicate definitions collapsed into one active role with explicit boundary vs JSX.

## Result
The canonical registry now expresses a materially smaller active system role set aligned to executable roleship, with merged/demoted/future states explicit and auditable.
