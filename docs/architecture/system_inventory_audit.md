# System Inventory Audit — SYS-REDUCE-01

## Prompt type
BUILD

## Scope and method
This audit enumerates 3-letter systems discovered in canonical registry surfaces and runtime executable surfaces, then classifies each as executable authority, merged capability, artifact family, review label, or placeholder.

Evidence sources inspected:
- `docs/architecture/system_registry.md` (canonical post-cleanup)
- `docs/architecture/system_registry_core.md`, `docs/architecture/system_registry_support.md`, `docs/architecture/system_registry_reserved.md`
- `spectrum_systems/modules/runtime/*.py`
- selected architecture/review documents referencing legacy acronyms

Runtime-prefix evidence command:
- `python - <<'PY' ...` extracting 3-letter filename prefixes from `spectrum_systems/modules/runtime`.

## Inventory classification

| System | Evidence (repo) | Actual ownership status | Class | Action | Rationale |
| --- | --- | --- | --- | --- | --- |
| AEX | runtime admission/execution files | Real executable owner | Authority | keep | Explicit bounded execution intake boundary. |
| PQX | `pqx_*` runtime modules | Real executable owner | Authority | keep | Primary execution engine and trace emitter. |
| EVL | eval registry/control/coverage modules | Real executable owner | Authority | keep | Required eval gate and risk/comparison absorption owner. |
| TPA | trust/policy governance modules | Real executable owner | Authority | keep | Trust/policy adjudication boundary. |
| CDE | closure decision engine modules | Real executable owner | Authority | keep | Closure/readiness control decision owner. |
| SEL | enforcement runtime modules | Real executable owner | Authority | keep | Fail-closed enforcement execution owner. |
| REP | replay engine/governance modules | Real executable owner | Authority | keep | Deterministic replay and replay gate authority. |
| LIN | lineage issuance/authenticity modules | Real executable owner | Authority | keep | Promotion lineage completeness owner. |
| OBS | observability metrics/trace modules | Real executable owner | Authority | keep | Measurability and telemetry completeness owner. |
| SLO | slo control/enforcement modules | Real executable owner | Authority | keep | Error-budget and reliability control owner. |
| CTX | `ctx.py`, context flow/normalizer | Real executable owner | Authority | keep | Context admission, retrieval adaptation, normalization. |
| PRM | task/prompt registry runtime modules | Real executable owner | Authority | keep | Prompt/task admissibility governance. |
| POL | policy registry/rollout modules | Real executable owner | Authority | keep | Policy lifecycle and rollout governance. |
| TLC | top-level conductor/routing modules | Real executable owner | Authority | keep | Orchestration and routing (distinct from execution). |
| RIL | interpretation/parsing modules | Real executable owner | Authority | keep | Structured interpretation layer for control surfaces. |
| FRE | failure diagnosis/repair modules | Real executable owner | Authority | keep | Failure diagnosis and repair planning authority. |
| RAX | `rax_model.py`, `rax_eval_runner.py` | Real executable owner | Authority | keep | Implemented bounded runtime candidate-signal layer. |
| RSM | drift/reconciliation modules | Real executable owner | Authority | keep | Desired-vs-actual reconciliation state ownership. |
| CAP | qos/reliability ops modules | Supporting with executable control | Authority | keep | Capacity/cost budget governance role remains distinct. |
| SEC | permission/identity/downstream guard modules | Real executable owner | Authority | keep | Security boundary governance and control integration. |
| JDX | judgment engine and policy-candidate modules | Real executable owner | Authority | keep | Judgment artifact semantics and application. |
| JSX | `jsx.py`, judgment lifecycle modules | Real executable owner | Authority | keep | Supersession/retirement/active-set lifecycle ownership. |
| PRA | promotion readiness checkpoint modules | Real executable owner | Authority | keep | Promotion-readiness gate authority. |
| GOV | governance chain/continuous governance modules | Real executable owner | Authority | keep | Certification and governance gate authority. |
| MAP | projection/meta-governance modules | Real executable owner | Authority | keep | Metadata/topology/system-map projection authority. |
| SUP | no dedicated runtime authority; overlaps JSX | No unique owner surface | Legacy system | merge | Active-set and supersession absorbed by JSX. |
| RET | no dedicated runtime authority; overlaps JSX | No unique owner surface | Legacy system | merge | Retirement lifecycle absorbed by JSX. |
| QRY | no distinct authority modules | No unique owner surface | Legacy system | merge | Query integrity folded into CTX retrieve/admission governance. |
| NRM | normalizer support path only | No unique owner surface | Legacy system | merge | Canonicalization under CTX admission flow. |
| TRN | transform support path only | No unique owner surface | Legacy system | merge | Translation/transformation under CTX governance. |
| CMP | comparison artifacts in eval workflow | No unique owner surface | Legacy system | merge | Comparison runs absorbed under EVL artifact families. |
| RSK | risk artifacts in eval workflow | No unique owner surface | Legacy system | merge | Risk classification absorbed under EVL gating. |
| MCL | documentation-only memory concept | Non-executable | Artifact family | demote | Method-level support, no top-level authority boundary. |
| DCL | documentation-only doctrine concept | Non-executable | Artifact family | demote | Doctrine compilation is support documentation capability. |
| DEM | recommendation/economics review concept | Non-executable | Review label | demote | Advisory scoring without executable authority rights. |
| ABX/DBB/LCE/SAL/SAS/SHA/SIV | registry/docs placeholder references | Placeholder-only | Placeholder | remove(active)/future | Preserve as future appendix only, not active owners. |

## Additional observed 3-letter runtime prefixes (non-active authorities)

Observed in runtime filenames and retained as supporting modules, method labels, or legacy seams: `AIL`, `CAL`, `CAX`, `CHX`, `CVX`, `DAG`, `DEP`, `DEX`, `DRT`, `DRX`, `ENT`, `EXT`, `HIX`, `HND`, `HNX`, `NSX`, `PRG`, `PRX`, `QOS`, `RCA`, `RDX`, `REL`, `RQX`, `RUX`, `SCH`, `SIM`, `TLX`, `XPL`, and others with low-count prefix evidence.

These are **not** elevated to active top-level authorities in the canonical registry because they fail one or more authority tests:
1. no unique failure prevented,
2. no unique measurable signal improvement,
3. no unique canonical artifact ownership distinct from active authorities.

## Duplicate acronym corrections validated
- `DEP` duplicate definitions removed from active canonical ownership.
- `JDX` duplicate definitions collapsed into one active owner with explicit boundary vs JSX.

## Result
The canonical registry now expresses a materially smaller active authority set aligned to executable ownership, with merged/demoted/future states explicit and auditable.
