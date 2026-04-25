"""Optional repo-bootstrap snapshot generator for HOP.

The bootstrap snapshot is a deterministic, schema-shaped summary of
the HOP-relevant repository surface (module layout, schema files, CLI
entrypoints, test commands). Trial-runner agents can request the
snapshot once at startup to ground their reasoning without
re-discovering the layout each invocation.

Snapshot characteristics:

- **Optional.** Nothing in the optimization loop, evaluator, or
  sandbox depends on the snapshot existing. Calling
  :func:`build_bootstrap_snapshot` is purely opt-in.
- **Bounded.** ``MAX_TOTAL_BYTES`` and ``MAX_FIELD_BYTES`` cap the
  snapshot so it cannot exceed the documented context budget.
- **Deterministic.** Output ordering is sorted; relative paths are
  used; timestamps are excluded from the artifact body.
- **Read-only.** The bootstrap performs filesystem reads only — it
  never writes, never imports candidate code, and never touches the
  experience store.

The snapshot is **not** an artifact in the governed sense (it does
not flow through the evaluator and is not promoted). It is a
read-only reference document.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spectrum_systems.modules.hop.schemas import list_hop_schemas

DEFAULT_MAX_TOTAL_BYTES = 32 * 1024  # 32 KiB
DEFAULT_MAX_FIELD_BYTES = 4 * 1024  # 4 KiB


class BootstrapBudgetExceeded(Exception):
    """Raised when the assembled snapshot would exceed the byte budget."""


_REPO_ROOT = Path(__file__).resolve().parents[3]
_HOP_MODULE_DIR = _REPO_ROOT / "spectrum_systems" / "modules" / "hop"
_HOP_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas" / "hop"


@dataclass(frozen=True)
class BootstrapBudget:
    """Per-snapshot byte caps."""

    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    max_field_bytes: int = DEFAULT_MAX_FIELD_BYTES

    def __post_init__(self) -> None:
        if self.max_total_bytes <= 0:
            raise ValueError(
                f"hop_bootstrap_invalid_total:{self.max_total_bytes}"
            )
        if self.max_field_bytes <= 0:
            raise ValueError(
                f"hop_bootstrap_invalid_field:{self.max_field_bytes}"
            )
        if self.max_field_bytes > self.max_total_bytes:
            raise ValueError(
                f"hop_bootstrap_field_exceeds_total:{self.max_field_bytes}>{self.max_total_bytes}"
            )


def _list_hop_modules(repo_root: Path) -> list[str]:
    base = repo_root / "spectrum_systems" / "modules" / "hop"
    if not base.is_dir():
        return []
    out: list[str] = []
    for entry in sorted(base.rglob("*.py")):
        if entry.name.startswith("_") and entry.name != "__init__.py":
            continue
        out.append(str(entry.relative_to(repo_root)))
    return out


def _list_schema_files(repo_root: Path) -> list[str]:
    base = repo_root / "contracts" / "schemas" / "hop"
    if not base.is_dir():
        return []
    return sorted(
        str(p.relative_to(repo_root)) for p in base.glob("*.schema.json")
    )


def _list_eval_manifest(repo_root: Path) -> dict[str, Any] | None:
    manifest_path = repo_root / "contracts" / "evals" / "hop" / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    summary = {
        "path": str(manifest_path.relative_to(repo_root)),
        "case_count": manifest.get("case_count"),
        "case_paths": sorted(
            entry.get("path", "") for entry in (manifest.get("cases") or [])
        ),
    }
    return summary


def _truncate(text: str, *, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[: max_bytes - 16].decode("utf-8", errors="ignore")
    return truncated + "...<truncated>"


def _cli_commands() -> list[dict[str, str]]:
    """Static, repo-wide CLI commands the trial runner can rely on."""
    return [
        {
            "name": "hop_admit_candidate",
            "command": "python -m spectrum_systems.modules.hop.admission",
            "description": "Run HOP admission gate on a candidate payload (JSON via stdin).",
        },
        {
            "name": "hop_evaluate",
            "command": "python -m spectrum_systems.modules.hop.evaluator",
            "description": "Evaluate an admitted candidate against an eval set.",
        },
    ]


def _test_commands() -> list[dict[str, str]]:
    """Static, repo-wide test commands."""
    return [
        {
            "name": "hop_unit",
            "command": "python -m pytest tests/hop -q",
            "description": "Run the HOP unit + integration tests.",
        },
        {
            "name": "hop_full",
            "command": "python -m pytest tests -q",
            "description": "Run the full repo test suite.",
        },
    ]


def build_bootstrap_snapshot(
    *,
    repo_root: Path | None = None,
    budget: BootstrapBudget | None = None,
) -> dict[str, Any]:
    """Build the structured bootstrap snapshot.

    Returns a JSON-serializable mapping. Raises
    :class:`BootstrapBudgetExceeded` if the assembled snapshot would
    exceed ``budget.max_total_bytes``.
    """
    root = repo_root or _REPO_ROOT
    cap = budget or BootstrapBudget()

    snapshot: dict[str, Any] = {
        "snapshot_kind": "hop_bootstrap_v1",
        "repo_root_relative": ".",
        "modules": _list_hop_modules(root),
        "schemas": {
            "registered": list_hop_schemas(),
            "files": _list_schema_files(root),
        },
        "eval_manifest": _list_eval_manifest(root),
        "cli_commands": _cli_commands(),
        "test_commands": _test_commands(),
        "patterns": [
            "spectrum_systems.modules.hop.patterns.draft_verify",
            "spectrum_systems.modules.hop.patterns.label_primer",
            "spectrum_systems.modules.hop.patterns.domain_router",
        ],
        "sandbox": {
            "module": "spectrum_systems.modules.hop.sandbox",
            "entrypoints": ["run_in_sandbox", "make_sandboxed_runner"],
            "blocks": [
                "network",
                "subprocess",
                "filesystem_writes_outside_scratch",
                "process_environment",
            ],
            "limits": ["timeout_seconds", "memory_limit_bytes", "cpu_seconds"],
        },
    }

    # Per-field cap: long lists get truncated to fit ``max_field_bytes``.
    for field_name in ("modules", "patterns"):
        encoded = json.dumps(snapshot[field_name], sort_keys=True).encode("utf-8")
        if len(encoded) > cap.max_field_bytes:
            snapshot[field_name] = snapshot[field_name][: max(1, len(snapshot[field_name]) // 2)]
            snapshot["truncated_fields"] = sorted(
                set(snapshot.get("truncated_fields", [])) | {field_name}
            )

    serialized = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > cap.max_total_bytes:
        raise BootstrapBudgetExceeded(
            f"hop_bootstrap_total_bytes:{len(serialized)}>{cap.max_total_bytes}"
        )
    return snapshot


def serialize_snapshot(snapshot: dict[str, Any]) -> str:
    """Stable JSON serialization of a snapshot."""
    return json.dumps(snapshot, sort_keys=True, ensure_ascii=False, indent=2)


__all__ = [
    "BootstrapBudget",
    "BootstrapBudgetExceeded",
    "DEFAULT_MAX_FIELD_BYTES",
    "DEFAULT_MAX_TOTAL_BYTES",
    "build_bootstrap_snapshot",
    "serialize_snapshot",
]
