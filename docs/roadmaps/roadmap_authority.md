# Roadmap Authority — Operational Note

## Active roadmap authority file
- **Active authority:** `docs/roadmaps/system_roadmap.md`

## Allowed supporting docs
These support execution but are not authority documents:
- `docs/roadmaps/execution_state_inventory.md`
- `docs/roadmaps/codex-prompt-roadmap.md` (reference slicing context)
- `docs/roadmaps/operational-ai-systems-roadmap.md` (historical/reference)
- `docs/roadmap/pqx_queue_roadmap.md` (subordinate queue track)
- `docs/roadmap/pqx_protocol_hardening.md` (subordinate protocol track)
- `docs/roadmap/pqx_execution_map.md` (execution map reference)

## How old roadmaps are treated
- `docs/roadmap/system_roadmap.md`: subordinate reference copy (non-authoritative).
- `docs/roadmap.md`: deprecated historical artifact.
- Any roadmap-like document outside `docs/roadmaps/system_roadmap.md` is either subordinate planning material or reference history.

## Where future status updates belong
- Update status rows, dependencies, and execution ordering only in `docs/roadmaps/system_roadmap.md`.
- Update implementation reality in `docs/roadmaps/execution_state_inventory.md` when bundle outcomes change maturity.

## Where future bundle planning belongs
- Create bundle plans in `docs/review-actions/PLAN-<BUNDLE>-<DATE>.md`.
- Keep each plan’s declared file scope explicit and enforce changed-scope verification.

## How design reviews feed roadmap changes
- Review outputs are authored in `docs/reviews/`.
- Follow-up actions are tracked in `docs/review-actions/`.
- Only after review findings are accepted should roadmap status/dependencies be changed in `docs/roadmaps/system_roadmap.md`.
