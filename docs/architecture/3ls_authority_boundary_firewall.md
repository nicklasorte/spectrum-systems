# 3LS Authority Boundary Firewall

A systematic hardening layer that catches authority vocabulary leaks across the
3-letter systems (3LS) earlier than the existing CI authority leak guard, and
explains them well enough that the fix is obvious.

This layer does **not** replace `scripts/run_authority_leak_guard.py`. The CI
guard remains the binding gate. The firewall described here is fast local
feedback that produces structured repair suggestions.

## Why authority vocabulary is protected

Authority words name a hard responsibility surface. When non-owner systems use
words like `allow`, `block`, `freeze`, `promote`, or fields like `decision` /
`certification_status`, downstream readers and tools cannot tell whether the
surface produced the verdict or merely echoed it. The H01B class of bugs is
exactly this confusion — a non-authority module quietly emits authority shape,
and another module begins to depend on it as if it were authoritative.

The firewall keeps the authority surface narrow and named.

## 3-letter system authority map

Defined in
`contracts/governance/authority_registry.json::three_letter_system_authority`:

| System    | Authority domains                          | Notes |
|-----------|--------------------------------------------|-------|
| TPA       | `control_decision`, `policy_authority`     | Sole control authority |
| SEL       | `enforcement`                              | Sole enforcement authority |
| CDE       | `certification`, `promotion`               | Sole certification + promotion authority |
| GOV       | `certification`, `governance_gate`         | Governance gate surface |
| TLC       | `routing`                                  | Routing only — never control |
| PQX       | `execution_coordination`                   | Execution coordination only — never approval |
| RDX       | `roadmap_planning`                         | Roadmap planning only — never control |
| MAP       | `mapping_metadata`                         | Mapping/metadata only — never control |
| DASHBOARD | `evidence_display`                         | Displays evidence only — never produces verdicts |

TLC, PQX, RDX, MAP, and DASHBOARD declare `non_authority_assertions` in the
registry; they are explicitly **not** control, enforcement, or certification
authorities even when their work involves consuming and routing gate evidence.

DASHBOARD is registered with empty `owner_path_prefixes` because dashboard/UI
files live outside the existing leak guard scope (`spectrum_systems/modules/`
and `contracts/examples/`). The registry entry records DASHBOARD's
non-authority status so any future scope extension or UI-layer review can
attribute findings correctly. Until that scope is extended, dashboard
authority shape is governed by separate UI review.

## Why TLC / PQX / RDX / MAP cannot use control words

If a router (TLC) emits `decision: allow`, callers downstream may accept that
record as if it were a TPA control decision. The same hazard applies when an
execution coordinator (PQX) emits `enforcement_action`, when a roadmap
planner (RDX) emits `promotion_ready`, or when a metadata layer (MAP) emits
`certified`. Any of these creates a parallel authority surface that bypasses
the canonical owner.

Neutral vocabulary keeps the same workflow expressiveness while keeping
authority attribution unambiguous.

## Neutral vocabulary

Defined in `contracts/governance/authority_neutral_vocabulary.json`.

| Forbidden            | Neutral replacement                                  |
|----------------------|------------------------------------------------------|
| `allow`              | `passed_gate`, `gate_evidence_valid`                 |
| `block`              | `failed_gate`, `gate_evidence_invalid`               |
| `freeze`             | `held_state`, `requires_review`                      |
| `promote`            | `advance_to_next_stage`                              |
| `decision`           | `gate_evidence`, `routing_result`, `evaluation_result` |
| `enforcement_action` | `action_request`, `routed_action_ref`                |
| `certification_status` | `certification_evidence_status`                    |
| `certified`          | `certification_evidence_present`                     |
| `promoted`           | `advanced_to_stage`                                  |
| `promotion_ready`    | `ready_for_gate_review`                              |

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

Both artifacts are deterministic and safe to commit when you want to capture a
review surface for a PR.

## What to do when the guard fails

1. Read the `suggested_repairs` block in the result artifact. Each repair lists
   the path, line, forbidden token, and one or more neutral replacements.
2. If you are working in TLC / PQX / RDX / MAP / DASHBOARD: rename the field or
   value to a neutral term and re-run the preflight.
3. If your file is a declared owner under
   `three_letter_system_authority.<SYSTEM>.owner_path_prefixes`, the suggestion
   is flagged `owner_authority_review_required: true`. Do **not** widen
   `vocabulary_overrides` to silence the warning; confirm the authority domain
   alignment with the owning system's maintainers first.
4. If you believe a new path should be a canonical owner, propose the change to
   `authority_registry.json` in a separate PR with explicit justification. The
   firewall never auto-edits source files and never auto-extends allowlists.

## Hard rules the firewall preserves

- Existing `scripts/run_authority_leak_guard.py` remains the binding CI gate.
- No broad allowlist override is ever proposed by the firewall.
- TLC, PQX, RDX, MAP, and DASHBOARD never become control authority via this
  surface — neutral vocabulary preserves their non-authority status.
- The firewall is suggestion-only. It never silently rewrites source files.
- Forbidden words are never normalised by hiding them in comments or docs.
