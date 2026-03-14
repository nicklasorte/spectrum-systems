# System Architecture

INPUTS  
|  
INGESTION  
|  
NORMALIZATION  
|  
ANALYSIS  
|  
SYNTHESIS  
|  
VALIDATION  
|  
OUTPUT ARTIFACTS

Every system implemented in this repository must follow this architecture, mapping its components and data flows through each stage to maintain consistency, auditability, and reproducibility.

## Contract Layer
- Contracts published in `contracts/` define the machine-readable interfaces between stages.
- System-factory will mirror these contracts into scaffolded repos, but spectrum-systems remains the source of truth.
- Each contract includes provenance metadata (`run_id`, `record_id`, `source_repo`, `standards_version`) to preserve traceability through the pipeline above.

## Control Plane vs Data Plane
- GitHub is the control plane for contracts, schemas, prompts, and governance; it is never the storage layer for operational artifacts.
- The data plane lives on approved local or network storage; engines must read/write production inputs and outputs through external paths only.
- No engine may assume GitHub is an artifact lake; manifests must reference absolute external paths instead.
- See `docs/data-boundary-governance.md` for the full policy and guardrails.
