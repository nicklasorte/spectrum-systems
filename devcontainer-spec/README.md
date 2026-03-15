# Canonical Development Container

This directory defines the base devcontainer used across the spectrum ecosystem. Downstream repositories (engines, pipelines, and data lake tooling) should copy or reference this configuration to ensure consistent development environments.

## Why this exists
- Establishes a single Python runtime (3.11) and toolchain for all ecosystem repos.
- Enables reproducible developer setups and reduces environment drift.
- Aligns engines and orchestration pipelines on shared dependencies and extensions.

## Contents
- `devcontainer.json` — VS Code Dev Containers definition pointing at the canonical image, extensions, and post-create setup.
- `Dockerfile` — pins the base image to Python 3.11 for the ecosystem runtime.
- `requirements-base.txt` — shared Python dependencies used across repos (DOCX parsing, schema validation, testing).

## Usage in other repositories
Create a `.devcontainer` directory in the target repo that reuses these assets (copy or reference) so every environment inherits the same runtime. This keeps engines, pipelines, and advisory tools aligned on a compatible baseline.
