# Contracts

This repo does **not** define new contracts. It imports canonical contracts from `nicklasorte/spectrum-systems/contracts/schemas`:
- program_brief
- study_readiness_assessment
- next_best_action_memo
- decision_log
- risk_register
- assumption_register
- milestone_plan
- plus upstream inputs (working_paper_input, comment_resolution_matrix, meeting_minutes_contract, etc.)

Fixtures in `examples/outputs/` mirror the canonical examples for local testing. Pin to `contracts/standards-manifest.json` from `spectrum-systems` when consuming schemas programmatically.
