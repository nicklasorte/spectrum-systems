# 3LS Authority Boundary Firewall — Fix Plan

**Source review:** `contracts/review_artifact/3LS_authority_firewall_review.json`
(`docs/reviews/3LS_authority_firewall_review.md`)
**Date:** 2026-04-25

The red-team review surfaced one finding (F-003, S3) requiring action in this
batch. All other findings (F-001, F-002, F-004 through F-008) were S0 and
covered by the implementation and tests. No S2+ findings were left
unresolved.

## FIX-001 — DASHBOARD scope gap recorded with explicit registry entry

**Finding:** F-003 — dashboard / app / components paths are outside the
existing `default_scope_prefixes` and therefore not scanned by either the CI
authority leak guard or the new 3LS preflight.

**Action taken in this batch:**

1. Added a `DASHBOARD` entry under
   `contracts/governance/authority_registry.json::three_letter_system_boundary_guidance`
   with `boundary_role: "evidence_display_support"`,
   `non_authority_assertions: ["not_control_authority", "not_judgment_authority", "not_certification_authority", "not_enforcement_authority"]`,
   empty `support_path_prefixes`, an explicit `canonical_authority_source`
   pointing back to `docs/architecture/system_registry.md`, and a
   `scope_note` documenting that dashboard files live outside the existing
   leak guard scope. Canonical responsibility remains with the registry; the
   entry is purely non-owning support classification.
2. Documented the same constraint in
   `docs/architecture/3ls_authority_boundary_firewall.md`, explaining that
   DASHBOARD is recorded for non-authority status declaration even though
   files under `dashboard/`, `app/`, `components/` are not currently
   scanned.

**Why the fix is structural rather than scope-extension:**

Extending `default_scope_prefixes` to include `dashboard/`, `app/`, and
`components/` would catch dashboard authority shape leaks but would also
trigger on existing non-authority uses of words like `allow` and `block`
(CSS classes, button labels, feature-flag toggles). That change would be a
scope expansion of the existing CI gate and warrants its own batch with a
separate red-team review.

**Regression test:**

`tests/governance/test_3ls_authority_preflight.py::test_classify_three_letter_system_owner_match`
exercises `classify_three_letter_system` against a known TLC owner path,
confirming the registry entries are visible to the firewall classification
helper. The classification helper handles the empty-prefix DASHBOARD entry
without failure (verified by all 16 firewall tests passing).

## Remaining risk

DASHBOARD/UI authority leaks remain outside the runtime scan surface. This
is now a tractable change: the registry entry, the neutral vocabulary, and
the firewall classification all already accept DASHBOARD; only the scope
extension is deferred. A follow-up batch should evaluate adding
`dashboard/api/` (or similar narrower prefix that only contains UI server
code) to `default_scope_prefixes`.
