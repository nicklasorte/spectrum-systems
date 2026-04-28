# Trust regression pack (NT-22)

A small, permanent set of seam-level fixtures exercised by
`tests/test_nt_trust_regression_pack.py`. Each fixture pins one path
through the canonical loop so a regression in any trust seam is caught
immediately.

## Why each fixture is permanent

| Fixture | Trust seam | Reason it stays |
| --- | --- | --- |
| `pass_path.json` | full canonical loop | proves the green path renders pass with all evidence refs and a current freshness audit |
| `block_eval_path.json` | EVL → CDE | regression catch for missing required eval (canonical reason `EVAL_FAILURE`) |
| `freeze_certification_path.json` | GOV / CDE | regression catch for control-issued freeze propagating into evidence index status |
| `stale_proof_path.json` | freshness audit | regression catch for digest mismatch on the certification evidence index |
| `tier_escape_path.json` | OBS tier audit | regression catch for `report` artifact attempting to satisfy promotion evidence |
| `unknown_reason_path.json` | reason-code canonicalizer | regression catch for an unknown blocking reason failing closed |
| `replay_lineage_mismatch_path.json` | REP / LIN join | regression catch for the broken-causality red team |
| `context_admission_failure_path.json` | CTX | regression catch for context admission block propagating to certification |

The pack is intentionally NOT a full pytest re-run; it pins seam
behaviour, not surface area.
