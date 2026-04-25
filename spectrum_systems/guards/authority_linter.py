"""Lightweight authority drift linter.

Pure-stdlib detection of SHADOW_OWNERSHIP_OVERLAP. This module is the
canonical implementation; ``spectrum_systems.modules.runtime.authority_linter``
re-exports from here. CI guard scripts must import this lightweight module
directly so they do not pull in ``spectrum_systems.modules.runtime.__init__``
and its third-party dependencies (``jsonschema`` etc.).

Constraints:
  * standard library only (PyYAML is preferred when available; a minimal
    loader handles the matrix dialect when it is not).
  * no runtime-package imports.
  * no side-effect imports.

Detection contract:
  * scan text for ``<SYSTEM> <verb>`` phrases.
  * cross-check attribution against the canonical authority ownership
    matrix at ``contracts/authority/authority_ownership_matrix.yaml``.
  * emit a finding for every (system, verb) attribution that the matrix
    declares forbidden for the system.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX_PATH = REPO_ROOT / "contracts" / "authority" / "authority_ownership_matrix.yaml"

REASON_CODE = "SHADOW_OWNERSHIP_OVERLAP"

_AUTHORITY_VERBS: tuple[str, ...] = (
    "decides",
    "determines",
    "approves",
    "adjudicates",
    "evaluates",
    "enforces",
    "executes",
    "promotes",
    "certifies",
    "gates",
    "packages",
    "routes",
    "annotates",
    "records",
    "governs",
    "defines",
    "provides",
    "supplies",
    "emits",
)

_VERB_GROUP = "|".join(_AUTHORITY_VERBS)
_SYSTEM_VERB_PATTERN = re.compile(
    rf"\b(?P<system>[A-Z]{{3}})\b(?P<gap>\s+(?:always\s+|never\s+|only\s+)?)(?P<verb>{_VERB_GROUP})\b"
)


class AuthorityLinterError(ValueError):
    """Raised when the authority linter cannot complete deterministically."""


# ---- Matrix loading --------------------------------------------------------


def _try_pyyaml(text: str) -> dict[str, Any] | None:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        loaded = yaml.safe_load(text)
    except Exception as exc:  # noqa: BLE001 - yaml.YAMLError + downstream
        raise AuthorityLinterError(f"authority ownership matrix is malformed: {exc}") from exc
    if not isinstance(loaded, dict):
        raise AuthorityLinterError("authority ownership matrix must be a YAML mapping")
    return loaded


def _strip_comment(line: str) -> str:
    """Strip an inline ``# ...`` comment that is not inside a quoted string.

    Our matrix dialect has no quoted strings, so a plain split is safe.
    """
    idx = line.find("#")
    if idx == -1:
        return line
    # Allow `#` only when preceded by space (inline comment) or at line start.
    if idx == 0 or line[idx - 1].isspace():
        return line[:idx]
    return line


def _minimal_yaml_load(text: str) -> dict[str, Any]:
    """Load the matrix YAML with a stdlib-only parser.

    Supports the exact dialect emitted by ``contracts/authority/
    authority_ownership_matrix.yaml``: mappings, nested mappings, sequences
    of scalar strings, inline empty list (``key: []``), and ``# ...`` line
    or trailing comments. No anchors, flow style, multi-line scalars, or
    quoted strings are required.

    Parsing model: a stack of frames, each holding the container (dict or
    list) and the indentation of the line that opened it. A pending key
    materializes on the first child line — list if it starts with ``- ``,
    mapping otherwise. A pending key with no children materializes as an
    empty mapping.
    """
    root: dict[str, Any] = {}
    frames: list[dict[str, Any]] = [
        {"indent": -1, "container": root, "pending_key": None, "pending_key_indent": -1}
    ]

    def _materialize_pending(top: dict[str, Any], as_list: bool) -> dict[str, Any]:
        new_container: Any = [] if as_list else {}
        if not isinstance(top["container"], dict):
            raise AuthorityLinterError("pending key inside non-mapping container")
        top["container"][top["pending_key"]] = new_container
        frame = {
            "indent": top["pending_key_indent"],
            "container": new_container,
            "pending_key": None,
            "pending_key_indent": -1,
        }
        top["pending_key"] = None
        top["pending_key_indent"] = -1
        frames.append(frame)
        return frame

    for raw_line in text.splitlines():
        stripped_full = _strip_comment(raw_line).rstrip()
        if not stripped_full.strip():
            continue
        indent = len(stripped_full) - len(stripped_full.lstrip(" "))
        body = stripped_full.strip()

        # Materialize a pending key when the next line is at deeper indent.
        # If the next line is at sibling level (indent <= pending_key_indent),
        # the pending key is left with no children — materialize as empty {}.
        top = frames[-1]
        if top["pending_key"] is not None:
            if indent > top["pending_key_indent"]:
                top = _materialize_pending(top, as_list=body.startswith("- "))
            else:
                _materialize_pending(top, as_list=False)
                # Frame just pushed is empty-mapping placeholder; leave it on
                # the stack so the normal pop loop can drop it below.
                top = frames[-1]

        # Pop frames whose opening indent >= current indent (we left their scope).
        while len(frames) > 1 and indent <= frames[-1]["indent"]:
            # If a popped frame still has a pending_key, materialize it as {}.
            if frames[-1]["pending_key"] is not None:
                _materialize_pending(frames[-1], as_list=False)
                # The new frame just pushed is a child of the one being popped;
                # pop it too because we are leaving its scope.
                frames.pop()
            frames.pop()
        top = frames[-1]

        if body.startswith("- "):
            value = body[2:].strip()
            container = top["container"]
            if not isinstance(container, list):
                raise AuthorityLinterError(f"sequence item under non-list: {raw_line!r}")
            container.append(_coerce_scalar(value))
            continue

        if ":" not in body:
            raise AuthorityLinterError(f"line is not a mapping: {raw_line!r}")
        key, _, raw_value = body.partition(":")
        key = key.strip()
        value = raw_value.strip()

        container = top["container"]
        if not isinstance(container, dict):
            raise AuthorityLinterError(f"mapping line under non-dict: {raw_line!r}")

        if value == "":
            top["pending_key"] = key
            top["pending_key_indent"] = indent
            container[key] = None  # placeholder; replaced on materialization
        elif value == "[]":
            container[key] = []
        elif value == "{}":
            container[key] = {}
        else:
            container[key] = _coerce_scalar(value)

    # Materialize any trailing pending keys as empty mappings.
    while frames:
        top = frames[-1]
        if top["pending_key"] is not None:
            _materialize_pending(top, as_list=False)
            frames.pop()
        frames.pop()

    return root


def _coerce_scalar(text: str) -> Any:
    raw = text.strip()
    if raw.startswith(('"', "'")) and raw.endswith(raw[0]) and len(raw) >= 2:
        return raw[1:-1]
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in ("null", "~"):
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _validate_matrix_shape(payload: dict[str, Any]) -> None:
    if not isinstance(payload.get("systems"), dict) or not payload["systems"]:
        raise AuthorityLinterError("authority ownership matrix missing 'systems' mapping")
    if not isinstance(payload.get("canonical_verb_owners"), dict):
        raise AuthorityLinterError("authority ownership matrix missing 'canonical_verb_owners'")


def load_authority_matrix(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the canonical authority ownership matrix.

    Tries PyYAML first (richer parser); falls back to the stdlib minimal
    loader when PyYAML is unavailable. Fails closed on any error.
    """
    matrix_path = Path(path) if path is not None else DEFAULT_MATRIX_PATH
    if not matrix_path.is_file():
        raise AuthorityLinterError(f"authority ownership matrix missing: {matrix_path}")
    text = matrix_path.read_text(encoding="utf-8")

    payload = _try_pyyaml(text)
    if payload is None:
        payload = _minimal_yaml_load(text)
    _validate_matrix_shape(payload)
    return payload


# ---- Detection / repair ----------------------------------------------------


def _normalize_verb(verb: str) -> str:
    return verb.strip().lower()


def _system_record(matrix: dict[str, Any], system: str) -> dict[str, Any] | None:
    systems = matrix.get("systems", {})
    record = systems.get(system)
    return record if isinstance(record, dict) else None


def _suggested_fix(system: str, verb: str, canonical_owner: str | None) -> str:
    if not canonical_owner or canonical_owner == system:
        return f"remove forbidden attribution '{system} {verb}' (system does not own this verb)"
    primary_verb_map = {
        "TLC": "routes",
        "TPA": "adjudicates",
        "CDE": "decides",
        "GOV": "certifies",
        "PRA": "provides",
        "POL": "governs",
        "SEL": "enforces",
        "PQX": "executes",
    }
    fallback_verb = primary_verb_map.get(system, "operates")
    return f"{system} {fallback_verb}; {canonical_owner} {verb}"


def detect_authority_drift(
    text: str,
    *,
    matrix: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return SHADOW_OWNERSHIP_OVERLAP findings for ``text``."""
    if matrix is None:
        matrix = load_authority_matrix()

    findings: list[dict[str, Any]] = []
    for line_index, line in enumerate(text.splitlines(), start=1):
        for match in _SYSTEM_VERB_PATTERN.finditer(line):
            system = match.group("system")
            verb = _normalize_verb(match.group("verb"))
            record = _system_record(matrix, system)
            if record is None:
                continue
            forbidden = {_normalize_verb(v) for v in record.get("forbidden_verbs", [])}
            if verb not in forbidden:
                continue
            canonical_owner = matrix.get("canonical_verb_owners", {}).get(verb)
            findings.append(
                {
                    "reason_code": REASON_CODE,
                    "system": system,
                    "verb": verb,
                    "canonical_owner": canonical_owner,
                    "line": line_index,
                    "match": match.group(0),
                    "suggested_fix": _suggested_fix(system, verb, canonical_owner),
                }
            )
    return findings


def apply_authority_repair(text: str, findings: list[dict[str, Any]]) -> str:
    """Rewrite ``text`` so every drift finding becomes a canonical pattern."""
    if not findings:
        return text

    replacements: dict[tuple[str, str], str] = {}
    for finding in findings:
        key = (str(finding["system"]), str(finding["verb"]))
        replacements[key] = str(finding["suggested_fix"])

    repaired = text
    for (system, verb), fix in replacements.items():
        pattern = re.compile(
            rf"\b{re.escape(system)}\b(?P<gap>\s+(?:always\s+|never\s+|only\s+)?){re.escape(verb)}\b"
        )
        repaired = pattern.sub(fix, repaired)
    return repaired


def is_clean(text: str, *, matrix: dict[str, Any] | None = None) -> bool:
    """True iff ``text`` contains no SHADOW_OWNERSHIP_OVERLAP drift."""
    return not detect_authority_drift(text, matrix=matrix)


def lint_file(path: Path, *, matrix: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run :func:`detect_authority_drift` against a file path."""
    rel = str(path).replace("\\", "/")
    repo_prefix = str(REPO_ROOT).replace("\\", "/") + "/"
    if rel.startswith(repo_prefix):
        rel = rel[len(repo_prefix) :]

    if matrix is None:
        matrix = load_authority_matrix()

    excluded = tuple(matrix.get("scope", {}).get("excluded_path_prefixes", []) or [])
    if any(rel == item or rel.startswith(item.rstrip("/") + "/") for item in excluded):
        return []

    suffixes = tuple(matrix.get("scope", {}).get("default_scope_suffixes", []) or [])
    if suffixes and Path(rel).suffix.lower() not in suffixes:
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AuthorityLinterError(f"failed to read {rel}: {exc}") from exc

    findings = detect_authority_drift(text, matrix=matrix)
    for finding in findings:
        finding["path"] = rel
    return findings


__all__ = [
    "AuthorityLinterError",
    "DEFAULT_MATRIX_PATH",
    "REASON_CODE",
    "REPO_ROOT",
    "apply_authority_repair",
    "detect_authority_drift",
    "is_clean",
    "lint_file",
    "load_authority_matrix",
]
