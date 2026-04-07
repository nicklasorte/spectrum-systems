# HR-B Action Note — 2026-04-07

- Introduced canonical HNX long-running continuity contracts (`checkpoint_record`, `resume_record`, `async_wait_record`, `handoff_artifact`).
- Extended `stage_contract` with deterministic long-running policy inputs (`execution_mode`, `resume_policy`, `async_policy`, `compaction_policy`).
- Added deterministic runtime continuity policy module (`hnx_execution_state`).
- Wired sequence transition seam to fail-closed on invalid continuity/resume/handoff conditions.
- Aligned (without broad migration) existing continuity patterns in prompt-queue and PQX artifacts.
