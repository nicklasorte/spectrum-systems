# System Source Index (Authoritative)

## Authority
- **Path:** `docs/architecture/system_source_index.md`
- **Version:** `2026-03-30`
- **Role:** Bounded architecture source authority used to ground roadmap/review/progression artifacts.

## Required Source Set
Use these source documents as bounded grounding authorities (strategy remains higher authority):

| Source ID | Path | Enforcement purpose |
| --- | --- | --- |
| SRE-MAPPING | `docs/source_structured/mapping_google_sre_reliability_principles_to_spectrum_systems.json` | Reliability/SLO/error-budget grounding for control-loop readiness and operational risk checks |
| AI-WORKFLOW-EVAL | `docs/source_structured/production_ready_best_practices_for_integrating_ai_models_into_automated_engineering_workflows.json` | Eval-driven workflow grounding, anti-hallucination and validation discipline |
| SBGE-DESIGN | `docs/source_structured/spectrum_systems_build_governance_engine_sbge_design.json` | Governance-engine architecture boundary and enforcement placement |
| AGENT-EVAL-INTEGRATION | `docs/source_structured/agent_eval_integration_design_spectrum_systems.json` | Agent/eval separation and integration grounding |
| AI-ADAPTER-ABSTRACTION | `docs/source_structured/spectrum_systems_ai_integration_governed_api_adapter_design.json` | Model adapter/replaceability boundary and model coupling prevention |
| GOV-10-DONE-CERT | `docs/source_structured/spectrum_systems_done_certification_gate_gov10_design.json` | Done certification and progression gate requirements |

## Consumption Rules
1. Roadmap/review/progression artifacts must cite strategy + at least one relevant source from this index.
2. Cited source path must exist at validation time.
3. Artifact must include enforcement purpose for each cited source.
4. Missing or empty source list is a fail-closed condition for governed seams.
5. Duplicate or conflicting authority declarations are drift and must be reported.
