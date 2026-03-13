# System Lifecycle

Use this lifecycle to move a system from idea to trusted operation. Do not skip stages; each stage adds evidence that the system is safe to depend on.

1. **Problem & Bottleneck Definition**  
   - Define the workflow pain point and decision impact. Link to `docs/bottleneck-map.md`.
2. **Interface & Schema Definition**  
   - Draft `systems/<system>/interface.md` with inputs, outputs, schemas, and validation rules.
3. **Design & Failure Analysis**  
   - Flesh out `design.md` and `failure-modes` for the system. Identify human review gates.
4. **Evaluation Plan**  
   - Define evaluation goals and datasets; link to `eval/<system>/`. Add the system to `eval/test-matrix.md`.
5. **Prompt & Rule Drafting**  
   - Create prompts under `prompts/` using the prompt standard; capture versioning and grounding rules.
6. **Prototype Implementation (separate repo)**  
   - Build minimal functionality in an implementation repository, importing schemas and prompts from here.
7. **Validation & Reproducibility**  
   - Run evaluation harnesses, capture run manifests, and verify determinism.
8. **Review & Approval**  
   - Human review of outputs, prompts, rules, and schemas. Update status in `docs/system-status-registry.md`.
9. **Operationalization**  
   - Establish maintenance cadence, rollback procedure, and change controls. Reference `docs/repo-maintenance-checklist.md`.

Exit criteria for each stage must be documented in the system’s `overview.md`. If a stage is blocked, document the dependency rather than bypassing it.
