# CI Runtime Budget (TST-15)

- **Fast PR gate budget:** 15 minutes target, 25 minutes ceiling.
- **Slow nightly deep gate budget:** 90 minutes target, 180 minutes ceiling.
- **Release readiness budget:** 60 minutes target, 120 minutes ceiling.

## Placement policy
- PR: canonical four gates + smoke/targeted tests only.
- Nightly: full pytest, deep replay/chaos checks, full governance/readiness evidence sweep.
- Release: readiness-heavy checks, replay+lineage, contract compatibility and handoff evidence.

Runtime speed does not override trust guarantees; missing required artifacts block.
