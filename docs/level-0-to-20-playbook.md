# Level 0-20 Maturity Playbook

## Purpose
This playbook guides the spectrum ecosystem from concept to strategic operating system. Progression is evaluated through evidence, metrics, and architectural capabilities-not intuition or aspiration. Each level requires observable proofs that the new capability exists and is durable.

The roadmap tracker (`ecosystem/roadmap-tracker.json`) is the execution companion to this playbook: roadmap steps should advance maturity levels with evidence recorded in both the tracker and the maturity model.

## External best-practice anchors
The ecosystem draws on proven practices:
- **Software delivery performance metrics**: shorten lead time, improve deployment frequency, reduce change failure, and recover quickly.
- **Site reliability engineering (SLOs and error budgets)**: define reliability targets, measure error-budget burn, and use them to govern change velocity.
- **Secure software development practices**: shift-left controls, dependency hygiene, and governed release processes.
- **Supply-chain provenance and artifact trust**: attestations, signatures, and traceable lineage for inputs/outputs.
- **Observability**: traces, metrics, logs, and run manifests that capture execution context and evaluation results.
- **Platform engineering**: consistent engine interfaces, paved paths, and self-service pipelines that bake in governance.

## Maturity dimensions
- **Value Loop** - Measures how well inputs become governed outputs that deliver user value. Higher maturity couples inputs to outcomes with closed feedback loops and evaluation artifacts.
- **Contracts and Architecture** - Assesses interface clarity and composability. At higher maturity, contracts are versioned, diff-aware, and enforced in CI across repos.
- **Engine Interface Consistency** - Tracks adherence to common engine patterns. Good maturity means engines expose uniform inputs/outputs, control signals, and provenance hooks.
- **Testing and Evaluation** - Captures fixture quality, harness coverage, and evaluation depth. Mature systems run deterministic tests per contract and emit evaluation artifacts by default.
- **Reliability and SLOs** - Measures whether services declare and meet SLOs with error-budget governance. Higher levels connect release gates to SLO health.
- **Observability** - Reviews telemetry completeness. Mature systems emit traces/metrics/logs plus run manifests for every execution, enabling fast diagnosis.
- **Security and Provenance** - Ensures supply-chain integrity, attestation, and artifact lineage. Higher levels sign artifacts, enforce SBOMs, and block untrusted inputs.
- **Governance and Control Plane** - Examines how registries, manifests, and policies are applied. Good maturity keeps contracts, schemas, and registries synchronized through automation.
- **Learning and Intelligence** - Measures ability to recommend, adapt, and learn across runs. At higher maturity, recommendations are evidence-backed, precision-tracked, and feed cross-study learning.

## Levels 0-20
| Level | Name | Capability Introduced | Promotion Test | Common Failure Mode |
| --- | --- | --- | --- | --- |
| 0 | Idea Vapor | Problem acknowledged but not captured. | Problem statement and desired outcomes are documented in a durable artifact. | Discussions dissipate with no persisted intent. |
| 1 | Organized Concept | Framed concept with initial scope. | Architecture sketch, stakeholders, and risks recorded in repo. | Scope creep without stable framing. |
| 2 | Blueprinted System | Repository, contracts, and schemas scaffolded. | Repo scaffold exists with initial contracts linked to standards manifest. | Contracts drift from vision or remain informal. |
| 3 | Governed Blueprint | Standards, roles, and boundaries enforced. | Standards manifest and governance docs approved; interfaces aligned to schemas. | Governance exists on paper only; no enforcement. |
| 4 | First Executable Component | One governed engine processes real inputs. | Single engine runs on real artifact and emits governed output with provenance. | Demo-only execution with synthetic inputs. |
| 5 | End-to-End MVP Loop | Closed-loop workflow proven. | One governed workflow runs end-to-end on real artifacts with evaluation evidence. | Partial loop with missing evaluation or provenance. |
| 6 | Repeatable Experiment System | Fixtures and harnesses make runs reproducible. | Deterministic fixtures and CI harness run the workflow repeatably with stable outputs. | Flaky fixtures or nondeterministic runs. |
| 7 | Multi-Engine Workflow | Sequential orchestration across engines. | Multiple governed engines orchestrated with contract compatibility validated. | Interface mismatches causing manual glue code. |
| 8 | CI-Enforced System | Automated contract and policy enforcement. | CI blocks contract drift and policy violations across repos; manifests are validated. | Enforcement skipped or only advisory. |
| 9 | Cross-Repo Ecosystem | Dependency-aware coordination. | Ecosystem registry drives dependency checks and version alignment across repos. | Hidden dependencies and untracked breaking changes. |
| 10 | Platformized Workflow Engine | Pipelines as platform services. | Pipelines orchestrate multiple engines through governed interfaces with self-service paths. | One-off pipelines without reusable platform patterns. |
| 11 | Observable Platform | Full telemetry and run manifests. | >=95% of runs emit traces/metrics/logs and run manifests linked to artifacts. | Telemetry gaps prevent diagnosis or audit. |
| 12 | Risk-Aware Platform | Change impact and rollback ready. | Releases gated by risk analysis and rollback plans tied to error budgets. | Releases proceed without risk signals or rollback hooks. |
| 13 | Semi-Automated Governance | Automated policy and action surfacing. | Governance automation files issues or flags drift with evidence; reviewers act on surfaced gaps. | Alerts ignored or unactionable; governance debt grows. |
| 14 | Self-Remediating Platform | Automated fixes and migrations. | System auto-applies low-risk remediations or migrations with approval workflows. | Automated fixes create new drift or bypass review. |
| 15 | Institutional Memory System | Decisions and rationale preserved. | Decisions, context, and provenance are queryable and linked to artifacts and runs. | Decisions scattered across docs with no lineage. |
| 16 | Decision Intelligence Layer | Evidence-backed recommendations. | System produces recommendations with precision/recall tracked against outcomes. | Recommendations unvalidated or ignored by operators. |
| 17 | Cross-Study Learning System | Learning transfers across workflows. | Signals from one workflow improve another with measurable uplift. | Insights siloed; no cross-workflow uptake. |
| 18 | Predictive Program System | Forecasting of risk and outcomes. | Predictive models forecast failure/lead time with backtested accuracy bounds. | Forecasts untuned or untrusted; operators bypass them. |
| 19 | Adaptive Workflow System | Context-aware dynamic execution. | Pipelines adapt paths based on context, confidence, and policy while staying governed. | Dynamic paths break contracts or bypass governance. |
| 20 | Strategic Operating System | Evidence drives planning and prioritization. | System influences planning/prioritization with evidence-backed advisories adopted by leadership. | Advisory outputs ignored or misaligned with strategy. |

## Phase structure
- **Tooling (0-5)**: Frame the problem, establish contracts, and prove a governed end-to-end loop on real artifacts.
- **Platform (6-10)**: Make workflows repeatable, orchestrate multiple engines, and enforce contracts/policies via CI and platform pipelines.
- **Governance (11-15)**: Deliver observability, risk-aware change management, automated governance, and preserved institutional memory.
- **Intelligence (16-20)**: Layer decision intelligence, cross-workflow learning, predictive capabilities, adaptive execution, and strategic advisories.

## Platform inflection points by maturity
Platform inflection points (see `docs/platform-inflection-points.md`) indicate when structural shifts are expected.

| Inflection Point | Approximate Maturity |
| --- | --- |
| First Executable Artifact | Level 3-4 |
| First Closed Loop | Level 4-5 |
| First Pipeline | Level 6-7 |
| Platform Standardization | Level 8-10 |
| Observability Maturity | Level 10-12 |
| Institutional Memory | Level 12-15 |
| Intelligence Layer | Level 15-20 |

## Dependency awareness
- Cross-repo ecosystems must become dependency-legible before scaling; hidden edges block promotion beyond Level 7.
- Levels 8–10 expect a current `ecosystem/dependency-graph.json` as the authoritative map for contract alignment, loop participation, and artifact flows.
- Dependency graph freshness is a promotion enabler: CI should regenerate it and reviews should use it to assess blast radius and maturity readiness.

## Promotion criteria by phase
- **To Level 5**: At least one governed workflow runs end-to-end on real artifacts with evaluation evidence and provenance.
- **To Level 10**: Pipelines orchestrate multiple engines through governed interfaces with CI enforcement and dependency awareness.
- **To Level 15**: Runs, decisions, and provenance are durable, queryable, and reviewable; governance automation is active.
- **To Level 20**: The system influences prioritization and planning via evidence-backed advisories that are adopted and measured.

Levels above 5 require correlated run evidence: every governed execution must emit `run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, and `provenance.json` sharing the same `run_id`. Systems cannot claim maturity without traceable, correlated execution artifacts.

## Scoreboard / measures
Use these measures to assess maturity honestly; track them in the registry and reviews.
- **Delivery**: change lead time; deployment frequency; failed deployment recovery time; change failure percentage; deployment rework rate.
- **Reliability**: SLO attainment; error-budget burn; mean time to diagnose failures.
- **Observability**: percent of runs with run manifests; percent of runs with traces/metrics/logs or equivalent execution telemetry; percent of runs with evaluation artifacts.
- **Security / provenance**: percent of artifacts with provenance metadata; percent of governed outputs with contract version traceability; percent of engine runs with explicit input/output lineage.
- **Governance**: contract drift incidents; registry completeness; policy violations detected in CI; number of custom adapters required between engines.
- **Intelligence**: recommendation adoption rate; recommendation precision / false positive rate; recurrence rate of previously known failures.

## Current ecosystem placement (approximate)
- **spectrum-systems**: Level ~4 - governance/control-plane assets are defined; broader enforcement and telemetry still maturing.
- **spectrum-data-lake**: Level ~5 - governed storage patterns exist; end-to-end integration and observability to strengthen.
- **meeting-minutes-engine**: Level ~4-5 - first operational engine; needs hardened evaluation and loop completion evidence.
- **working-paper-review-engine**: Level ~5-6 - produces reviewer sets; cross-engine orchestration still early.
- **comment-resolution-engine**: Level ~5-6 - adjudication exists; requires stronger provenance and CI enforcement.
- **docx-comment-injection-engine**: Level ~5-6 - governed injection; needs tighter telemetry and interface reuse.
- **spectrum-pipeline-engine**: Level ~6-7 - orchestration planned/early; dependency awareness and CI enforcement pending.
- **spectrum-program-advisor**: Level ~8-9 - advisory concepts exist; evidence-backed adoption and precision tracking needed.
- **system-factory**: Level ~3-4 - scaffolds governed repos; maturity increases as generated projects embed CI enforcement by default.

## Immediate target
Immediate Target: Level 5. Near-term goal: a working loop from DOCX transcript → meeting-minutes-engine → governed minutes artifact → evaluation, with evidence that the loop is repeatable and governed.

## Architectural principles to sustain through Level 20
- Durable artifacts
- Explicit contracts
- Reproducible pipelines
- Traceable decisions
- Common engine operating model
- Evidence-backed reviews
