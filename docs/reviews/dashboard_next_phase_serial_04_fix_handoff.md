# DASHBOARD NEXT PHASE SERIAL 04 — Fix Handoff Prompt

Use this follow-up prompt only for remaining blockers/highest-leverage surgical fixes after the final repair pass:

1. Validate all phase-04 panels against live artifact payload variants and tighten field-level type guards where unknown payload shapes appear.
2. Add targeted fixture artifacts for each blocked-state branch in phase-04 panels and expand unit tests to exercise those branches.
3. Run certification gate trace diagnostics and capture any panel parity drift (contract vs capability vs provenance) in a single repair PR.
4. Keep scope narrow: no new panels, no new authority, no new artifact families.
