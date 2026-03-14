# GitHub Data Boundary and Artifact Governance

## Control plane vs. data plane
- GitHub is the **control plane** for source, schemas, prompts, templates, lightweight examples, and documentation.
- Local or approved network storage is the **data plane** for any operational or production artifact.
- Engines must read inputs from and write outputs to external storage paths only; no engine may assume GitHub is an artifact lake.

## Allowed in GitHub
- Source code, contracts, schemas, prompts, templates, deterministic tests, and lightweight synthetic examples.
- Documentation, governance rules, and small redacted fixtures that prove interface shapes.

## Forbidden in GitHub
- Operational data of any kind, including uploaded study inputs, working papers, revision sets, comment matrices containing real data, meeting transcripts, generated reports, logs, or evidence bundles.
- Production PDFs, DOCX/DOC files, XLSX/XLS workbooks, PPT/PPTX decks, audio or video recordings, and raw exports from tools.
- Generated outputs or intermediate artifacts from runs (including drafts) beyond tiny synthetic fixtures.
- Artifact archives or datasets stored via Git LFS or GitHub Releases.

## Storage requirements
- All operational artifacts live on approved local or network storage under explicit access control.
- GitHub references artifacts only via external paths and manifests; repositories must never embed or vendor production files.
- Sample artifacts in-repo must be synthetic, redacted, or tiny fixtures stored under clearly named `examples/` or test fixture paths.

## Guardrails and enforcement
- `.gitignore` blocks common binary and office artifact patterns outside fixture paths.
- `scripts/check_artifact_boundary.py` plus the `artifact-boundary` CI workflow warn and fail on prohibited extensions or oversized binaries.
- The `external_artifact_manifest` contract captures where artifacts live externally and proves checksums for traceability.
- Exceptions require documented justification and must remain synthetic within `examples/`, `contracts/examples/`, or test fixture folders.
