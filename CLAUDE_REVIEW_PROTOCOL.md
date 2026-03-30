# Claude Review Protocol

Canonical protocol for Claude-led architecture and governance reviews across the Spectrum Systems ecosystem. Reviews must behave like a design review board: evaluate evidence, identify risks, and produce structured findings without directly modifying the architecture under review.

## Principles
- Evidence-driven and repeatable; subjective commentary is insufficient.
- Draws on reliability engineering (SLOs, error budgets, postmortems), software delivery performance metrics, secure software development practices, platform engineering governance, and observability/operational telemetry.
- Treat unsubstantiated architecture claims as weak signals until supported by operational proof.
- Respect repo separation: governance artifacts live in `spectrum-systems`; implementation happens downstream.

## Scope and evaluation lenses
- **Architecture:** repository structure, engine interface compliance, artifact contract compliance, and alignment to the system registry.
- **Maturity:** claimed maturity level, supporting evidence, and promotion readiness per the maturity model.
- **Operational Evidence (critical):** presence and freshness of run manifests, evaluation artifacts, contract validation outputs, registry consistency, and pipeline reproducibility proofs.
- **Roadmap alignment:** current roadmap step cluster, dependencies from `ecosystem/roadmap-tracker.json`, and whether blockers are architectural, roadmap, or maturity-related.
- **Governance:** compliance with spectrum-systems standards, required governance files present, schema/contract validation status.
- **Risk:** architectural drift, system complexity risks, governance gaps, reliability risks.
- Architecture or maturity claims without operational evidence remain provisional.

## Horizon evaluation
- Reference `docs/architecture-horizons.md` and determine whether the scope is balanced across horizons:
  - **H1**: executable functionality present.
  - **H2**: architecture contracts defined.
  - **H3**: long-term direction documented.
- If one horizon dominates or is missing, flag the imbalance and tie findings to evidence gaps.

## Inflection point detection
- Reference `docs/platform-inflection-points.md` and evaluate whether the ecosystem has crossed major platform inflection points.
- Report achieved inflection points, the next expected inflection, and any architecture risks blocking the next point.
- Example output:
  - Inflection Points Achieved: First Executable Artifact
  - Next Expected Inflection: First Closed Loop
  - Architecture Risks: evaluation harness not yet implemented

## Required review outputs
Every Claude review produces two artifacts:
1. **Human-readable report** stored under `docs/reviews/` using `docs/design-review-standard.md` structure. Include metadata (date, repo, commit or document version, inputs consulted) and stable finding IDs.
2. **Action tracker** under `docs/review-actions/` derived via `docs/review-to-action-standard.md` and `docs/review-actions/action-tracker-template.md`, capturing recommendations, owners/placeholders, priorities, evidence links, and follow-up triggers. Update the review registry after both artifacts exist.

## Evidence expectations
- Reliability: SLO definitions, error budgets, incident/postmortem summaries, availability/latency/backlog telemetry.
- Delivery performance: lead time, deployment frequency, change failure rate, mean/median restore, and trend evidence.
- Secure development: threat model references, SBOM or dependency risk outputs, vulnerability management evidence.
- Platform governance: interface adherence, contract/schema validation outputs, and alignment to standards manifests.
- Observability: metrics/logs/traces coverage, alert quality, and linkage to evaluation or run manifests.

## Run Evidence Correlation
- Verify that `run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, and `provenance.json` all exist for the reviewed scope.
- Confirm each artifact contains an identical `run_id`; any mismatch or omission is a finding (`category: operational_evidence`, `severity: high`).
- Block maturity promotion if evidence bundles cannot be correlated by `run_id`.

## Roadmap context
- Reviews may reference `ecosystem/roadmap-tracker.json` to understand the active step cluster, upstream dependencies, and blocking risks.
- Distinguish blockers explicitly:
  - **Architecture blockers:** missing or flawed contracts, schemas, or interfaces.
  - **Roadmap blockers:** prerequisite steps or sequencing gaps preventing progress.
  - **Maturity blockers:** absent evidence against the maturity model or playbook criteria.
- Call out maturity implications of unfinished roadmap items when assessing readiness or promotion claims.

## Dependency graph checks
- Inspect `ecosystem/dependency-graph.json` (and summary/visualization outputs) for completeness and freshness; call out missing systems, artifacts, or contracts.
- Identify hidden or unmodeled dependencies, contract/artifact coupling risks, and any architecture areas that are no longer legible from the graph.
- Explicitly comment on whether loop participation and cross-loop orchestration/advisory roles remain clear in the graph before approving architectural changes.

## ADR alignment
- Reference relevant ADRs when evaluating architecture changes and ensure findings cite the governing decision.
- If a proposal conflicts with an ADR, flag the conflict and recommend either updating the ADR (with a new design review) or reconsidering the change until governance is aligned.

## Review method
1. Ingest supplied artifacts and confirm scope; reject scopes lacking run manifests or registry alignment if evidence cannot be evaluated.
2. Evaluate each scope lens (architecture, maturity, operational evidence, governance, risk) against the expectations above.
3. Classify findings with severity and map them to required evidence; flag unverifiable claims as weak.
4. Populate the human-readable report (Section order from `docs/design-review-standard.md`) and extract actions into the tracker with acceptance criteria and evidence placeholders (`docs/review-evidence-standard.md`).
5. Record follow-up triggers and promotion gates in the tracker and registry; ensure reproducibility (pipelines/runbooks are executable from provided manifests).

## Strategy + Source Enforcement Checks (mandatory)
- Verify reviewed artifacts include `strategy_ref` pointing to `docs/architecture/system_strategy.md`; missing reference is a **high-severity governance finding**.
- Verify at least one bounded source authority from `docs/architecture/system_source_index.md` is cited with enforcement purpose; otherwise mark **NO_GO** for governance readiness.
- Explicitly test for: invariant violation, control bypass risk, missing eval, missing trace, missing certification, governance drift, and duplicate governance surface creation.
- Reviews must emit reusable yes/no checks (not prose-only advice) for each governance control above.

## Progression Blocking Rule
- If strategy/source linkage is missing or unverifiable, progression recommendation must be `NO_GO` until corrected.
