# SKILL.md — claude-review-prep

## Metadata
- **Skill ID**: claude-review-prep
- **Type**: REVIEW
- **Trigger**: After checkpoint-packager completes at a major checkpoint
- **Output**: A structured review prompt file at `docs/review-actions/<DATE>-<CHECKPOINT_ID>-review-prep.md`

## Purpose
Assemble the structured input Claude needs to conduct a design review at a roadmap checkpoint.
Produces a review prompt that follows the canonical review format in `docs/design-review-standard.md`.
Claude review at a checkpoint blocks advancement until findings are addressed or formally deferred.

## Inputs
- `CHECKPOINT_ID` — the checkpoint being reviewed (e.g., `checkpoint-P`)
- Checkpoint bundle at `artifacts/checkpoints/<CHECKPOINT_ID>/`
- Relevant roadmap items from `docs/roadmaps/codex-prompt-roadmap.md`

## Workflow

1. Verify the checkpoint bundle exists:
   ```
   artifacts/checkpoints/<CHECKPOINT_ID>/manifest.json
   ```

2. Read the checkpoint manifest to determine which roadmap items are covered.

3. Collect review inputs:
   - `artifacts/checkpoints/<CHECKPOINT_ID>/test_results.txt`
   - `artifacts/checkpoints/<CHECKPOINT_ID>/contract_audit.txt`
   - `artifacts/checkpoints/<CHECKPOINT_ID>/changed_files.txt`
   - `artifacts/checkpoints/<CHECKPOINT_ID>/open_work_items.md`

4. Generate a review prompt file at:
   ```
   docs/review-actions/<DATE>-<CHECKPOINT_ID>-review-prep.md
   ```

5. The review prompt must include:
   - Checkpoint ID and covered roadmap items
   - Summary of what was built/wired/validated in this stage
   - Test and contract audit results
   - Changed file summary
   - Open work items
   - Specific review questions based on the stage focus (see checkpoint table)
   - Request for structured findings using `docs/design-review-standard.md` format
   - Request for action tracker stub using `docs/review-actions/action-tracker-template.md`

## Stage-specific review focus
| Checkpoint | Review focus |
| --- | --- |
| `checkpoint-L` | Governance integrity — are contracts, schemas, and lifecycle gates structurally sound? |
| `checkpoint-P` | Workflow correctness — do modules produce and consume artifacts correctly end-to-end? |
| `checkpoint-QR` | Integration coherence — does cross-source wiring respect contract boundaries? |
| `checkpoint-XZ` | Packaging discipline — are checkpoint bundles complete and extraction artifacts traceable? |
| `checkpoint-AB` | Hardening progress — are guardrails, SLOs, and reconciliation loops operational? |
| `checkpoint-AJ` | Final proof — does the system satisfy all Level-16 criteria? |

## Usage
```bash
.codex/skills/claude-review-prep/run.sh checkpoint-P
```

## Notes
- The output file is a prompt, not a review. Submit it to Claude for the actual review.
- After Claude produces findings, create an action tracker stub in `docs/review-actions/` using `action-tracker-template.md`.
- Link the review and action tracker in `docs/review-registry.md`.
