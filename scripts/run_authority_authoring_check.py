#!/usr/bin/env python3
"""AUTH-AUTHORING-01 - pre-PR authoring-time authority-safe language check.

Fast, observation-only scanner over changed authored files. Surfaces
reserved authority vocabulary and protected owner-acronym usage in
non-owner builder/doc contexts so authors can repair them before the
heavier CI guards run.

Authority scope: observation_only. This check is non-substituting -
it does not replace or weaken any of:

  - scripts/run_authority_shape_preflight.py
  - scripts/run_authority_leak_guard.py
  - scripts/run_system_registry_guard.py

Canonical ownership remains with the systems declared in
``docs/architecture/system_registry.md``.

Exit codes:
  0 - status=pass (no findings)
  1 - status=warn (findings present but observation-only)
  2 - status=block (reserved for future hard-gate adoption; never set
      by default to avoid accidental authority claims)
  3 - status=unknown (scan could not complete deterministically)

The artifact written at ``outputs/authority_authoring_check/
authority_authoring_check_record.json`` is the durable evidence
surface; consumers MUST read the artifact rather than infer status
from exit code alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.changed_files import (  # noqa: E402
    ChangedFilesResolutionError,
    resolve_changed_files,
)


DEFAULT_OUTPUT_REL_PATH = "outputs/authority_authoring_check/authority_authoring_check_record.json"

# Authored-language surfaces this check is responsible for. Anything
# outside these prefixes is skipped (with skip_reason=outside_authored_surface)
# - the heavier guards still cover the non-authored runtime / module surface.
AUTHORED_PREFIXES: tuple[str, ...] = (
    "docs/",
    "contracts/schemas/",
    "contracts/examples/",
    "scripts/",
    "tests/",
)
AUTHORED_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
)

# Non-authored generated artifact surfaces. These are produced by
# scripts and are not authored content; default policy is to skip
# them (they are covered by deterministic-regen tests). Authors
# should not be flagged for terminology baked into a generated JSON.
GENERATED_PREFIXES: tuple[str, ...] = (
    "outputs/",
    "artifacts/",
    "governance/reports/",
    "docs/governance-reports/",
)

# Owner paths exempt from this check. The scanner is itself an
# authority-vocabulary surface (it has to reference the words it
# detects), and its own contract/test/doc files describe the same
# vocabulary. These are explicit owner-context paths for AUTH-AUTHORING-01.
SELF_OWNER_PATHS: frozenset[str] = frozenset({
    "scripts/run_authority_authoring_check.py",
    "contracts/schemas/authority_authoring_check_record.schema.json",
    "contracts/examples/authority_authoring_check_record.example.json",
    "tests/test_authority_authoring_check.py",
    "docs/reviews/AUTH-AUTHORING-01_redteam.md",
    "docs/review-actions/AUTH-AUTHORING-01_fix_actions.md",
})

# Canonical-owner path prefixes loaded from the authority registry
# (categories[*].canonical_owners[*].owner_path_prefixes). Files
# matching one of these prefixes are owner-context for the cluster
# named by the term, so observed authority terminology is expected
# there and is not flagged. Existing guards continue to govern the
# substantive authority-shape check.
_AUTHORITY_REGISTRY_PATH = REPO_ROOT / "contracts" / "governance" / "authority_registry.json"


def _load_owner_path_prefixes() -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    """Return ``(all_owner_paths, owner_paths_by_cluster)``.

    Cluster keys mirror the registry's category names (e.g. ``control_decision``,
    ``enforcement``, ``certification``, ``promotion``).
    """
    try:
        payload = json.loads(_AUTHORITY_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return frozenset(), {}
    by_cluster: dict[str, set[str]] = {}
    union: set[str] = set()
    for cluster_name, cluster in (payload.get("categories") or {}).items():
        if not isinstance(cluster, dict):
            continue
        owners = cluster.get("canonical_owners") or []
        for owner in owners:
            for prefix in owner.get("owner_path_prefixes") or []:
                p = str(prefix).strip()
                if not p:
                    continue
                by_cluster.setdefault(str(cluster_name), set()).add(p)
                union.add(p)
    # Also exclude paths registry explicitly excludes from forbidden contexts.
    contexts = payload.get("forbidden_contexts") or {}
    for excluded in contexts.get("excluded_path_prefixes") or []:
        e = str(excluded).strip()
        if e:
            union.add(e)
    return frozenset(union), {k: frozenset(v) for k, v in by_cluster.items()}


# Reserved authority term clusters. Built from base verbs by suffix
# expansion to avoid hand-listing every inflected form (and to keep the
# list compact and auditable). Cluster keys align with the canonical
# authority categories declared in the registry.
_BASE_VERBS_BY_CLUSTER: dict[str, tuple[str, ...]] = {
    "approval":         ("approve", "approval"),
    "certification":    ("certify", "certification"),
    "promotion":        ("promote", "promotion"),
    "enforcement":      ("enforce", "enforcement"),
    "control_decision": ("decide", "decision"),
    "authorization":    ("authorize", "authorization"),
    "verdict":          ("verdict",),
}


def _expand_term(base: str) -> tuple[str, ...]:
    """Expand a base verb/noun to its common inflected forms.

    Suffix expansion is conservative: only forms a human author is
    realistically going to write. We do not generate every English
    inflection - only the common ones used in PR drift cases.
    """
    forms = {base}
    if base.endswith("e"):
        # approve -> approved, approves, approving
        forms.add(base + "d")
        forms.add(base + "s")
        forms.add(base[:-1] + "ing")
    elif base.endswith("y"):
        # certify -> certified, certifies, certifying
        forms.add(base[:-1] + "ied")
        forms.add(base[:-1] + "ies")
        forms.add(base + "ing")
    elif base.endswith("ion"):
        # certification -> certifications
        forms.add(base + "s")
    else:
        forms.add(base + "s")
        forms.add(base + "d")
        forms.add(base + "ing")
    return tuple(sorted(forms))


_RESERVED_TERMS_BY_CLUSTER: dict[str, tuple[str, ...]] = {
    cluster: tuple(sorted({form for base in bases for form in _expand_term(base)}))
    for cluster, bases in _BASE_VERBS_BY_CLUSTER.items()
}

# Build a single regex that matches any reserved term as a whole word.
_ALL_RESERVED_TERMS: tuple[str, ...] = tuple(sorted({
    t for terms in _RESERVED_TERMS_BY_CLUSTER.values() for t in terms
}))
_RESERVED_TERMS_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _ALL_RESERVED_TERMS) + r")\b",
    flags=re.IGNORECASE,
)
# Map term -> cluster (lowercase keys).
_TERM_TO_CLUSTER: dict[str, str] = {}
for _cluster, _terms in _RESERVED_TERMS_BY_CLUSTER.items():
    for _t in _terms:
        _TERM_TO_CLUSTER[_t.lower()] = _cluster

# Negation cues that immediately precede a reserved term within a
# small window. Negated phrasing is still an authority claim shape -
# "does not certify" still asserts a certification stance the
# non-owner file cannot make - so we flag it with its own category.
_NEGATION_CUES: tuple[str, ...] = (
    "not", "no", "never", "without", "non", "cannot", "can't", "won't",
    "doesn't", "don't", "isn't", "aren't", "wasn't", "weren't", "didn't",
    "shouldn't",
)
_NEGATION_WINDOW = 32  # characters before the matched term

# Protected canonical owner acronyms. These are flagged when used
# in ownership/authority/responsibility shape inside non-owner authored
# files. The simple shape check is "acronym near authority verb within
# a small window" - a strict regex would over-fire on routine
# documentation references.
_PROTECTED_OWNER_ACRONYMS: tuple[str, ...] = ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL")
_OWNERSHIP_VERBS: tuple[str, ...] = (
    "owns", "owning", "owned", "controls", "controlling", "controlled",
    "is responsible for", "responsible for", "approves", "approving", "approved",
    "certifies", "certifying", "certified", "promotes", "promoting", "promoted",
    "enforces", "enforcing", "enforced", "decides", "deciding", "decided",
    "authorizes", "authorizing", "authorized",
)
_OWNERSHIP_RE = re.compile(
    r"\b(?P<acronym>" + "|".join(_PROTECTED_OWNER_ACRONYMS) + r")\b[^.\n]{0,60}?\b(?P<verb>"
    + "|".join(re.escape(v) for v in _OWNERSHIP_VERBS) + r")\b",
)
_OWNERSHIP_RE_REVERSE = re.compile(
    r"\b(?P<verb>" + "|".join(re.escape(v) for v in _OWNERSHIP_VERBS) + r")\b[^.\n]{0,60}?\b(?P<acronym>"
    + "|".join(_PROTECTED_OWNER_ACRONYMS) + r")\b",
)


# Reason codes, suffixed to make grep-and-find easy in artifacts.
RC_RESERVED = "reserved_authority_term_in_non_owner_context"
RC_NEGATED = "negated_authority_term_in_non_owner_context"
RC_PROTECTED_OWNER = "protected_owner_reference_in_non_owner_context"
RC_GENERATED_SKIPPED = "generated_file_skipped"
RC_SCAN_UNKNOWN = "scan_unknown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_record_id(*, base_ref: str, head_ref: str, created_at: str) -> str:
    raw = f"{base_ref}|{head_ref}|{created_at}".encode("utf-8")
    return "auth-authoring-check-" + hashlib.sha256(raw).hexdigest()[:16]


def _is_authored_path(rel_path: str) -> bool:
    if rel_path in AUTHORED_FILES:
        return True
    return any(rel_path.startswith(prefix) for prefix in AUTHORED_PREFIXES)


def _is_generated_path(rel_path: str) -> bool:
    return any(rel_path.startswith(prefix) for prefix in GENERATED_PREFIXES)


def _is_owner_path(rel_path: str, owner_paths: frozenset[str]) -> bool:
    if rel_path in SELF_OWNER_PATHS:
        return True
    for prefix in owner_paths:
        norm = prefix.rstrip("/")
        if rel_path == norm:
            return True
        if prefix.endswith("/") and rel_path.startswith(prefix):
            return True
        if not prefix.endswith("/") and rel_path.startswith(norm + "/"):
            return True
    return False


def _looks_like_text(path: Path) -> bool:
    """Cheap text-ness probe: read first 4KB and check for NUL bytes."""
    try:
        head = path.open("rb").read(4096)
    except OSError:
        return False
    if b"\x00" in head:
        return False
    return True


def _negation_precedes(text: str, term_start: int) -> str | None:
    """Return the negation cue immediately preceding ``term_start``, else None."""
    window_start = max(0, term_start - _NEGATION_WINDOW)
    window = text[window_start:term_start].lower()
    # Look at words in the window. Any negation cue within the window counts.
    for cue in _NEGATION_CUES:
        # word-boundary, allow trailing punctuation/whitespace before the term
        pattern = r"\b" + re.escape(cue) + r"\b"
        if re.search(pattern, window):
            return cue
    return None


def _line_at(text: str, offset: int) -> tuple[int, str]:
    """Return ``(line_number_1_based, line_text)`` for character offset."""
    line_no = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset) + 1
    line_end = text.find("\n", offset)
    if line_end == -1:
        line_end = len(text)
    return line_no, text[line_start:line_end]


def _trim_snippet(snippet: str, *, max_len: int = 240) -> str:
    s = snippet.strip()
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_file(
    *,
    rel_path: str,
    text: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return ``(unsafe_findings, protected_owner_findings)`` for a file.

    The caller is responsible for owner-path filtering; this function
    only runs the regex layer.
    """
    unsafe_findings: list[dict[str, object]] = []
    protected_findings: list[dict[str, object]] = []

    for match in _RESERVED_TERMS_RE.finditer(text):
        term = match.group(1)
        line_no, line_text = _line_at(text, match.start())
        cluster = _TERM_TO_CLUSTER.get(term.lower())
        negation = _negation_precedes(text, match.start())
        category = "negated_authority_term" if negation else "reserved_authority_term"
        reason_code = RC_NEGATED if negation else RC_RESERVED
        unsafe_findings.append({
            "file": rel_path,
            "line": line_no,
            "term": term,
            "category": category,
            "snippet": _trim_snippet(line_text),
            "reason_code": reason_code,
            "canonical_owner_hint": cluster,
        })

    seen_protected: set[tuple[int, str]] = set()
    for regex in (_OWNERSHIP_RE, _OWNERSHIP_RE_REVERSE):
        for match in regex.finditer(text):
            acronym = match.group("acronym")
            line_no, line_text = _line_at(text, match.start())
            key = (line_no, acronym)
            if key in seen_protected:
                continue
            seen_protected.add(key)
            protected_findings.append({
                "file": rel_path,
                "line": line_no,
                "owner_acronym": acronym,
                "snippet": _trim_snippet(line_text),
                "reason_code": RC_PROTECTED_OWNER,
            })

    return unsafe_findings, protected_findings


def evaluate_authoring_check(
    *,
    repo_root: Path,
    changed_files: list[str],
    base_ref: str,
    head_ref: str,
    output_artifact_ref: str,
    owner_paths: frozenset[str],
) -> dict[str, object]:
    """Evaluate the authoring check and return the artifact payload."""
    scanned: list[str] = []
    skipped: list[dict[str, object]] = []
    unsafe: list[dict[str, object]] = []
    protected: list[dict[str, object]] = []
    reason_codes: set[str] = set()
    scan_unknown = False

    for rel_path in changed_files:
        full = repo_root / rel_path
        if not full.is_file():
            skipped.append({"file": rel_path, "skip_reason": "missing_on_disk"})
            continue
        if _is_owner_path(rel_path, owner_paths):
            skipped.append({"file": rel_path, "skip_reason": "owner_path"})
            continue
        if _is_generated_path(rel_path):
            skipped.append({"file": rel_path, "skip_reason": "generated_artifact"})
            reason_codes.add(RC_GENERATED_SKIPPED)
            continue
        if not _is_authored_path(rel_path):
            skipped.append({"file": rel_path, "skip_reason": "outside_authored_surface"})
            continue
        if not _looks_like_text(full):
            skipped.append({"file": rel_path, "skip_reason": "non_text"})
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped.append({"file": rel_path, "skip_reason": "unreadable"})
            scan_unknown = True
            continue

        scanned.append(rel_path)
        u, p = scan_file(rel_path=rel_path, text=text)
        unsafe.extend(u)
        protected.extend(p)

    has_findings = bool(unsafe or protected)
    if scan_unknown:
        status = "unknown"
        reason_codes.add(RC_SCAN_UNKNOWN)
    elif has_findings:
        status = "warn"
        for f in unsafe:
            reason_codes.add(str(f.get("reason_code")))
        for f in protected:
            reason_codes.add(str(f.get("reason_code")))
    else:
        status = "pass"

    payload: dict[str, object] = {
        "artifact_type": "authority_authoring_check_record",
        "schema_version": "1.0.0",
        "record_id": _stable_record_id(
            base_ref=base_ref, head_ref=head_ref, created_at=_utc_now()
        ),
        "created_at": _utc_now(),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "changed_files": list(changed_files),
        "scanned_files": sorted(scanned),
        "skipped_files": skipped,
        "unsafe_findings": unsafe,
        "protected_owner_findings": protected,
        "status": status,
        "reason_codes": sorted(reason_codes),
        "output_artifact_refs": [output_artifact_ref],
        "authority_scope": "observation_only",
        "summary": {
            "unsafe_finding_count": len(unsafe),
            "protected_owner_finding_count": len(protected),
            "scanned_file_count": len(scanned),
            "skipped_file_count": len(skipped),
        },
    }
    return payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AUTH-AUTHORING-01 pre-PR authority-safe authoring check"
    )
    parser.add_argument(
        "--base-ref", default="origin/main",
        help="Git base ref for changed-file resolution",
    )
    parser.add_argument(
        "--head-ref", default="HEAD",
        help="Git head ref for changed-file resolution",
    )
    parser.add_argument(
        "--changed-files", nargs="*", default=[],
        help="Explicit changed files (passthrough; bypasses git diff)",
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT_REL_PATH,
        help="Artifact output path",
    )
    return parser.parse_args()


def _exit_code_for_status(status: str) -> int:
    return {"pass": 0, "warn": 1, "block": 2, "unknown": 3}.get(status, 3)


def main() -> int:
    args = _parse_args()
    output_path = (REPO_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_rel = str(output_path.relative_to(REPO_ROOT))
    except ValueError:
        # ``--output`` may point outside the repo (e.g. tmp dir in tests).
        # Fall back to the absolute path; consumers reading the artifact
        # ref can still resolve it.
        output_rel = str(output_path)

    try:
        changed_files = resolve_changed_files(
            repo_root=REPO_ROOT,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            explicit_changed_files=list(args.changed_files or []),
        )
    except ChangedFilesResolutionError as exc:
        payload = {
            "artifact_type": "authority_authoring_check_record",
            "schema_version": "1.0.0",
            "record_id": _stable_record_id(
                base_ref=args.base_ref, head_ref=args.head_ref, created_at=_utc_now()
            ),
            "created_at": _utc_now(),
            "base_ref": args.base_ref,
            "head_ref": args.head_ref,
            "changed_files": [],
            "scanned_files": [],
            "skipped_files": [],
            "unsafe_findings": [],
            "protected_owner_findings": [],
            "status": "unknown",
            "reason_codes": [RC_SCAN_UNKNOWN, f"changed_files_resolution_error:{exc}"],
            "output_artifact_refs": [output_rel],
            "authority_scope": "observation_only",
        }
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": "unknown",
            "reason": "changed_files_resolution_error",
            "output": output_rel,
        }, indent=2))
        return _exit_code_for_status("unknown")

    owner_paths, _by_cluster = _load_owner_path_prefixes()

    payload = evaluate_authoring_check(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        output_artifact_ref=output_rel,
        owner_paths=owner_paths,
    )

    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": payload["status"],
        "scanned_file_count": payload["summary"]["scanned_file_count"],
        "unsafe_finding_count": payload["summary"]["unsafe_finding_count"],
        "protected_owner_finding_count": payload["summary"]["protected_owner_finding_count"],
        "reason_codes": payload["reason_codes"],
        "output": output_rel,
    }
    print(json.dumps(summary, indent=2))
    return _exit_code_for_status(str(payload["status"]))


if __name__ == "__main__":
    raise SystemExit(main())
