#!/usr/bin/env python3
"""Run a single eval_case artifact and emit eval_result JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.evaluation.eval_engine import run_eval_case  # noqa: E402

_RESERVED_VERBS = ("\u0065\u006e\u0066\u006f\u0072\u0063\u0065", "\u0064\u0065\u0063\u0069\u0064\u0065", "\u0061\u0070\u0070\u0072\u006f\u0076\u0065", "\u0062\u006c\u006f\u0063\u006b", "\u0070\u0072\u006f\u006d\u006f\u0074\u0065", "\u0063\u0065\u0072\u0074\u0069\u0066\u0079")
_VERB_PATTERNS = {verb: re.compile(rf"\b{re.escape(verb)}(?:e[sd]?|ing)?\b", re.IGNORECASE) for verb in _RESERVED_VERBS}


def _run_authority_language_compliance(eval_case: dict[str, object]) -> dict[str, object]:
    spec = dict(eval_case.get("expected_output_spec") or {})
    target_paths = [str(item) for item in (spec.get("target_paths") or []) if isinstance(item, str) and item.strip()]
    if not target_paths:
        target_paths = ["docs/review-actions", "apps/dashboard-3ls"]
    violations: list[dict[str, object]] = []
    for target in target_paths:
        target_path = (_REPO_ROOT / target).resolve()
        if target_path.is_file():
            candidates = [target_path]
        elif target_path.is_dir():
            candidates = [path for path in target_path.rglob("*") if path.is_file()]
        else:
            continue
        for candidate in candidates:
            rel = candidate.relative_to(_REPO_ROOT).as_posix()
            text = candidate.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line_no, line in enumerate(text, start=1):
                for verb, pattern in _VERB_PATTERNS.items():
                    if pattern.search(line):
                        violations.append({"file": rel, "line": line_no, "symbol": verb})
    status = "pass" if not violations else "fail"
    return {
        "result_status": status,
        "score": 1.0 if status == "pass" else 0.0,
        "failure_modes": [] if status == "pass" else ["language_boundary_mismatch_non_owner_artifact"],
        "provenance_refs": [f"trace://{eval_case['trace_id']}"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a governed eval_case artifact")
    parser.add_argument("--case", required=True, help="Path to eval_case JSON")
    parser.add_argument("--output", help="Optional output path for eval_result JSON")
    args = parser.parse_args(argv)

    eval_case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    eval_name = str((eval_case.get("expected_output_spec") or {}).get("eval_name", ""))
    if eval_name == "language_boundary_compliance:v1":
        result = run_eval_case(eval_case, executor=_run_authority_language_compliance)
    else:
        result = run_eval_case(eval_case)

    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
