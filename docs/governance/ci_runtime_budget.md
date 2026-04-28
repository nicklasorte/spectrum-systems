# CI Runtime Budget (TST-15)

- **Fast PR gate budget:** 15 minutes target, 25 minutes hard ceiling.
- **Slow nightly deep gate budget:** 90 minutes target, 180 minutes hard ceiling.
- **Release gate budget:** 60 minutes target, 120 minutes hard ceiling.

## Placement policy
- PR: canonical four gates + smoke/targeted tests only.
- Nightly: full pytest, deep replay/chaos/fail-closed validations, full governance/certification sweep.
- Release: certification-heavy checks, replay+lineage, contract compatibility and promotion readiness.

Runtime speed never overrides trust guarantees; if required artifacts are missing, gates block.
