# Authority-Shape Feedback Loop (ASF-01)

## Purpose

Catch authority-shape vocabulary issues earlier and propose bounded repair
guidance that coding agents can act on inside the changed file set. The
existing `authority_shape_preflight` (AGS-001) and the 3LS authority leak
guard remain the binding gates; ASF-01 only adds an early-warning chain that
emits artifacts upstream of those gates.

This loop does not redefine ownership. Canonical authority is declared in
`docs/architecture/system_registry.md` and remains with CDE/SEL.

## Participating 3-letter systems

| System  | Role in this loop                                                                                                                  |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| AEX     | Observes admission risk early. Runs the changed-scope authority scan before full preflight.                                        |
| PQX     | Scopes the scan to the changed file set. PQX never expands repair scope beyond changed files.                                      |
| RIL     | Interprets each finding into a plain-language `authority_shape_violation` with safe and unsafe repair guidance.                     |
| FRE     | Proposes vocabulary-only replacements for each finding. FRE proposes; it never authorizes or applies.                               |
| TPA     | Validates the repair candidate against the trust/policy envelope (neutral vocabulary, no allowlist edits, no registry edits).       |
| CDE     | Sole decision authority. CDE may consume the policy-check record as input; ASF-01 does not bypass CDE.                              |
| SEL     | Sole enforcement authority. SEL never receives a vocabulary repair from this loop without a CDE authorization record upstream.      |

## Flow

```
authority-shape issue
  → AEX preflight observation
      run_changed_scope_authority_scan.py
      → changed_scope_authority_scan_record.json
  → PQX scoped test selection
      (scan inherits the changed-file set; never escalates scope)
  → RIL interpretation packet
      → authority_shape_interpretation_packet.json
  → FRE repair candidate
      → authority_shape_repair_candidate.json   (status: proposed)
  → TPA policy/trust check
      validate_authority_repair_candidate.py
      → authority_repair_policy_check_record.json
  → CDE receives authority input
  → SEL only acts after CDE authorization
```

The wrapper `scripts/run_authority_shape_feedback_loop.py` chains these
artifacts in one call.

## Why MET cannot use authority verbs

`MET` (metrics, measurement, telemetry) surfaces produce evidence about
artifacts; they do not produce decisions, certifications, promotions, or
enforcement. When a MET document reads "promotion_decision" or
"enforcement_action", a downstream reader can no longer tell whether MET
emitted authority or merely echoed it. Neutral framing keeps attribution
unambiguous.

## Banned terms and neutral replacements

| Banned term            | Owner system(s) | Neutral replacement                            | Example fix                                                              |
| ---------------------- | --------------- | ---------------------------------------------- | ------------------------------------------------------------------------ |
| `*_decision`           | JDX, CDE        | `*_signal`, `*_observation`, `*_recommendation` | `routing_decision` → `routing_observation`                                |
| `promotion`, `promoted` | REL, GOV, CDE  | `promotion_signal`, `readiness_observation`     | `harness_promotion_decision` → `harness_promotion_signal`                 |
| `rollback_record`      | REL             | `rollback_signal`, `restoration_recommendation` | `rollback_record` → `rollback_signal`                                     |
| `certified`, `certification` | GOV, CDE  | `certification_input`, `readiness_evidence`     | `certification_record` → `certification_input`                            |
| `control_decision`     | CDE, TPA        | `control_input`, `risk_signal`                 | `control_decision` → `control_input`                                      |
| `enforcement_action`   | SEL, ENF        | `enforcement_signal`, `compliance_observation`  | `enforcement_record` → `enforcement_signal`                               |
| `approved`, `approval` | GOV, HIT        | `review_request`, `advisory_result`             | `approval_record` → `review_request`                                      |
| `release_decision`     | REL, GOV        | `release_signal`, `release_observation`         | `release_decision` → `release_signal`                                     |
| `authority_decision`   | GOV             | `authority_input`, `authority_signal`           | `authority_decision` → `authority_signal`                                 |
| `quarantine`           | REL, SEC        | `quarantine_signal`, `risk_observation`         | `quarantine_record` → `quarantine_signal`                                 |
| `final_decision`       | CDE, GOV        | `final_signal`, `closure_input`                 | `final_decision` → `final_signal`                                         |

The full vocabulary is canonical in
`contracts/governance/authority_shape_vocabulary.json` and
`contracts/governance/authority_neutral_vocabulary.json`. ASF-01 reads from
those files; it does not extend them.

## Artifacts

| Artifact                                       | Producer  | Consumer  | Authority effect |
| ---------------------------------------------- | --------- | --------- | ---------------- |
| `changed_scope_authority_scan_record`          | AEX/PQX   | RIL       | none (input)     |
| `authority_shape_interpretation_packet`        | RIL       | FRE       | none (input)     |
| `authority_shape_repair_candidate`             | FRE       | TPA       | none (proposal)  |
| `authority_repair_policy_check_record`         | TPA       | CDE       | none (input)     |

CDE/SEL authority is the only path that can result in a source-tree change.
ASF-01 does not modify source files.

## Running the loop locally

```bash
# Run only the early scan
python scripts/run_changed_scope_authority_scan.py \
  --base-ref main --head-ref HEAD \
  --output outputs/authority_shape_preflight/changed_scope_authority_scan_record.json

# Run the full chain (scan → RIL packet → FRE candidate → TPA check)
python scripts/run_authority_shape_feedback_loop.py \
  --base-ref main --head-ref HEAD \
  --output-dir outputs/authority_shape_preflight
```

The full binding preflight is unchanged:

```bash
python scripts/run_authority_shape_preflight.py \
  --base-ref main --head-ref HEAD --suggest-only
python scripts/run_3ls_authority_preflight.py
```

## Hard constraints

- Does not weaken `authority_shape_preflight`.
- Does not add allowlist exceptions for any system, including MET.
- Does not change canonical authority ownership.
- Does not let a model decide authority. Replacement candidates are drawn
  from the existing vocabulary clusters.
- Does not auto-apply changes; only proposes them inside the changed file set.
- Does not introduce a new top-level 3-letter system.
