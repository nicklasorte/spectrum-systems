# RTX-WPG-02

## Scope
Red-team round 2 for WPG pipeline.

## Attacks and findings
1. Cross-stage inconsistency: mitigated by schema validation at every artifact boundary.
2. Replay drift: mitigated by deterministic replay signature over full artifact chain.
3. Policy drift: mitigated by embedding `policy_version` and `eval_version` in provenance/replay.
4. 3LS ownership bypass: mitigated by adding WPG ownership and required tests to three-letter policy.

## Mandatory fixes applied
- Added deterministic replay signature and trace linkage to output bundle.
- Added 3LS policy ownership for module/orchestration/script/schema paths.
- Added tests for replay consistency, control decisions, contract validity, and CLI output.
