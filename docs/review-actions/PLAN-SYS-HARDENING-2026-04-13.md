# PLAN — SYS Hardening Full Stack (2026-04-13)

Primary prompt type: `BUILD`

## Intent
Serially harden the governed control spine and trust envelope without redefining ownership. Changes are fail-closed and repo-native across registry docs, runtime enforcement seams, contracts/schemas, validators, and tests.

## Step Mapping (SYS-001 .. SYS-034)

| Step | Owner system | Repo seams touched | Artifacts/schemas | Tests | Fail-closed expectation |
| --- | --- | --- | --- | --- | --- |
| SYS-001 Registry expansion | Registry authority surface | `docs/architecture/system_registry.md`, `docs/system-registry.md`, `contracts/examples/system_registry_artifact.json` | registry entries + interaction edges | registry boundary tests | Missing system definition blocks validation. |
| SYS-002 Registry-to-implementation conformance | SEL + governance validators | `scripts/validate_system_registry_boundaries.py`, `tests/test_system_registry_boundary_enforcement.py` | conformance checks | boundary enforcement tests | ownership bleed now exits non-zero. |
| SYS-003 AEX admission perimeter | AEX/TLC/PQX | `top_level_conductor.py`, `pqx_handoff_adapter.py` | admission lineage requirements | admission boundary tests | repo mutation without AEX lineage blocked. |
| SYS-004 TPA authority anchoring | TPA | `tpa_policy_authority.py`, conductor wiring | admissibility/scope artifact usage | targeted policy tests | non-TPA admissibility artifacts rejected. |
| SYS-005 TLC de-drift | TLC | `top_level_conductor.py` | TLC routing-only checks | orchestration seam tests | TLC interpretation/admission/closure duplication blocked. |
| SYS-006 PQX execution truthfulness | PQX | `pqx_execution_hardening.py`, `pqx_sequence_runner.py` | explicit execution mode fields | PQX hardening tests | simulation cannot be promoted. |
| SYS-007 Queue permission realism | PQX/SEL | queue integration + enforcement seams | permission decision artifact wiring | queue path tests | fabricated approvals rejected. |
| SYS-008 SEL boundary proof | SEL/PQX queue state machine | `queue_state_machine.py`, SEL validation path | deterministic boundary proof token | SEL/replay tests | self-asserted boundary claims rejected. |
| SYS-009 Legacy path quarantine | SEL/TLC | enforcement/orchestration modules | canonical enforcement selector | regression tests | legacy alternate semantics blocked. |
| SYS-010 RQX trace completeness | RQX | review queue integrations | strict trace continuity | review path tests | fallback trace ids forbidden. |
| SYS-011 RIL canonical interpretation | RIL | review parsing/integration adapters | interpretation artifact checks | RIL integration tests | downstream semantics without RIL blocked. |
| SYS-012 FRE authoritative repair planning | FRE | failure diagnosis + repair flow | diagnosis/recurrence/plan authority check | repair flow tests | non-FRE repair planning blocked. |
| SYS-013 CDE closure/readiness exclusivity | CDE | closure decision flow + conductor | closure authority tightening | readiness tests | non-CDE closure/readiness transitions blocked. |
| SYS-014 REP replay gating | REP + CDE/SEL | replay governance + promotion gates | replay-required promotion evidence | replay tests | replay failure freezes promotion. |
| SYS-015 CTX context bundle contract | CTX | new schema + context flow | context bundle schema (provenance/TTL/recipe/inclusion/manifest) | schema + context tests | malformed/incomplete context bundle blocked. |
| SYS-016 CTX preflight gates | CTX/EVL | context admission/preflight | freshness/provenance/coverage/conflict/trust gates | context preflight tests | required gate failure blocks execution. |
| SYS-017 LIN lineage completeness | LIN | lineage guard + promotion gate | full lineage requirement artifact | lineage tests | missing lineage blocks promotion. |
| SYS-018 OBS contract unification | OBS | observability modules + queue/runtime emitters | trace/span/correlation requirement checks | observability completeness tests | incomplete observability blocks readiness. |
| SYS-019 EVL required eval registry | EVL | eval control/runtime | required eval registry + version checks | eval gating tests | missing required eval blocks. |
| SYS-020 DAT eval dataset registry | DAT | eval registry tooling | dataset lineage/version records | dataset registry tests | unknown/unstamped datasets block required evals. |
| SYS-021 EVL slice coverage reporting | EVL | eval reporting | slice coverage artifact | eval coverage tests | blind-spot slices reported and block if required. |
| SYS-022 DRT drift signal system | DRT | drift detection + control integration | drift artifacts (input/outcome/route/override/contradiction) | drift tests | unresolved critical drift blocks control. |
| SYS-023 SLO error budget governance | SLO | slo enforcement/control | error-budget + burn-rate artifacts | slo enforcement tests | budget breach can freeze/block. |
| SYS-024 CAN canary/rollback | CAN | release canary runtime | staged rollout + rollback artifacts | canary tests | failed canary blocks promote and triggers rollback. |
| SYS-025 PRM prompt registry enforcement | PRM | prompt execution seams | prompt registry resolution artifacts | prompt registry tests | shadow prompts blocked. |
| SYS-026 ROU routing governance | ROU | TLC routing + observability | route candidate/selection/comparison artifacts | routing tests | route changes without eval+canary blocked. |
| SYS-027 JDG judgment artifacts | JDG | readiness/policy/escalation decisions | governed judgment artifact requirement | judgment tests | high-impact decisions without JDG artifact blocked. |
| SYS-028 POL policy lifecycle/conflicts | POL | policy registry/runtime | lifecycle states + conflict/precedence checks | policy regression tests | unresolved policy conflict blocks. |
| SYS-029 HIT override artifactization | HIT | human override flows | override/correction/learning artifacts | HIT tests | unaudited override blocked. |
| SYS-030 SEC guardrail-control integration | SEC | input/output/tool guardrail runtime | guardrail event artifacts wired to control | guardrail integration tests | indeterminate guardrail freezes execution. |
| SYS-031 CAP budget governance | CAP | capacity/cost/latency controls | governed budget artifacts | budget tests | severe budget breach blocks/freeze paths. |
| SYS-032 CON interface contracts | CON | contracts + validators | explicit inter-system interface contracts | contract tests | incompatible hidden coupling blocked. |
| SYS-033 ENT entropy loop | ENT | drift/exception mining + lint | entropy/backlog/correction artifacts | entropy tests | unresolved entropy debt marked not ready. |
| SYS-034 Final promotion lock | CDE+SEL control envelope | promotion gate + conductor/SEL | final promotion lock contract | end-to-end promotion tests | no promotion without lineage+eval+replay+cert+control decision. |

## Validation Plan
Minimum validation runset after changes:
- system registry boundary tests
- registry-to-implementation conformance checks
- targeted admission/policy tests
- targeted orchestration/execution seam tests
- targeted replay/promotion/readiness tests
- all newly added regression tests for hardened weaknesses

## Blocking Rule
Any partially implemented step must be converted into a blocking validator, failing test, or explicit NOT READY finding in the final review artifact.
