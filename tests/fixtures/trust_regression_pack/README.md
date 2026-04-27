# Trust Regression Pack (NT-22..24)

Each fixture in this folder is a permanent trust-loop seam exemplar. The
pack is small by design — it does NOT duplicate the wider pytest suite. It
exists so that a single canonical example of each failure mode is always
available for:

* operator triage CLI rendering tests,
* end-to-end loop-proof validation,
* red-team mutation tests that confirm the seam still catches the failure.

## Fixtures

| File | Seam | Expected canonical category |
| --- | --- | --- |
| `pass.json` | passing path | (none — `final_status=pass`) |
| `block.json` | blocked path | EVAL_FAILURE / CERTIFICATION_GAP |
| `freeze.json` | freeze path | CERTIFICATION_GAP |
| `stale_proof.json` | stale trust artifact | CERTIFICATION_GAP (TRUST_FRESHNESS_*) |
| `tier_violation.json` | report-as-evidence escape | POLICY_MISMATCH (TIER_DRIFT_*) |
| `reason_code_violation.json` | unmapped/forbidden code | POLICY_MISMATCH |
| `replay_lineage_mismatch.json` | replay vs lineage trace gap | REPLAY_MISMATCH / LINEAGE_GAP |
| `context_admission_failure.json` | context untrusted | CONTEXT_ADMISSION_FAILURE |

Each fixture should remain compact. If a new failure mode emerges, add a
new fixture file rather than mutating an existing one.
