# spectrum-program-advisor (governed scaffold)

Program-management advisor for spectrum studies. Normalizes canonical artifacts, scores decision readiness, and emits briefs, readiness assessments, and prioritized next actions. This folder is the governed scaffold for the standalone `spectrum-program-advisor` repo.

## What it does (MVP)
- Ingest canonical inputs: working paper metadata, comment resolution matrix metadata, meeting minutes metadata, risk register, milestone plan, decision log, assumption register.
- Normalize them into a shared internal program-state model.
- Run rule-based + AI-assisted assessments to produce: Program Brief, Study Readiness Assessment, Next Best Action Memo, Top Risks summary, Open Decisions summary, Missing Evidence / Missing Artifact report.
- Expose a simple CLI (`src/cli.py`) that serves deterministic structured outputs from fixtures.
- Ship fixtures and tests that align to `spectrum-systems` contracts.

## How this fits the czar repo org
- **Constitution**: Inherits governance from `nicklasorte/spectrum-systems`; all contracts are defined there and mirrored here as fixtures only.
- **Upstream engines**: Consumes outputs from comment-resolution-engine, working-paper-review-engine, meeting-minutes-engine, and risk/decision/milestone/assumption publishers.
- **Downstream**: Feeds governance boards, report compilers, and pipeline orchestrations with decision readiness and next actions.
- **Contracts**: Uses canonical contracts from `spectrum-systems/contracts/schemas` (program_brief, study_readiness_assessment, next_best_action_memo, decision_log, risk_register, assumption_register, milestone_plan).
- **Determinism**: Structured outputs are authoritative; prose renderings must round-trip to the JSON.

## Layout
- `SYSTEMS.md` — system index for this repo scaffold.
- `CODEX.md` / `CLAUDE.md` — agent guidance for execution vs. reasoning.
- `docs/` — architecture, program-state model, MVP scope.
- `contracts/` — pointer to canonical contracts (no copies); fixtures mirror canonical examples.
- `src/` — CLI entrypoint and normalization helpers.
- `examples/` — sample inputs and outputs used by the CLI.
- `tests/` — minimal tests verifying fixtures and CLI determinism.

## Quick start
```bash
cd examples/spectrum-program-advisor
python src/cli.py brief
python src/cli.py readiness
python src/cli.py nba
python src/cli.py top-risks
python src/cli.py missing-evidence
```

Outputs come from `examples/outputs/` and conform to the canonical contracts. Update fixtures alongside contract changes in `spectrum-systems`.
