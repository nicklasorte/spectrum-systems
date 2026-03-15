from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATTERNS = [
    "curl",
    "requests.get(",
    "urllib.request(",
    "raw.githubusercontent.com",
    "api.github.com",
]

CONTEXT_KEYWORDS = [
    "schema",
    "schemas",
    "contract",
    "contracts",
    "registry",
    "registries",
    "standard",
    "standards",
    "manifest",
    "manifests",
    "governance",
]

CODE_EXTENSIONS = {".py", ".js", ".ts", ".sh", ".bash", ".zsh"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".mypy_cache"}


def _iter_candidate_files() -> Iterator[Path]:
    for path in REPO_ROOT.rglob("*"):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path == Path(__file__):
            continue
        if path.suffix.lower() in CODE_EXTENSIONS or (path.suffix == "" and path.parent.name == "scripts"):
            yield path


def test_no_network_schema_loading_patterns() -> None:
    violations: list[str] = []

    for path in _iter_candidate_files():
        try:
            content = path.read_text(errors="ignore")
        except (UnicodeDecodeError, OSError):
            continue

        lines = content.splitlines()
        for idx, line in enumerate(lines):
            lower_line = line.lower()
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in lower_line:
                    context_window = "\n".join(lines[max(0, idx - 1) : idx + 2]).lower()
                    if any(keyword in context_window for keyword in CONTEXT_KEYWORDS):
                        violations.append(f"{path}:{idx + 1} contains '{pattern}' near governance artifact loading logic")

    assert not violations, (
        "Local Governance Artifact Rule: governance artifacts must be loaded from local filesystem paths, "
        "not fetched over the network. Remove network fetch patterns in schema/contract loading contexts:\n- "
        + "\n- ".join(violations)
    )
