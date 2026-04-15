# Plan — WPG-EXEC-01 — 2026-04-15

## Prompt type
PLAN

## Roadmap item
WPG-EXEC-01 (RTX-04 hardening + RTX-05 red-team closure gate)

## Objective
Harden the governed WPG pipeline fail-closed against RTX-03 severity classes, emit mandatory control decisions at every stage, and execute a post-fix red-team slice that blocks progression on any HIGH finding with ALLOW.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-WPG-EXEC-01-2026-04-15.md | CREATE | Required plan-first governance declaration for multi-file BUILD scope |
| spectrum_systems/modules/wpg/common.py | MODIFY | Tighten control/eval composition and reusable hardening helpers |
| spectrum_systems/modules/wpg/question_extractor.py | MODIFY | Ingress transcript validation and stage-level control decision hardening |
| spectrum_systems/modules/wpg/faq_generator.py | MODIFY | Unknown handling, semantic conflict detection, grounding validation |
| spectrum_systems/modules/wpg/faq_formatter.py | MODIFY | Mandatory control decision and adversarial evaluation checks |
| spectrum_systems/modules/wpg/faq_clusterer.py | MODIFY | Replace keyword routing with similarity/multi-label clustering |
| spectrum_systems/modules/wpg/section_writer.py | MODIFY | Narrative chronology/causality integrity checks + control decision |
| spectrum_systems/modules/wpg/working_paper_assembler.py | MODIFY | Mandatory control decision for working paper and delta artifacts |
| spectrum_systems/orchestration/wpg_pipeline.py | MODIFY | Transcript artifact schema validation + fail-closed control-decision enforcement |
| spectrum_systems/modules/wpg/redteam.py | CREATE | Deterministic RTX-05 red-team execution harness |
| scripts/run_wpg_redteam.py | CREATE | CLI to run post-fix WPG red-team and write governed finding artifact |
| contracts/schemas/transcript_artifact.schema.json | CREATE | Ingress governance schema for transcript boundary |
| contracts/examples/transcript_artifact.json | CREATE | Canonical transcript artifact example |
| contracts/schemas/wpg_redteam_findings.schema.json | CREATE | Contract for deterministic WPG red-team findings artifact |
| contracts/examples/wpg_redteam_findings_post_fix.json | CREATE | Required RTX-05 findings artifact output |
| contracts/standards-manifest.json | MODIFY | Register new contracts under canonical manifest |
| tests/test_wpg_pipeline.py | MODIFY | Add hardening tests for control, unknown, conflict, grounding, narrative, ingress |
| tests/test_wpg_contracts.py | MODIFY | Include new WPG contracts in schema validation coverage |

## Contracts touched
- `transcript_artifact` (new)
- `wpg_redteam_findings` (new)

## Tests that must pass after execution
1. `pytest tests/test_wpg_pipeline.py tests/test_wpg_contracts.py -q`
2. `python -m pytest -q`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/run_wpg_pipeline.py --input tests/fixtures/wpg/sample_transcript.json --output-dir outputs/wpg_exec_01`
5. `python scripts/run_wpg_redteam.py --output contracts/examples/wpg_redteam_findings_post_fix.json`

## Scope exclusions
- No changes to non-WPG orchestration domains outside required contract registration.
- No relaxation of fail-closed control enforcement.
- No test removals or suppression.

## Dependencies
- WPG-00 baseline pipeline available.
- RTX-03 findings treated as hardening requirements.
