# SSOS label system

Standardized GitHub labels for the Spectrum Study Operating System (SSOS) to keep issue tracking consistent across repositories.

## Categories and naming
- **artifact:** Output from meetings and study work products. Examples include `artifact:transcript`, `artifact:minutes`, `artifact:agenda`, `artifact:working-paper`, `artifact:comment-matrix`, `artifact:faq`, `artifact:report-section`, `artifact:decision`.
- **layer:** SSOS system architecture layers. Labels include `layer:factory`, `layer:governance`, `layer:orchestrator`, `layer:engine`, `layer:knowledge`, `layer:advisor`.
- **study:** Study or band focus. Labels include `study:7ghz`, `study:4.4ghz`, `study:2.7ghz`, `study:system`.
- **priority:** Work urgency. Labels include `priority:critical`, `priority:high`, `priority:medium`, `priority:low`.

Naming convention: each label is prefixed with its category (`artifact:`, `layer:`, `study:`, `priority:`) to make filtering deterministic and keep categories grouped.

## Setup
Run the label creation script in any SSOS repository. The script is idempotent and skips labels that already exist.

1. Install GitHub CLI (https://cli.github.com/).
2. Authenticate: `gh auth login`.
3. From the repository root, run:

```bash
./scripts/setup-labels.sh
```
