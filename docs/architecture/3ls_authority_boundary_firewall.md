# Authority Boundary Firewall (3-Letter System Support Layer)

A systematic hardening layer that catches protected vocabulary leaks across
the 3-letter systems earlier than the existing CI leak guard.

This firewall does not define ownership. Canonical responsibility for every
3-letter system lives in `docs/architecture/system_registry.md`. The firewall
reads that registry indirectly via
`contracts/governance/authority_registry.json` and applies vocabulary checks.
It enforces what the canonical registry already declares; it never creates,
extends, or shadows ownership.

This layer does not replace `scripts/run_authority_leak_guard.py`. The CI
gate remains the binding check. The firewall described here is fast local
feedback that produces structured repair suggestions.

## Source of canonical responsibility

Every responsibility claim referenced in this document is delegated to:

- `docs/architecture/system_registry.md`

Each entry under `three_letter_system_boundary_guidance` in
`contracts/governance/authority_registry.json` carries a
`canonical_authority_source` field that points back to the registry. The
firewall does not assign responsibility; it reads the canonical registry and
classifies changed paths against non-owning support roles.

## Why protected vocabulary is firewalled

Protected words name a hard responsibility seam. When non-owning surfaces
use words like `allow`, `block`, `freeze`, `promote`, or fields like
`decision`, `enforcement_action`, `certification_status`, downstream
readers and tools cannot tell whether the surface produced the verdict or
merely echoed it. The H01B class of bugs is exactly this confusion — a
non-owning module quietly emits responsibility shape, and another module
begins to depend on it as if it were canonical.

The firewall keeps the responsibility seam narrow and named. It does not
rename, redirect, or override the canonical registry.

## Boundary support roles

The firewall classifies each 3-letter system as a non-owning support role.
The canonical owner of any specific responsibility is declared in
`docs/architecture/system_registry.md`. The boundary roles below are
classification labels only.

| System    | boundary_role                       |
|-----------|-------------------------------------|
| `TPA`     | `trust_policy_support`              |
| `SEL`     | `fail_closed_action_support`        |
| `CDE`     | `closure_readiness_support`         |
| `GOV`     | `gate_review_support`               |
| `TLC`     | `routing_support`                   |
| `PQX`     | `execution_coordination_support`    |
| `RDX`     | `roadmap_preparation_support`       |
| `MAP`     | `metadata_topology_support`         |
| `DASHBOARD` | `evidence_display_support`        |

Each entry declares `non_authority_assertions` recording what the entry
must not claim. Examples (read directly from the registry, not redefined
here):

- A `routing_support` entry declares `not_control_authority`,
  `not_judgment_authority`, `not_certification_authority`,
  `not_enforcement_authority`.
- An `execution_coordination_support` entry declares `not_control_authority`,
  `not_judgment_authority`, `not_certification_authority`,
  `not_enforcement_authority`.
- A `roadmap_preparation_support` entry declares `not_control_authority`,
  `not_closure_authority`, `not_certification_authority`,
  `not_enforcement_authority`.
- A `metadata_topology_support` entry declares `not_control_authority`,
  `not_closure_authority`, `not_certification_authority`,
  `not_enforcement_authority`.
- An `evidence_display_support` entry declares `not_control_authority`,
  `not_judgment_authority`, `not_certification_authority`,
  `not_enforcement_authority`.

Note that `DASHBOARD` is recorded with empty `support_path_prefixes`
because dashboard/UI files live outside the existing leak guard scope
(`spectrum_systems/modules/` and `contracts/examples/`). Until that scope
is extended, dashboard surfaces are governed by the separate UI review
process; the entry is preserved only for non-claim declaration and to
attribute future scope-extension findings.

## Why support surfaces cannot use protected words

If a routing support surface emits `decision: allow`, callers downstream
may accept that record as if it were a canonical control verdict. The same
hazard applies when an execution coordination support surface emits
`enforcement_action`, when a roadmap preparation support surface emits
`promotion_ready`, or when a metadata topology support surface emits
`certified`. Any of these creates a parallel responsibility seam that
bypasses the canonical registry.

Neutral vocabulary preserves the same workflow expressiveness while keeping
canonical attribution unambiguous.

## Neutral vocabulary

Defined in `contracts/governance/authority_neutral_vocabulary.json`.

| Forbidden              | Neutral replacement                                  |
|------------------------|------------------------------------------------------|
| `allow`                | `passed_gate`, `gate_evidence_valid`                 |
| `block`                | `failed_gate`, `gate_evidence_invalid`               |
| `freeze`               | `held_state`, `requires_review`                      |
| `promote`              | `advance_to_next_stage`                              |
| `decision`             | `gate_evidence`, `routing_result`, `evaluation_result` |
| `enforcement_action`   | `action_request`, `routed_action_ref`                |
| `certification_status` | `certification_evidence_status`                      |
| `certified`            | `certification_evidence_present`                     |
| `promoted`             | `advanced_to_stage`                                  |
| `promotion_ready`      | `ready_for_gate_review`                              |

These mappings are machine-readable; the preflight emits them directly as
suggestion targets.

## How to run the preflight locally

```bash
scripts/preflight_3ls_authority.sh
```

That wrapper runs:

```bash
python scripts/run_3ls_authority_preflight.py --base-ref origin/main --head-ref HEAD
python scripts/suggest_3ls_authority_repairs.py \
    --input outputs/3ls_authority_preflight/3ls_authority_preflight_result.json
```

Outputs:

- `outputs/3ls_authority_preflight/3ls_authority_preflight_result.json`
- `outputs/3ls_authority_preflight/3ls_authority_repair_suggestions.json`

Both artifacts are deterministic and safe to commit when you want to capture
a review surface for a PR.

## What to do when the firewall fails

1. Read the `suggested_repairs` block in the result artifact. Each repair
   lists the path, line, forbidden token, one or more neutral replacements,
   and the `canonical_authority_source` to consult.
2. If the changed file matches a non-owning support classification, rename
   the field or value to a neutral term and re-run the preflight.
3. If the suggestion is flagged `owner_authority_review_required: true`, the
   path matched a declared support prefix. Confirm the responsibility
   alignment against `docs/architecture/system_registry.md` (the
   canonical_authority_source) before doing anything else. Do not widen
   `vocabulary_overrides`.
4. If you believe a new path should map to a canonical responsibility owner,
   that change is a registry update — propose it in
   `docs/architecture/system_registry.md` first, then add the support
   classification entry separately. The firewall never auto-edits source
   files and never auto-extends allowlists.

## Hard rules the firewall preserves

- Existing `scripts/run_authority_leak_guard.py` remains the binding CI gate
  and is not weakened by this firewall.
- This firewall does not assign responsibility. Every entry under
  `three_letter_system_boundary_guidance` is non-owning.
- No broad allowlist override is ever proposed by the firewall.
- The non-owning support classifications never become a parallel
  responsibility seam — the neutral vocabulary preserves their non-claim
  status and the canonical registry retains responsibility.
- The firewall is suggestion-only. It never silently rewrites source files.
- Forbidden words are never normalised by hiding them in comments or docs.
