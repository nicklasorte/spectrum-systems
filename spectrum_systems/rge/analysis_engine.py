"""RGE Analysis Engine - Wave 0 repo audit.

Scans the repository to build a snapshot of its current state. The snapshot
drives Principle 1 (where is complexity?) and Principle 2 (where is drift?)
decisions downstream in the roadmap generator.

Emits: rge_analysis_record (schema_version 1.1.0)

Measured signals:
  - context_maturity_level: 0-10 based on presence of key runtime modules
  - wave_status: 0-4 SBGE wave, derived from indicator-file presence
  - active_drift_legs: from loop_contribution_checker.get_active_drift_legs
  - complexity_budget_by_module: per-module burn rate
  - mg_slice_health: which meta-governance slices are present
  - fragile_points: caller-supplied module paths flagged as fragile
  - fragile_point_signals: AST-derived stub/silent-except findings
  - entropy_vectors: 7-vector assessment (clean | warn | critical)
  - rge_can_operate / rge_max_autonomy: autonomy gate derived from maturity
  - bottlenecks: loop legs with saturation >= 6 contributors
"""
from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.rge.loop_contribution_checker import (
    get_active_drift_legs,
)

CANONICAL_LOOP_LEGS = (
    "AEX", "PQX", "EVL", "TPA", "CDE", "SEL",
    "REP", "LIN", "OBS", "SLO",
)

_KEY_MODULES = (
    ("aex", "spectrum_systems/aex"),
    ("pqx", "spectrum_systems/exec_system"),
    ("evl", "spectrum_systems/eval_system"),
    ("tpa", "spectrum_systems/modules/runtime/tpa_complexity_governance.py"),
    ("cde", "spectrum_systems/govern"),
    ("sel", "spectrum_systems/security"),
    ("rep", "spectrum_systems/tracing"),
    ("lin", "spectrum_systems/artifact_store"),
    ("obs", "spectrum_systems/observability"),
    ("slo", "spectrum_systems/modules/runtime/autonomy_guardrails.py"),
)

# SBGE wave indicators: wave N is active iff the indicator path exists.
# Waves are cumulative; the reported wave is the highest present.
_WAVE_INDICATORS: tuple[tuple[int, str], ...] = (
    (0, "spectrum_systems/__init__.py"),
    (1, "contracts/schemas"),
    (2, "spectrum_systems/modules/runtime/continuous_governance.py"),
    (3, "spectrum_systems/modules/runtime/full_autonomy_execution.py"),
    (4, "spectrum_systems/rge/orchestrator.py"),
)

_RGE_OPERATE_MIN_MATURITY = 7
_AUTONOMY_WARN_GATED_MIN_MATURITY = 9
_AUTONOMY_AUTONOMOUS_MIN_MATURITY = 10
_AST_SCAN_FILE_CAP = 40
_STUB_HEAVY_THRESHOLD = 3
_SILENT_EXCEPT_THRESHOLD = 2


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"RAR-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def _measure_context_maturity(repo_root: Path) -> tuple[int, list[str]]:
    present: list[str] = []
    for label, rel_path in _KEY_MODULES:
        if (repo_root / rel_path).exists():
            present.append(label)
    return len(present), present


def _measure_wave(repo_root: Path) -> int:
    """Return the highest SBGE wave whose indicator exists."""
    wave = 0
    for w, indicator in _WAVE_INDICATORS:
        if (repo_root / indicator).exists():
            wave = w
    return wave


def _count_stubs(source: str) -> int:
    """Count functions whose entire body is a single `pass`."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                count += 1
    return count


def _count_silent_excepts(source: str) -> int:
    """Count except handlers whose body is only pass or a bare ellipsis."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        body = node.body
        if not body:
            continue
        if all(_is_silent_statement(stmt) for stmt in body):
            count += 1
    return count


def _is_silent_statement(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr):
        value = stmt.value
        if isinstance(value, ast.Constant) and value.value is Ellipsis:
            return True
    return False


def _audit_fragile_point_signals(runtime_dir: Path) -> list[dict[str, Any]]:
    """Scan `runtime_dir` for stub-heavy and silent-except modules.

    Returns a list of {type, file, count} dicts. Only Python files are
    examined. Caps scan at `_AST_SCAN_FILE_CAP` to keep the audit bounded.
    """
    signals: list[dict[str, Any]] = []
    if not runtime_dir.exists() or not runtime_dir.is_dir():
        return signals
    files = sorted(runtime_dir.glob("*.py"))[:_AST_SCAN_FILE_CAP]
    for py_file in files:
        try:
            source = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        stubs = _count_stubs(source)
        silent = _count_silent_excepts(source)
        if stubs > _STUB_HEAVY_THRESHOLD:
            signals.append({
                "type": "stub_heavy",
                "file": py_file.name,
                "count": stubs,
            })
        if silent > _SILENT_EXCEPT_THRESHOLD:
            signals.append({
                "type": "silent_excepts",
                "file": py_file.name,
                "count": silent,
            })
    return signals


def _assess_entropy_vectors(
    *,
    maturity_level: int,
    active_drift_legs: list[str],
    fragile_point_signals: list[dict[str, Any]],
) -> dict[str, str]:
    stub_heavy = sum(1 for s in fragile_point_signals if s.get("type") == "stub_heavy")
    silent = sum(1 for s in fragile_point_signals if s.get("type") == "silent_excepts")
    return {
        "decision_entropy":       "warn" if maturity_level < 7 else "clean",
        "silent_drift":           "warn" if active_drift_legs else "clean",
        "exception_accumulation": "warn" if silent > 5 else "clean",
        "hidden_logic_creep":     "warn" if stub_heavy > 3 else "clean",
        "evaluation_blind_spots": "warn" if maturity_level < 5 else "clean",
        "overconfidence_risk":    "warn" if maturity_level < 9 else "clean",
        "loss_of_causality":      "warn" if maturity_level < 6 else "clean",
    }


def _derive_autonomy(maturity_level: int) -> tuple[bool, str]:
    """Derive (rge_can_operate, rge_max_autonomy) from maturity."""
    can_operate = maturity_level >= _RGE_OPERATE_MIN_MATURITY
    if maturity_level < _AUTONOMY_WARN_GATED_MIN_MATURITY:
        mode = "shadow"
    elif maturity_level < _AUTONOMY_AUTONOMOUS_MIN_MATURITY:
        mode = "warn_gated"
    else:
        mode = "autonomous"
    return can_operate, mode


def _default_leg_counts(repo_root: Path) -> dict[str, int]:
    """Best-effort per-leg contributor count from the filesystem.

    We count non-dunder `.py` files in the relevant module directory. This is
    a signal, not a source of truth; the caller can override.
    """
    counts: dict[str, int] = {leg: 0 for leg in CANONICAL_LOOP_LEGS}
    dir_map = {
        "AEX": "spectrum_systems/aex",
        "PQX": "spectrum_systems/exec_system",
        "EVL": "spectrum_systems/eval_system",
        "TPA": "spectrum_systems/modules/runtime",
        "CDE": "spectrum_systems/govern",
        "SEL": "spectrum_systems/security",
        "REP": "spectrum_systems/tracing",
        "LIN": "spectrum_systems/artifact_store",
        "OBS": "spectrum_systems/observability",
        "SLO": "spectrum_systems/modules/runtime",
    }
    for leg, rel in dir_map.items():
        path = repo_root / rel
        if not path.exists() or not path.is_dir():
            continue
        counts[leg] = sum(
            1
            for p in path.glob("*.py")
            if not p.name.startswith("_")
        )
    return counts


def analyze_repository(
    *,
    repo_root: str | Path,
    run_id: str,
    trace_id: str,
    roadmap_signal_bundle: dict[str, Any] | None = None,
    complexity_budgets: list[dict[str, Any]] | None = None,
    fragile_points: list[str] | None = None,
    mg_slices_present: list[str] | None = None,
) -> dict[str, Any]:
    """Produce an rge_analysis_record for the given repo state.

    Args:
        repo_root: path to the repo root
        run_id, trace_id: lineage identifiers
        roadmap_signal_bundle: optional steering bundle; drift extracted from it
        complexity_budgets: optional list of complexity_budget artifacts
        fragile_points: optional list of module paths flagged as fragile
        mg_slices_present: optional list of MG-## slice IDs currently wired

    Returns:
        schema-validated rge_analysis_record
    """
    root = Path(repo_root).resolve()

    maturity, present = _measure_context_maturity(root)
    wave_status = _measure_wave(root)
    drift_legs = get_active_drift_legs(roadmap_signal_bundle) if roadmap_signal_bundle else []
    leg_counts = _default_leg_counts(root)

    budgets_by_module: dict[str, dict[str, Any]] = {}
    for budget in complexity_budgets or []:
        module = str(budget.get("module_or_path", "unknown"))
        budgets_by_module[module] = {
            "budget_status": budget.get("budget_status"),
            "burn_rate": budget.get("burn_rate"),
            "current_complexity": budget.get("current_complexity"),
            "baseline_complexity": budget.get("baseline_complexity"),
        }

    bottlenecks = sorted(
        leg for leg, count in leg_counts.items() if count >= 6
    )

    fragile_point_signals = _audit_fragile_point_signals(
        root / "spectrum_systems" / "modules" / "runtime"
    )

    drift_legs_sorted = sorted(drift_legs)
    entropy_vectors = _assess_entropy_vectors(
        maturity_level=maturity,
        active_drift_legs=drift_legs_sorted,
        fragile_point_signals=fragile_point_signals,
    )
    can_operate, max_autonomy = _derive_autonomy(maturity)

    record = {
        "artifact_type": "rge_analysis_record",
        "schema_version": "1.1.0",
        "record_id": _stable_id({"run_id": run_id, "trace_id": trace_id}),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "repo_root": str(root),
        "context_maturity_level": maturity,
        "context_maturity_max": len(_KEY_MODULES),
        "modules_present": sorted(present),
        "wave_status": wave_status,
        "active_drift_legs": drift_legs_sorted,
        "complexity_budget_by_module": budgets_by_module,
        "mg_slice_health": {
            "present": sorted(set(mg_slices_present or [])),
            "missing": [],
        },
        "fragile_points": sorted(set(fragile_points or [])),
        "fragile_point_signals": fragile_point_signals,
        "bottlenecks": bottlenecks,
        "leg_saturation": leg_counts,
        "entropy_vectors": entropy_vectors,
        "rge_can_operate": can_operate,
        "rge_max_autonomy": max_autonomy,
    }

    validate_artifact(record, "rge_analysis_record")
    return record
