"""Mutation policy for HOP candidates.

The proposer can suggest a *bounded* set of changes to the harness
candidate:

**Allowed**:
- prompt structure changes (textual rewrites of the harness body);
- retrieval-logic changes (changing how/what is selected from the
  transcript);
- ordering / control-flow changes inside the harness;
- additive context (e.g. a deterministic preamble bootstrap).

**Forbidden** — any of these mark the candidate as
``mutation_policy_violation`` at severity ``reject``:
- editing eval cases (any path under ``contracts/evals/hop/``);
- editing schemas (any path under ``contracts/schemas/hop/``);
- editing the evaluator, validator, safety_checks, admission, frontier,
  experience_store, schemas, or proposer modules;
- removing required fields from the FAQ output;
- bypassing the evaluator (calling into the experience store directly,
  reading raw eval files, importing eval-case modules);
- injecting fixed outputs (hardcoding answer/question pairs);
- accessing hidden state (process env, the file system outside the
  candidate's own module, network);
- adding external calls without a contract (``urllib``, ``requests``,
  ``httpx``, ``socket``, ``subprocess``, ``os.system``, ``os.popen``).

The policy operates on two surfaces:

1. **changeset surface** — the diff between baseline and candidate
   ``code_source`` plus a list of modified file paths reported by the
   proposer. The policy refuses any modified path outside the
   candidate's own module file.
2. **structural surface** — a static AST scan of the candidate
   ``code_source`` looking for forbidden imports, calls, attribute
   reads, and string patterns.

Every violation is reported as a ``hop_harness_failure_hypothesis`` with
``stage = "mutation_policy"`` so downstream gates short-circuit just like
they do for safety violations.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

FORBIDDEN_PATH_PREFIXES: tuple[str, ...] = (
    "contracts/evals/hop/",
    "contracts/schemas/hop/",
    "spectrum_systems/modules/hop/evaluator.py",
    "spectrum_systems/modules/hop/validator.py",
    "spectrum_systems/modules/hop/safety_checks.py",
    "spectrum_systems/modules/hop/admission.py",
    "spectrum_systems/modules/hop/frontier.py",
    "spectrum_systems/modules/hop/experience_store.py",
    "spectrum_systems/modules/hop/schemas.py",
    "spectrum_systems/modules/hop/proposer.py",
    "spectrum_systems/modules/hop/mutation_policy.py",
    "spectrum_systems/modules/hop/optimization_loop.py",
    "spectrum_systems/modules/hop/failure_analysis.py",
    "spectrum_systems/modules/hop/trace_diff.py",
    "spectrum_systems/modules/hop/artifacts.py",
    "spectrum_systems/modules/hop/sandbox.py",
    "spectrum_systems/modules/hop/bootstrap.py",
    "spectrum_systems/modules/hop/trial_runner.py",
    "spectrum_systems/modules/hop/patterns/",
)

FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {
        "urllib",
        "urllib.request",
        "urllib.parse",
        "urllib.error",
        "requests",
        "httpx",
        "socket",
        "subprocess",
        "ctypes",
        "spectrum_systems.modules.hop.evaluator",
        "spectrum_systems.modules.hop.experience_store",
        "spectrum_systems.modules.hop.safety_checks",
        "spectrum_systems.modules.hop.validator",
        "spectrum_systems.modules.hop.admission",
        "spectrum_systems.modules.hop.frontier",
        "spectrum_systems.modules.hop.proposer",
        "spectrum_systems.modules.hop.mutation_policy",
        "spectrum_systems.modules.hop.optimization_loop",
        "spectrum_systems.modules.hop.failure_analysis",
        "spectrum_systems.modules.hop.trace_diff",
        "spectrum_systems.modules.hop.sandbox",
        "spectrum_systems.modules.hop.bootstrap",
        "spectrum_systems.modules.hop.trial_runner",
        "spectrum_systems.modules.hop.patterns",
    }
)

# Modules whose surface is allowed because the harness needs them and they
# do not expose decision/orchestration/persistence authority.
ALLOWED_SAFE_IMPORTS: frozenset[str] = frozenset(
    {
        "spectrum_systems.modules.hop.artifacts",
        "spectrum_systems.modules.hop.baseline_harness",
    }
)

FORBIDDEN_CALL_PATTERNS: tuple[str, ...] = (
    "os.system",
    "os.popen",
    "os.exec",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "socket.socket",
    "eval(",
    "exec(",
    "compile(",
    "__import__",
    "globals()",
    "open(",
)

FORBIDDEN_CALL_PATTERN_EXCEPTIONS: tuple[str, ...] = (
    # The candidate is allowed to read its own input; no forbidden pattern
    # below is exempted in BATCH-2 — exceptions are listed here explicitly so
    # any future relaxation is auditable.
)

REQUIRED_FAQ_OUTPUT_FIELDS: tuple[str, ...] = (
    "items",
    "transcript_id",
    "candidate_id",
)

_FORBIDDEN_FIELD_REMOVAL_RE = re.compile(
    r"\bdel\s+(?:[A-Za-z_][A-Za-z_0-9]*\.)?(?:items|transcript_id|candidate_id)\b"
)


class MutationPolicyError(Exception):
    """Raised when the policy itself cannot be evaluated (parse error)."""


@dataclass(frozen=True)
class MutationProposal:
    """Describes the changeset the proposer is asking to admit.

    ``modified_paths`` MUST be the proposer's declared list of repo-relative
    paths it intends to write. The candidate's own module file is the only
    allowed path. ``baseline_code_source`` is used to detect *removal* of
    required fields from the FAQ output emission site.
    """

    candidate_id: str
    candidate_code_source: str
    candidate_module_path: str
    baseline_code_source: str
    modified_paths: tuple[str, ...]
    mutation_kind: str


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _build_failure(
    *,
    candidate_id: str,
    failure_class: str,
    evidence: list[dict[str, str]],
    trace_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_failure_hypothesis",
        "schema_ref": "hop/harness_failure_hypothesis.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "hypothesis_id": f"mp_{failure_class}_{candidate_id}",
        "candidate_id": candidate_id,
        "run_id": None,
        "stage": "mutation_policy",
        "failure_class": failure_class,
        "severity": "reject",
        "evidence": evidence,
        "detected_at": _utcnow(),
        "blocks_promotion": True,
    }
    finalize_artifact(payload, id_prefix="hop_failure_")
    return payload


def _check_modified_paths(
    proposal: MutationProposal, *, trace_id: str
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    allowed = {proposal.candidate_module_path}
    illegal: list[str] = []
    for path in proposal.modified_paths:
        normalized = path.replace("\\", "/")
        if normalized in allowed:
            continue
        for forbidden in FORBIDDEN_PATH_PREFIXES:
            if normalized == forbidden or normalized.startswith(forbidden):
                illegal.append(normalized)
                break
        else:
            # Any path outside the candidate's own module is rejected; the
            # proposer's only legitimate write surface is its candidate file.
            illegal.append(normalized)
    if illegal:
        failures.append(
            _build_failure(
                candidate_id=proposal.candidate_id,
                failure_class="mutation_policy_violation",
                evidence=[
                    {
                        "kind": "code_path",
                        "detail": "illegal_modified_paths=" + ",".join(sorted(set(illegal))),
                    }
                ],
                trace_id=trace_id,
            )
        )
    return failures


def _ast_scan(
    proposal: MutationProposal, *, trace_id: str
) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(proposal.candidate_code_source)
    except SyntaxError as exc:
        return [
            _build_failure(
                candidate_id=proposal.candidate_id,
                failure_class="mutation_policy_violation",
                evidence=[
                    {"kind": "exception", "detail": f"SyntaxError:{exc}"},
                ],
                trace_id=trace_id,
            )
        ]

    failures: list[dict[str, Any]] = []
    forbidden_imports_seen: set[str] = set()
    forbidden_calls_seen: set[str] = set()
    forbidden_attr_paths_seen: set[str] = set()
    accesses_env: bool = False
    accesses_filesystem_root: bool = False
    accesses_eval_dir: bool = False

    def _full_attr_name(node: ast.AST) -> str | None:
        parts: list[str] = []
        cur: ast.AST | None = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name in FORBIDDEN_IMPORTS or any(
                    name.startswith(p + ".") for p in FORBIDDEN_IMPORTS
                ):
                    forbidden_imports_seen.add(name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in FORBIDDEN_IMPORTS or any(
                module.startswith(p + ".") for p in FORBIDDEN_IMPORTS
            ):
                forbidden_imports_seen.add(module)
            for alias in node.names:
                qualified = f"{module}.{alias.name}" if module else alias.name
                if qualified in FORBIDDEN_IMPORTS:
                    forbidden_imports_seen.add(qualified)
        elif isinstance(node, ast.Call):
            target = _full_attr_name(node.func) if isinstance(node.func, ast.Attribute) else None
            if target is None and isinstance(node.func, ast.Name):
                target = node.func.id
            if target in {"eval", "exec", "compile", "__import__", "open", "globals"}:
                forbidden_calls_seen.add(target)
            elif target and (
                target.startswith("os.system")
                or target.startswith("os.popen")
                or target.startswith("os.exec")
                or target.startswith("subprocess.")
                or target.startswith("socket.")
                or target.startswith("ctypes.")
            ):
                forbidden_calls_seen.add(target)
            # Detect direct write paths back into the experience store.
            if target and target.startswith("ExperienceStore"):
                forbidden_calls_seen.add(target)
            if target == "ExperienceStore.write_artifact":
                forbidden_calls_seen.add(target)
        elif isinstance(node, ast.Attribute):
            full = _full_attr_name(node)
            if full is None:
                continue
            if full.startswith("os.environ"):
                accesses_env = True
            if full == "os.environ":
                accesses_env = True
            if full.startswith("sys.argv"):
                accesses_env = True
            if full.startswith("ExperienceStore"):
                forbidden_attr_paths_seen.add(full)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if "/etc/" in value or value.startswith("/"):
                if value.startswith("/tmp"):  # noqa: S108 - flagged below
                    accesses_filesystem_root = True
                else:
                    accesses_filesystem_root = True
            if "contracts/evals/hop" in value:
                accesses_eval_dir = True

    if forbidden_imports_seen:
        failures.append(
            _build_failure(
                candidate_id=proposal.candidate_id,
                failure_class="mutation_policy_violation",
                evidence=[
                    {
                        "kind": "code_path",
                        "detail": "forbidden_imports="
                        + ",".join(sorted(forbidden_imports_seen)),
                    }
                ],
                trace_id=trace_id,
            )
        )
    if forbidden_calls_seen:
        failures.append(
            _build_failure(
                candidate_id=proposal.candidate_id,
                failure_class="mutation_policy_violation",
                evidence=[
                    {
                        "kind": "code_path",
                        "detail": "forbidden_calls="
                        + ",".join(sorted(forbidden_calls_seen)),
                    }
                ],
                trace_id=trace_id,
            )
        )
    if forbidden_attr_paths_seen:
        failures.append(
            _build_failure(
                candidate_id=proposal.candidate_id,
                failure_class="mutation_policy_violation",
                evidence=[
                    {
                        "kind": "code_path",
                        "detail": "forbidden_attribute_access="
                        + ",".join(sorted(forbidden_attr_paths_seen)),
                    }
                ],
                trace_id=trace_id,
            )
        )
    if accesses_env:
        failures.append(
            _build_failure(
                candidate_id=proposal.candidate_id,
                failure_class="mutation_policy_violation",
                evidence=[
                    {
                        "kind": "code_path",
                        "detail": "hidden_state=os.environ_or_sys.argv",
                    }
                ],
                trace_id=trace_id,
            )
        )
    if accesses_filesystem_root:
        failures.append(
            _build_failure(
                candidate_id=proposal.candidate_id,
                failure_class="mutation_policy_violation",
                evidence=[
                    {
                        "kind": "code_path",
                        "detail": "absolute_filesystem_path_in_source",
                    }
                ],
                trace_id=trace_id,
            )
        )
    if accesses_eval_dir:
        failures.append(
            _build_failure(
                candidate_id=proposal.candidate_id,
                failure_class="mutation_policy_violation",
                evidence=[
                    {
                        "kind": "code_path",
                        "detail": "literal_eval_directory_reference",
                    }
                ],
                trace_id=trace_id,
            )
        )

    return failures


def _check_required_field_removal(
    proposal: MutationProposal, *, trace_id: str
) -> list[dict[str, Any]]:
    """Reject candidates whose source actively *removes* a required FAQ field.

    A purely-structural check: we look for ``del payload.<field>``,
    ``payload.pop("<field>")``, or ``payload.pop('<field>')`` patterns for
    any of ``REQUIRED_FAQ_OUTPUT_FIELDS``. The evaluator's schema check is
    the authoritative gate, but intercepting at policy time avoids burning
    an evaluation on a candidate that will fail-closed anyway.
    """
    failures: list[dict[str, Any]] = []
    code = proposal.candidate_code_source
    illegal: list[str] = []
    for field in REQUIRED_FAQ_OUTPUT_FIELDS:
        if re.search(rf'\.pop\(\s*["\']{field}["\']\s*\)', code):
            illegal.append(f"pop:{field}")
        if re.search(rf"\bdel\b\s+\w+\[['\"]{field}['\"]\]", code):
            illegal.append(f"del_index:{field}")
    if _FORBIDDEN_FIELD_REMOVAL_RE.search(code):
        illegal.append("del_attr:required_field")
    if illegal:
        failures.append(
            _build_failure(
                candidate_id=proposal.candidate_id,
                failure_class="mutation_policy_violation",
                evidence=[
                    {
                        "kind": "code_path",
                        "detail": "removed_required_fields=" + ",".join(sorted(set(illegal))),
                    }
                ],
                trace_id=trace_id,
            )
        )
    return failures


def evaluate_proposal(
    proposal: MutationProposal,
    *,
    trace_id: str = "hop_mutation_policy",
) -> tuple[bool, list[dict[str, Any]]]:
    """Run the full mutation-policy chain.

    Returns ``(ok, failures)``. ``ok`` is True only when every check
    passes. ``failures`` is the list of structured failure hypotheses
    (never None, possibly empty).
    """
    if not isinstance(proposal, MutationProposal):
        raise MutationPolicyError("hop_mutation_policy_invalid_proposal")

    failures: list[dict[str, Any]] = []
    failures.extend(_check_modified_paths(proposal, trace_id=trace_id))
    failures.extend(_ast_scan(proposal, trace_id=trace_id))
    failures.extend(_check_required_field_removal(proposal, trace_id=trace_id))
    return not failures, failures


def list_allowed_mutation_kinds() -> tuple[str, ...]:
    """The whitelist of mutation kinds the proposer may declare.

    These are descriptive labels carried on the proposal; they do not
    relax any structural check. The optimization loop uses them for
    artifact tagging (``parent_candidate_id`` lineage + ``tags``).
    """
    return (
        "additive_context",
        "ordering",
        "retrieval_logic",
        "prompt_structure",
    )
