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
- **Governance:** compliance with spectrum-systems standards, required governance files present, schema/contract validation status.
- **Risk:** architectural drift, system complexity risks, governance gaps, reliability risks.
- Architecture or maturity claims without operational evidence remain provisional.

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

## Dependency graph checks
- Inspect `ecosystem/dependency-graph.json` (and summary/visualization outputs) for completeness and freshness; call out missing systems, artifacts, or contracts.
- Identify hidden or unmodeled dependencies, contract/artifact coupling risks, and any architecture areas that are no longer legible from the graph.
- Explicitly comment on whether loop participation and cross-loop orchestration/advisory roles remain clear in the graph before approving architectural changes.

## Review method
1. Ingest supplied artifacts and confirm scope; reject scopes lacking run manifests or registry alignment if evidence cannot be evaluated.
2. Evaluate each scope lens (architecture, maturity, operational evidence, governance, risk) against the expectations above.
3. Classify findings with severity and map them to required evidence; flag unverifiable claims as weak.
4. Populate the human-readable report (Section order from `docs/design-review-standard.md`) and extract actions into the tracker with acceptance criteria and evidence placeholders (`docs/review-evidence-standard.md`).
5. Record follow-up triggers and promotion gates in the tracker and registry; ensure reproducibility (pipelines/runbooks are executable from provided manifests).
