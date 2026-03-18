# SKILL.md — checkpoint-packager

## Metadata
- **Skill ID**: checkpoint-packager
- **Type**: VALIDATE
- **Trigger**: At major roadmap checkpoints (after L, P, Q+R, X+Z, AB, AJ)
- **Output**: A checkpoint bundle directory at `artifacts/checkpoints/<CHECKPOINT_ID>/`

## Purpose
Collect and package all evidence required at a roadmap checkpoint.
A checkpoint bundle is the artifact that authorizes advancement to the next roadmap stage.
It is also the input to the Claude review (see `claude-review-prep` skill).

## Checkpoint IDs
| Checkpoint | After | Bundle contents |
| --- | --- | --- |
| `checkpoint-L` | Roadmap item L | Governance/foundations evidence |
| `checkpoint-P` | Roadmap item P | Workflow module evidence (M–P) |
| `checkpoint-QR` | Roadmap items Q+R | Cross-source integration evidence |
| `checkpoint-XZ` | Roadmap items X–Z | Packaging and extraction evidence |
| `checkpoint-AB` | Roadmap item AB | Hardening evidence (AA–AB) |
| `checkpoint-AJ` | Roadmap item AJ | Final proof (AA–AJ complete) |

## Bundle contents (all checkpoints)
```
artifacts/checkpoints/<CHECKPOINT_ID>/
  manifest.json           — checkpoint metadata (ID, date, roadmap items covered)
  test_results.txt        — output of pytest run
  contract_audit.txt      — output of contract-boundary-audit skill
  golden_path_results.txt — output of golden-path-check for relevant contracts
  changed_files.txt       — git diff --stat since last checkpoint
  open_work_items.md      — list of unresolved work items from docs/review-actions/
```

## Workflow

1. Identify the checkpoint ID based on the current roadmap position.

2. Run tests and capture output:
   ```bash
   pytest --tb=short > artifacts/checkpoints/<CHECKPOINT_ID>/test_results.txt 2>&1
   ```

3. Run contract audit:
   ```bash
   .codex/skills/contract-boundary-audit/run.sh > artifacts/checkpoints/<CHECKPOINT_ID>/contract_audit.txt 2>&1
   ```

4. Run golden-path checks for all contracts touched in this stage:
   ```bash
   .codex/skills/golden-path-check/run.sh <CONTRACT_NAME> >> artifacts/checkpoints/<CHECKPOINT_ID>/golden_path_results.txt
   ```

5. Record changed files since last checkpoint:
   ```bash
   git diff --stat <LAST_CHECKPOINT_TAG> HEAD > artifacts/checkpoints/<CHECKPOINT_ID>/changed_files.txt
   ```

6. Collect open work items:
   ```bash
   grep -r "TODO\|OPEN\|DEFERRED" docs/review-actions/ > artifacts/checkpoints/<CHECKPOINT_ID>/open_work_items.md || true
   ```

7. Write `manifest.json` with checkpoint metadata.

8. Pass the bundle path to `claude-review-prep` skill.

## Usage
```bash
.codex/skills/checkpoint-packager/run.sh checkpoint-P
```
