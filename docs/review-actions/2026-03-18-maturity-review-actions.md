# Action Tracker — Maturity Review 2026-03-18

**Source Review:** [2026-03-18-maturity-review.md](../reviews/2026-03-18-maturity-review.md)
**Review Date:** 2026-03-18
**Status:** Open

---

## Action Items

| ID | Priority | Description | Owner | Status |
| --- | --- | --- | --- | --- |
| MR-001 | Critical | Run `eval_runner.py` against `case_001` and `case_002`; commit output as initial `data/regression_baselines/v1.json` baseline. No new code required. | Copilot | Open |
| MR-002 | Critical | Wire `ObservabilityRecord` writes into `eval_runner.py` so every evaluation run persists a record to `data/observability/`. | Copilot | Open |
| MR-003 | Critical | Run the AU → AV → AW0 pipeline against the 24 existing error classification records in `data/error_classifications/`. Commit real validated cluster files into `data/validated_clusters/` (replacing `.gitkeep` files). | Copilot | Open |
| MR-004 | Critical | Run AW1 (remediation mapping) against the real validated clusters produced by MR-003. Replace seeded demo plans in `data/remediation_plans/` with plans derived from real cluster data. | Copilot | Open |
| MR-005 | Critical | Materialize `data/simulation_results/` directory. Run AW2 simulation against at least one AW1-produced remediation plan. Commit the simulation result. | Copilot | Open |
| MR-006 | High | Wire AO (human feedback) into the evaluation loop so that reviewers can submit feedback records. Collect at least one real `HumanFeedbackRecord` in `data/human_feedback/`. | Copilot | Open |
| MR-007 | High | Produce a complete evidence bundle (per `docs/evaluation-spine.md`) for at least one evaluation-remediation-simulation cycle. Bundle must include `run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, `provenance.json`, and `readiness_assessment.json`. | Copilot | Open |
| MR-008 | Medium | Replace all `.gitkeep` sentinel files in `data/validated_clusters/` with real validated cluster JSON after MR-003 is complete. Remove the 5 placeholder UUID-named entries. | Copilot | Open |
| MR-009 | Medium | Audit seeded demo data timestamp pattern in `data/error_classifications/` and `data/remediation_plans/`. Add a `data_provenance` field or README note in each directory distinguishing fixture data from operational data, per `docs/data-provenance-standard.md`. | Copilot | Open |
| MR-010 | Medium | Implement AW promotion pipeline: code that can apply an AW2-approved `promotion_recommendation` to a controlled artifact (schema version swap or prompt template update). This is the only net-new code blocking L15. | Copilot | Open |

---

## Follow-up Trigger

Re-run this maturity review after MR-001 through MR-005 are complete. Target: advance score from L7 to L9. Do not advance review status to Closed until at least one complete end-to-end AU→AV→AW0→AW1→AW2 cycle has produced committed operational artifacts.
