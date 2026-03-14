# Spectrum Pipeline Engine — Prompts and Rules (SYS-009)

Prompt and rule guidance for deterministic orchestration. Implementation repos must pin to prompt/rule versions and record them in the pipeline run manifest.

## Prompt Principles
- Use contract-aware templates that preserve field names and ordering; never rename keys from upstream artifacts.
- Require explicit citations to upstream artifacts (minutes spans, comment IDs, risk/decision IDs) in generated agenda and readiness outputs.
- Enforce deterministic rendering: avoid randomized sampling; set temperature to zero; require consistent ordering of agenda items and readiness sections.
- Do not allow prompts to invent new fields or restructure contracts; block when required source artifacts are missing or unvalidated.

## Rule Pack Expectations
- Agenda rules: carry over unresolved items; prioritize comment dispositions requiring meeting time; map each agenda item to minutes spans or comment IDs.
- Readiness rules: ensure program_brief, study_readiness_assessment, next_best_action_memo, decision_log, risk_register, assumption_register, milestone_plan reference current versions and include provenance pointers.
- Failure rules: block emission when upstream artifacts are missing, stale, or inconsistent; produce explicit failure codes recorded in the run manifest.

## Logging & Provenance
- Every prompt/rule set version, model hash, and seed must be recorded in the run manifest.
- Outputs must include provenance links to all source artifacts used during orchestration.
