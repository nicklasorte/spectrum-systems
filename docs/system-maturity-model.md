# System Maturity Model (Levels 0-20)

## Overview
The spectrum ecosystem advances through a Level 0-20 ladder from concept to strategic operating system. The canonical playbook, promotion tests, and measurement guidance live in `docs/level-0-to-20-playbook.md`; maturity tracking is recorded in `ecosystem/maturity-tracker.json` using `ecosystem/maturity-tracker.schema.json`.

## Maturity Levels Table (0-20)
| Level | Name | Capability Introduced | What It Means |
| --- | --- | --- | --- |
| Level 0 | Idea Vapor | Concept articulation | A problem area is recognized and discussed but not yet captured. |
| Level 1 | Organized Concept | Problem framing | Scope, stakeholders, and risks are written down. |
| Level 2 | Blueprinted System | Repository and contract scaffolding | Repositories, architecture docs, and initial contracts/schemas are defined. |
| Level 3 | Governed Blueprint | Standards and roles | Schemas, standards, and repository roles are formalized to guard boundaries. |
| Level 4 | First Executable Component | Real input processing | One governed engine runs on real input and produces governed output. |
| Level 5 | End-to-End MVP Loop | Closed-loop workflow | A single workflow executes end-to-end from input through governed output with evaluation evidence. |
| Level 6 | Repeatable Experiment System | Fixtures and evaluation harness | Deterministic fixtures and harnesses make runs repeatable. |
| Level 7 | Multi-Engine Workflow | Sequential orchestration | Multiple governed engines operate in sequence to deliver a combined outcome. |
| Level 8 | CI-Enforced System | Automated contract enforcement | CI validates contracts, schemas, and policies to prevent drift. |
| Level 9 | Cross-Repo Ecosystem | Dependency awareness | Systems understand upstream/downstream dependencies across repositories. |
| Level 10 | Platformized Workflow Engine | Pipeline orchestration | Pipelines coordinate engines as platform services rather than one-offs. |
| Level 11 | Observable Platform | Metrics and provenance | Metrics, logs, traces, and run manifests are captured for every execution. |
| Level 12 | Risk-Aware Platform | Impact detection | Changes trigger risk analysis and impact detection before rollout. |
| Level 13 | Semi-Automated Governance | Governance automation | Automated issue generation and policy checks support reviewers. |
| Level 14 | Self-Remediating Platform | Automated remediation | The platform proposes and submits fixes or migrations automatically. |
| Level 15 | Institutional Memory System | Decision preservation | Decisions, rationale, and context are preserved and discoverable. |
| Level 16 | Decision Intelligence Layer | Action recommendations | The system recommends actions and priorities based on observed signals. |
| Level 17 | Cross-Study Learning System | Transfer of insights | Insights from one workflow improve models and practices in others. |
| Level 18 | Predictive Program System | Forecasting | The platform predicts failures, delays, and quality risks before they occur. |
| Level 19 | Adaptive Workflow System | Context-aware adaptation | Pipelines adapt dynamically based on context, confidence, and constraints. |
| Level 20 | Strategic Operating System | Strategy alignment | The system supports organizational strategy execution with governed automation. |

## Phase Structure
- **Tooling (Levels 0-5)**: Establish the problem framing, governed scaffolds, and the first executable loop that proves the concept on real inputs.
- **Platform (Levels 6-10)**: Build repeatability, introduce fixtures and harnesses, and platformize workflows through orchestrated pipelines with CI enforcement.
- **Governance (Levels 11-15)**: Add observability, risk detection, semi-automated governance, and preserve institutional memory across artifacts.
- **Intelligence (Levels 16-20)**: Layer decision intelligence, cross-workflow learning, predictive capabilities, and adaptive pipelines aligned to strategy.

## Current Ecosystem Mapping
- **spectrum-systems**: Governance and contracts (Levels ~4-5).
- **spectrum-data-lake**: Artifact storage and lineage (Levels ~5-6).
- **meeting-minutes-engine**: First operational engine (Levels ~4-5; target 5 with end-to-end evidence).
- **working-paper-review-engine**: Review artifact generation (Levels ~5-6).
- **comment-resolution-engine**: Adjudication engine (Levels ~5-6).
- **docx-comment-injection-engine**: Document revision engine (Levels ~5-6).
- **spectrum-pipeline-engine**: Workflow orchestration (Levels ~6-7).
- **spectrum-program-advisor**: Advisory layer (Levels ~8-9).
- **system-factory**: Scaffolding factory (Levels ~3-4).

## Registry as Maturity Control Plane
The System Registry (`docs/system-registry.md` and `ecosystem/system-registry.json`) records where every system sits on the maturity ladder and which loop it primarily serves. The maturity tracker (`ecosystem/maturity-tracker.json`) captures evidence, blocking gaps, and next targets, and reviews apply the rubric in `docs/review-maturity-rubric.md` to govern promotion.

## Immediate Target: Level 5
The near-term milestone is a working loop that transforms a transcript into a minutes artifact through the meeting-minutes engine. Achieving this end-to-end path establishes the first operational workflow and proves governed execution on real inputs.

## Architectural Principles for Reaching Level 20
- **Durable artifacts**: Persist artifacts in stable, queryable forms that survive tooling changes.
- **Explicit contracts**: Define interfaces and schemas so components compose safely and consistently.
- **Reproducible pipelines**: Ensure runs can be replayed with fixtures and harnesses to isolate changes.
- **Traceable decisions**: Record rationale, lineage, and provenance so choices remain auditable across decades.
- **Common engine operating model**: Maintain consistent interfaces, control signals, and telemetry expectations.
- **Evidence-backed reviews**: Require proof for maturity claims and promotions.
