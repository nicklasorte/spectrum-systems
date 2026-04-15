# RTX-03 WPG Red-Team Review

## Prompt type
`REVIEW`

## 1) Scope of testing
This review targeted the live WPG pipeline path:
- transcript -> question extraction -> FAQ generation -> FAQ report -> clustering -> section writing -> working paper assembly -> delta.
- Eval and control behavior at each stage.
- Deterministic replay and boundary governance behavior.

Inspected implementation surfaces:
- `spectrum_systems/modules/wpg/*`
- `spectrum_systems/orchestration/wpg_pipeline.py`
- `scripts/run_wpg_pipeline.py`
- `contracts/schemas/wpg_*.schema.json`
- `contracts/examples/wpg_*.json`

## 2) Inputs used
### Baseline (mandatory)
- `sample_transcript.json`

### Adversarial red-team inputs (created for this review)
- `outputs/wpg_redteam/inputs/conflict_suppression.json`
  - Semantically conflicting answers phrased with slight question-text variation.
- `outputs/wpg_redteam/inputs/overconfidence_unknown.json`
  - Unknown / no-answer prompts to stress confidence and uncertainty handling.
- `outputs/wpg_redteam/inputs/missing_questions.json`
  - High-risk declaratives with no question marks.
- `outputs/wpg_redteam/inputs/clustering_narrative.json`
  - Cross-theme lexical overlaps to stress clustering and sequencing.

## 3) Pipeline outputs observed
Per run, full artifact chain was captured under `outputs/wpg_redteam/<case>/`:
- `question_set_artifact.json`
- `faq_artifact.json`
- `faq_report_artifact.json`
- `faq_cluster_artifact.json`
- `working_section_artifact.json`
- `working_paper_artifact.json`
- plus conflict/confidence/unknowns/delta/bundle.

Key observed behaviors:
- High pass-rates in eval summaries even for incorrect outcomes.
- Control decisions only populated for early stages; later synthesis stages had no control decision envelope.
- Unknown answers frequently scored with max confidence and rendered as normal narrative bullets.

## 4) Top 5 vulnerabilities (ranked)
1. **Control bypass at synthesis stages** (high): no control gate on working-paper stages, allowing silently bad outputs through.
2. **Overconfidence on unknown/no-answer content** (high): confidence remains 1.0 for weak answers.
3. **Hallucinated consensus / conflict suppression** (high): semantic disagreement missed due exact-string grouping.
4. **Eval weakness** (high): contradiction eval includes trivially passing check and does not test adversarial failure.
5. **Unknown suppression** (high): uncertainty is recorded but not enforced in confidence/control or prominent narrative status.

## 5) Failure patterns across stages
- **Extraction stage**: strict `?` heuristic causes blind spots (missed implicit questions) but does fail closed when empty.
- **FAQ stage**: source-presence checks pass without semantic grounding quality; contradiction detection underpowered.
- **Cluster/section/assembly stages**: lexical bucketing and deterministic ordering can manipulate emphasis while still passing eval.
- **Control chain**: only partial stage coverage; missing control metadata is effectively a bypass condition.

## 6) Detection outcomes (eval/control/silent)
| Failure class | Detected by eval? | Detected by control? | Silently passed? |
|---|---|---|---|
| Hallucinated consensus | No | No | Yes |
| Conflict suppression | No | No | Yes |
| Source drift risk | No | No | Yes |
| Overconfidence | No | No (ALLOW) | Yes |
| Missing questions | Yes | Yes (BLOCK) | No |
| Clustering failure | No | No | Yes |
| Narrative manipulation | No | No | Yes |
| Unknown suppression | No | No | Yes |
| Eval weakness | N/A (self weakness) | No | Yes |
| Control bypass | N/A (missing controls) | No | Yes |

## 7) Replay consistency results
Replay test on `conflict_suppression.json` produced identical replay signatures across repeated runs:
- run1: `383154ed92e6437f838b9a593f6e0d548478da453530dbe97678246fc8f260ff`
- run2: `383154ed92e6437f838b9a593f6e0d548478da453530dbe97678246fc8f260ff`

Result: **deterministic replay is stable** for tested case.

## 8) 3LS boundary integrity
Boundary risk identified:
- `transcript_artifact` is created directly in orchestration and not contract-validated at ingress.
- Governance/control/eval become active only after this entry step.

Result: **boundary is partially governed, not end-to-end fail-closed at ingress**.

## 9) Final verdict
Because multiple **high-severity** failures (overconfidence, conflict suppression, control bypass, eval weakness) passed with effective `ALLOW` behavior and no blocking enforcement in tested runs, verdict is:

## **NEEDS FIXES FIRST**

This system is **not safe to expand** in its current control/eval state.
