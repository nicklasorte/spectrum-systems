# Systems Index — spectrum-program-advisor

| Component | Purpose | Inputs | Outputs | Contracts |
| --- | --- | --- | --- | --- |
| Program Advisor Core | Normalize canonical artifacts into a program-state model and score decision readiness | Working paper metadata, comment resolution matrix metadata, meeting minutes metadata, risk register, decision log, milestone plan, assumption register | Program Brief, Study Readiness Assessment, Next Best Action Memo, top risks, open decisions, missing evidence report | program_brief, study_readiness_assessment, next_best_action_memo, decision_log, risk_register, assumption_register, milestone_plan |

Follow the canonical contracts defined in `spectrum-systems/contracts/schemas`. Use `docs/program-state-model.md` for the internal normalization layout.
