# Architecture Review Checklist (Governance-Controlled)

Use this checklist for Claude, Codex, or human architecture reviews before approving governance-sensitive changes.

Authority anchor: `docs/governance/strategy_control_doc.md`.

## 1) Invariant protection
- Which non-negotiable invariant could this change weaken?
- Is the invariant explicitly preserved in design and implementation evidence?
- If changed, is there explicit supersession/ADR authority?

## 2) Stable vs replaceable layer discipline
- Does this increase replaceable-layer complexity without strengthening stable layers?
- Does it add indirection that weakens contract, control, or certification authority?
- Is sequencing still foundation-first?

## 3) Bypass and hidden policy detection
- Does this introduce any path that bypasses eval, trace, policy, enforcement, or certification?
- Does it create hidden policy logic outside declared governance surfaces?
- Are decision criteria explicit and replayable?

## 4) Replayability and determinism
- Does this weaken replayability or deterministic reconstruction?
- Are required artifacts sufficient for post-hoc audit and rerun?
- Is failure state reproducible and diagnosable?

## 5) Trust-gain test
- Does this change add capability without measurable trust gain?
- Is claimed trust gain tied to explicit evidence and exit criteria?
- If trust gain is absent, should this change be blocked or deferred?

## 6) Drift handling
- What drift signals does this change increase, decrease, or leave unaddressed?
- Are warning/freeze/block responses defined?
- Are unresolved drift signals blocking further roadmap expansion?

## 7) Fix-before-expand gate
- What must be fixed before further roadmap expansion is allowed?
- Are required fix slices dependency-ordered and prioritized ahead of expansion work?
- Is the final recommendation: `approve`, `approve_with_blocks`, `freeze`, or `block`?

## Review output minimum
- `decision`
- `invariants_checked`
- `bypass_findings`
- `replayability_status`
- `required_pre_expansion_fixes`
- `drift_signal_summary`
