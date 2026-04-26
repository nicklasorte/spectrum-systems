"""TLS-00 — Parse ``docs/architecture/system_registry.md`` into a deterministic
dependency graph artifact.

Fail-closed contract:

* Missing/empty registry file -> ``RegistryParseError``.
* Active executable section absent -> ``RegistryParseError``.
* Canonical loop line missing/malformed -> ``RegistryParseError``.
* No active systems detected -> ``RegistryParseError``.
* Validator returns errors -> caller MUST treat as a hard failure; no silent skip.

The output schema is defined in
``schemas/artifacts/system_registry_dependency_graph.schema.json``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "system_registry.md"
SCHEMA_VERSION = "tls-00.v1"


class RegistryParseError(RuntimeError):
    """Raised when the registry cannot be parsed deterministically."""


@dataclass(frozen=True)
class SystemNode:
    system_id: str
    status: str
    purpose: Optional[str]
    upstream: List[str] = field(default_factory=list)
    downstream: List[str] = field(default_factory=list)
    artifacts_owned: List[str] = field(default_factory=list)
    primary_code_paths: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class DependencyGraph:
    schema_version: str
    canonical_loop: List[str]
    canonical_overlays: List[str]
    active_systems: Dict[str, SystemNode]
    merged_or_demoted: Dict[str, Dict[str, str]]
    future_systems: Dict[str, str]
    notes: List[str]


_ACTIVE_SECTION_HEADER = "## Active executable systems"
_MERGED_SECTION_HEADER = "## Merged or demoted systems"
_FUTURE_SECTION_HEADER = "## Future / placeholder systems"
_CANONICAL_LOOP_HEADER = "## Canonical loop"

_SYSTEM_HEADER_RE = re.compile(r"^### (?P<id>[A-Z][A-Z0-9]{1,5})\s*$")
_FIELD_RE = re.compile(r"^- \*\*(?P<key>[^*]+):\*\*\s*(?P<value>.*)$")
_BULLET_RE = re.compile(r"^\s*-\s+(?P<value>.+)$")
_LOOP_TOKEN_RE = re.compile(r"`([A-Z]{2,6}(?:\s*[+→]\s*[A-Z]{2,6})+)`")
_SYSTEM_ID_RE = re.compile(r"^[A-Z][A-Z0-9]{1,5}$")
# Used inside narrative dependency lists where a 2-letter prefix like "PR" can
# appear from words like "PR/task registry". Require 3 chars to match the
# canonical registry's identifier convention (AEX, PQX, EVL, ...).
_NARRATIVE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]{2,5}$")


def _read_registry(path: Path) -> str:
    if not path.exists():
        raise RegistryParseError(f"system registry not found at {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise RegistryParseError(f"system registry at {path} is empty")
    return text


def _split_canonical_loop(text: str) -> tuple[List[str], List[str]]:
    """Extract canonical loop and overlay tokens from the Canonical loop block.

    Accepts the documented form::

        `AEX → PQX → EVL → TPA → CDE → SEL`

        ...

        `REP + LIN + OBS + SLO`
    """

    section_idx = text.find(_CANONICAL_LOOP_HEADER)
    if section_idx == -1:
        raise RegistryParseError("canonical loop section missing")
    section = text[section_idx : text.find("\n## ", section_idx + 1)]
    matches = _LOOP_TOKEN_RE.findall(section)
    if len(matches) < 2:
        raise RegistryParseError("canonical loop block must declare loop and overlay")

    loop_tokens = [t.strip() for t in re.split(r"[→\s]+", matches[0]) if t.strip()]
    overlay_tokens = [t.strip() for t in re.split(r"[+\s]+", matches[1]) if t.strip()]

    if len(loop_tokens) < 3:
        raise RegistryParseError(
            f"canonical loop must contain at least 3 systems, got {loop_tokens!r}"
        )
    if not overlay_tokens:
        raise RegistryParseError("canonical overlays missing from loop block")
    for tok in [*loop_tokens, *overlay_tokens]:
        if not _SYSTEM_ID_RE.match(tok):
            raise RegistryParseError(f"invalid system id in canonical loop: {tok!r}")

    return loop_tokens, overlay_tokens


def _section_slice(text: str, header: str) -> Optional[str]:
    start = text.find(header)
    if start == -1:
        return None
    next_h = text.find("\n## ", start + len(header))
    return text[start:next_h] if next_h != -1 else text[start:]


def _parse_active_systems(text: str) -> Dict[str, SystemNode]:
    section = _section_slice(text, _ACTIVE_SECTION_HEADER)
    if section is None:
        raise RegistryParseError("active executable systems section missing")

    systems: Dict[str, SystemNode] = {}
    lines = section.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _SYSTEM_HEADER_RE.match(line)
        if not m:
            i += 1
            continue
        system_id = m.group("id")
        i += 1

        # Collect raw key->value+continuations and bullets-under-field for
        # this system. Continuations are 2-space-indented lines that follow
        # the bullet or its prior continuation.
        raw_fields: Dict[str, str] = {}
        bullets_for_field: Dict[str, List[str]] = {}
        current_field: Optional[str] = None
        while i < len(lines) and not _SYSTEM_HEADER_RE.match(lines[i]) and not lines[i].startswith("## "):
            row = lines[i]
            field_m = _FIELD_RE.match(row)
            if field_m:
                current_field = field_m.group("key").strip().lower()
                raw_fields[current_field] = field_m.group("value").strip()
                bullets_for_field.setdefault(current_field, [])
            elif current_field is not None and row.startswith("  ") and not row.startswith("  -"):
                # plain continuation of the previous field value
                raw_fields[current_field] = (raw_fields[current_field] + " " + row.strip()).strip()
            elif current_field is not None:
                bullet_m = _BULLET_RE.match(row)
                if bullet_m:
                    bullets_for_field[current_field].append(bullet_m.group("value").strip())
            i += 1

        status = (raw_fields.get("status", "unknown") or "unknown").lower()
        purpose = raw_fields.get("purpose") or None
        upstream = _split_id_list(raw_fields.get("upstream dependencies", ""))
        downstream = _split_id_list(raw_fields.get("downstream dependencies", ""))

        artifacts_inline = _split_artifact_list(raw_fields.get("canonical artifacts owned", ""))
        artifacts_bullet = [_strip_backticks(b) for b in bullets_for_field.get("canonical artifacts owned", [])]
        artifacts_owned = _dedupe(artifacts_inline + artifacts_bullet)

        primary_code_paths = _dedupe(
            _strip_backticks(b) for b in bullets_for_field.get("primary code paths", [])
        )

        if status == "active":
            systems[system_id] = SystemNode(
                system_id=system_id,
                status=status,
                purpose=purpose,
                upstream=_dedupe(upstream),
                downstream=_dedupe(downstream),
                artifacts_owned=artifacts_owned,
                primary_code_paths=primary_code_paths,
            )

    if not systems:
        raise RegistryParseError("no active systems parsed from registry")
    return systems


def _parse_merged_or_demoted(text: str) -> Dict[str, Dict[str, str]]:
    section = _section_slice(text, _MERGED_SECTION_HEADER)
    if section is None:
        return {}
    table: Dict[str, Dict[str, str]] = {}
    for line in section.splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        sys_id, status, target, rationale = cells[:4]
        if not _SYSTEM_ID_RE.match(sys_id):
            continue
        table[sys_id] = {
            "status": status.lower(),
            "merged_into": target,
            "rationale": rationale,
        }
    return table


def _parse_future_systems(text: str) -> Dict[str, str]:
    section = _section_slice(text, _FUTURE_SECTION_HEADER)
    if section is None:
        return {}
    table: Dict[str, str] = {}
    for line in section.splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        sys_id, _status, rationale = cells[:3]
        if not _SYSTEM_ID_RE.match(sys_id):
            continue
        table[sys_id] = rationale
    return table


def _split_id_list(value: str) -> List[str]:
    parts = re.split(r"[,/]| and ", value)
    out: List[str] = []
    for part in parts:
        token = part.strip().rstrip(".").strip()
        if not token:
            continue
        m = re.match(r"^([A-Z][A-Z0-9]{2,5})", token)
        if m and _NARRATIVE_ID_RE.match(m.group(1)):
            out.append(m.group(1))
    return out


def _split_artifact_list(value: str) -> List[str]:
    return [_strip_backticks(p.strip().rstrip(".")) for p in value.split(",") if p.strip()]


def _strip_backticks(value: str) -> str:
    return value.strip().strip("`").strip()


def _dedupe(values: Iterable[str]) -> List[str]:
    seen: List[str] = []
    for v in values:
        if v and v not in seen:
            seen.append(v)
    return seen


def parse_registry(registry_path: Optional[Path] = None) -> DependencyGraph:
    """Parse the canonical registry markdown into a ``DependencyGraph``.

    Raises ``RegistryParseError`` on any structural violation. There are no
    silent recoveries.
    """

    path = registry_path or DEFAULT_REGISTRY_PATH
    text = _read_registry(path)
    canonical_loop, canonical_overlays = _split_canonical_loop(text)
    active = _parse_active_systems(text)
    merged = _parse_merged_or_demoted(text)
    future = _parse_future_systems(text)

    notes: List[str] = []
    for sys_id in canonical_loop + canonical_overlays:
        if sys_id not in active:
            raise RegistryParseError(
                f"canonical loop system {sys_id} not found in active executable section"
            )

    graph = DependencyGraph(
        schema_version=SCHEMA_VERSION,
        canonical_loop=canonical_loop,
        canonical_overlays=canonical_overlays,
        active_systems=active,
        merged_or_demoted=merged,
        future_systems=future,
        notes=notes,
    )
    errors = validate_dependency_graph(graph)
    if errors:
        raise RegistryParseError("; ".join(errors))
    return graph


def validate_dependency_graph(graph: DependencyGraph) -> List[str]:
    """Return a list of validation errors. Empty list = valid."""

    errors: List[str] = []
    if not graph.canonical_loop:
        errors.append("canonical_loop empty")
    if not graph.canonical_overlays:
        errors.append("canonical_overlays empty")
    if not graph.active_systems:
        errors.append("active_systems empty")
    for sys_id, node in graph.active_systems.items():
        if node.status != "active":
            errors.append(f"{sys_id}: non-active node in active_systems")
        for ref in node.upstream + node.downstream:
            if ref not in graph.active_systems and ref not in graph.merged_or_demoted and ref not in graph.future_systems:
                # missing reference is a non-fatal note: registry text may use
                # narrative aliases (e.g. "review inputs"). We tolerate but
                # surface in notes via the parser (no schema break).
                graph.notes.append(f"unresolved_reference:{sys_id}->{ref}")
    return errors


def build_dependency_graph(registry_path: Optional[Path] = None) -> Dict:
    """Build the JSON-serializable artifact dictionary.

    Output conforms to ``schemas/artifacts/system_registry_dependency_graph.schema.json``.
    """

    graph = parse_registry(registry_path)
    nodes = []
    for sys_id in sorted(graph.active_systems):
        node = graph.active_systems[sys_id]
        nodes.append(
            {
                "system_id": node.system_id,
                "status": node.status,
                "purpose": node.purpose,
                "upstream": list(node.upstream),
                "downstream": list(node.downstream),
                "artifacts_owned": list(node.artifacts_owned),
                "primary_code_paths": list(node.primary_code_paths),
            }
        )

    merged_rows = sorted(
        (
            {"system_id": k, **v}
            for k, v in graph.merged_or_demoted.items()
        ),
        key=lambda r: r["system_id"],
    )
    future_rows = sorted(
        ({"system_id": k, "rationale": v} for k, v in graph.future_systems.items()),
        key=lambda r: r["system_id"],
    )

    return {
        "schema_version": graph.schema_version,
        "phase": "TLS-00",
        "canonical_loop": list(graph.canonical_loop),
        "canonical_overlays": list(graph.canonical_overlays),
        "active_systems": nodes,
        "merged_or_demoted": merged_rows,
        "future_systems": future_rows,
        "parse_notes": list(graph.notes),
    }


def write_artifact(output_path: Path, registry_path: Optional[Path] = None) -> Dict:
    payload = build_dependency_graph(registry_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
