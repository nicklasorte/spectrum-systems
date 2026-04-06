# RIL Architecture Review Action Tracker — 2026-04-05

- Source Review: docs/reviews/2026-04-05-ril-architecture-review.md
- Owner: Spectrum Systems maintainers
- Last Updated: 2026-04-05

## High-Priority Items

### [RIL-ARCH-01] Tighten bundle contract to fail closed on nested projection shape
- **Priority:** High
- **Why:** `review_projection_bundle_artifact` currently allows nested projection fields as generic objects, weakening contract-level validation at final handoff.
- **Required change:** Bind `roadmap_projection`, `control_loop_projection`, and `readiness_projection` to strict schema definitions.
- **Acceptance evidence:**
  - Schema rejects malformed nested projections.
  - Adapter tests include a failing malformed nested projection case and passing golden-path case.
- **Status:** Open

### [RIL-ARCH-02] Enforce RIL-01 parser output contract at runtime
- **Priority:** High
- **Why:** RIL-01 does not currently validate emitted `review_signal_artifact` against schema before return, unlike RIL-02/03/04.
- **Required change:** Add schema validation of parser output in `parse_review_to_signal()` and fail closed on violations.
- **Acceptance evidence:**
  - Tests proving invalid parser output cannot be emitted.
  - Golden-path parser output remains schema-valid.
- **Status:** Open

## Medium-Priority Items

### [RIL-ARCH-03] Add governance controls for classifier rule evolution
- **Priority:** Medium
- **Why:** RIL-02 classification semantics are deterministic but policy-adjacent; ungoverned rule growth can create hidden authority behavior.
- **Required change:** Introduce explicit versioning + change control expectations for classifier mapping rules.
- **Acceptance evidence:**
  - Rule-version bump requirement documented.
  - Review/action evidence required for classifier mapping changes.
- **Status:** Open

### [RIL-ARCH-04] Codify non-authoritative consumption expectations for RIL outputs
- **Priority:** Medium
- **Why:** Strong labels (`enforcement_block`, `control_escalation`) can be misused by downstream consumers as decisions.
- **Required change:** Add explicit contract/docs language that RIL outputs are intake intelligence, not enforcement authority.
- **Acceptance evidence:**
  - Contract notes or governance docs updated.
  - At least one downstream intake interface references non-authoritative handling requirement.
- **Status:** Open

## Deferred Items

### [RIL-ARCH-D1] Monitor path-sensitive provenance identity behavior
- **Priority:** Deferred
- **Why:** Parser hash basis includes source path, which is deterministic but may cause cross-environment identity surprises.
- **Trigger:** Evidence of replay confusion across environment/path moves.
- **Status:** Deferred
