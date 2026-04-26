"""Run a HOP-003C controlled trial against the live transcript->FAQ eval set.

This script is the empirical validator for HOP Phase 1 (HOP-003C-004). It:

1. Loads the manifest-bound eval set from ``contracts/evals/hop``.
2. Wraps the deterministic baseline harness in a HOP candidate envelope.
3. Runs ``trial_runner.run_controlled_trial`` for the requested iteration count.
4. Persists the trial summary and surfaces a structured JSON report on stdout.

The script writes only to the supplied store root. It never mutates the eval
set, never bypasses the sandbox, and never claims release/advancement authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.hop import baseline_harness
from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.evaluator import load_eval_set_from_manifest
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from spectrum_systems.modules.hop.trial_runner import run_controlled_trial


def _build_baseline_candidate() -> dict[str, Any]:
    code_source = Path(baseline_harness.__file__).read_text(encoding="utf-8")
    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_candidate",
        "schema_ref": "hop/harness_candidate.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="hop_trial_runner_phase1"),
        "candidate_id": "baseline_v1",
        "harness_type": "transcript_to_faq",
        "code_module": "spectrum_systems.modules.hop.baseline_harness",
        "code_entrypoint": "run",
        "code_source": code_source,
        "declared_methods": ["run"],
        "parent_candidate_id": None,
        "tags": ["baseline"],
        "created_at": "2026-04-25T00:00:00.000000Z",
    }
    finalize_artifact(payload, id_prefix="hop_candidate_")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store-root",
        required=True,
        help="Directory the experience store will write under.",
    )
    parser.add_argument(
        "--manifest",
        default=str(REPO_ROOT / "contracts" / "evals" / "hop" / "manifest.json"),
        help="Path to the eval-set manifest.",
    )
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument(
        "--report-path",
        default=None,
        help="Optional file path to dump the trial summary JSON to.",
    )
    args = parser.parse_args()

    eval_set = load_eval_set_from_manifest(args.manifest)
    eval_cases = list(eval_set.cases)
    store = ExperienceStore(args.store_root)
    baseline_candidate = _build_baseline_candidate()
    try:
        store.write_artifact(baseline_candidate)
    except Exception as exc:  # noqa: BLE001
        if "duplicate_artifact" not in str(exc):
            raise

    summary = run_controlled_trial(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        store=store,
        iterations=args.iterations,
    )
    output = {
        "trial_summary": summary,
        "store_root": str(Path(args.store_root).resolve()),
        "manifest": str(Path(args.manifest).resolve()),
        "case_count": eval_set.case_count,
        "iterations": args.iterations,
    }
    if args.report_path:
        Path(args.report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_path).write_text(
            json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
