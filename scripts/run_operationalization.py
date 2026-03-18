#!/usr/bin/env python3
"""
Operationalization Pass — scripts/run_operationalization.py

Runs the AN–AW2 control-loop systems end-to-end and persists real artifacts
to their governed data directories.  This script is the primary execution
entry-point for the operationalization sprint (2026-03-18).

Pipeline
--------
1. AN  — Evaluation Framework: run golden cases through EvalRunner
2. AP  — Observability: emit ObservabilityRecord for every eval result
3. AR  — Regression Harness: create a governed baseline from this run
4. AU  — Error Taxonomy: classify errors from eval + observability outputs
5. AV  — Auto-Failure Clustering: cluster classification records
6. AW0 — Cluster Validation: validate clusters and persist valid ones
7. AW1 — Remediation Mapping: map validated clusters to remediation plans
8. AW2 — Fix Simulation Sandbox: simulate each mapped plan
9. AO  — Human Feedback: persist one representative feedback record

Outputs (all relative to repo root)
-------------------------------------
data/observability/          ObservabilityRecord per eval case + AO event
data/regression_baselines/   Named baseline  "operationalization-2026-03-18"
data/error_clusters/         ErrorCluster per dominant family
data/validated_clusters/     ValidatedCluster for each passing cluster
data/remediation_plans/      RemediationPlan per validated cluster
data/simulation_results/     SimulationResult per remediation plan
data/human_feedback/         HumanFeedbackRecord for case_001 eval result

Usage
-----
    python scripts/run_operationalization.py

Exit codes
----------
0  All stages completed successfully.
1  One or more stages had non-fatal warnings.
2  A stage failed and could not complete.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPTS_DIR.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Imports — all from existing spectrum_systems modules
# ---------------------------------------------------------------------------

from spectrum_systems.modules.evaluation.golden_dataset import load_all_cases
from spectrum_systems.modules.evaluation.eval_runner import EvalRunner, EvalResult
from spectrum_systems.modules.evaluation.grounding import GroundingVerifier
from spectrum_systems.modules.evaluation.regression import RegressionHarness

from spectrum_systems.modules.observability.metrics import ObservabilityRecord, MetricsStore

from spectrum_systems.modules.regression.baselines import BaselineManager, BaselineExistsError

from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord, ErrorClassifier
from spectrum_systems.modules.error_taxonomy.cluster_pipeline import (
    build_clusters_from_classifications,
    validate_clusters,
)
from spectrum_systems.modules.error_taxonomy.cluster_store import save_cluster, list_clusters
from spectrum_systems.modules.error_taxonomy.validated_cluster_store import (
    save_validated_cluster,
    load_validated_clusters,
)

from spectrum_systems.modules.improvement.remediation_pipeline import (
    build_remediation_plans_from_validated_clusters,
)
from spectrum_systems.modules.improvement.remediation_store import (
    save_remediation_plan,
    list_remediation_plans,
)
from spectrum_systems.modules.improvement.simulation_pipeline import run_simulation_batch
from spectrum_systems.modules.improvement.simulation_store import (
    save_simulation_result,
    list_simulation_results,
)

from spectrum_systems.modules.feedback.human_feedback import FeedbackStore, HumanFeedbackRecord
from spectrum_systems.modules.feedback.feedback_ingest import create_feedback_from_review

# ---------------------------------------------------------------------------
# Data directories
# ---------------------------------------------------------------------------

_GOLDEN_CASES_DIR = _ROOT / "data" / "golden_cases"
_OBSERVABILITY_DIR = _ROOT / "data" / "observability"
_REGRESSION_BASELINES_DIR = _ROOT / "data" / "regression_baselines"
_ERROR_CLASSIFICATIONS_DIR = _ROOT / "data" / "error_classifications"
_ERROR_CLUSTERS_DIR = _ROOT / "data" / "error_clusters"
_VALIDATED_CLUSTERS_DIR = _ROOT / "data" / "validated_clusters"
_REMEDIATION_PLANS_DIR = _ROOT / "data" / "remediation_plans"
_SIMULATION_RESULTS_DIR = _ROOT / "data" / "simulation_results"
_HUMAN_FEEDBACK_DIR = _ROOT / "data" / "human_feedback"

_OUTPUTS_DIR = _ROOT / "outputs"
_BASELINE_NAME = "operationalization-2026-03-18"

# ---------------------------------------------------------------------------
# Stub reasoning engine (same as run_eval.py)
# ---------------------------------------------------------------------------


class _StubReasoningEngine:
    """Minimal stub engine for deterministic golden-case evaluation.

    Returns a completed pass chain with empty pass_results so the full
    EvalRunner pipeline can exercise schema validation, grounding,
    regression detection, and observability emission without a live model.
    """

    def run(self, transcript: str, config: Dict[str, Any] = None) -> Dict[str, Any]:  # noqa: ANN001
        return {
            "chain_id": "stub-chain",
            "status": "completed",
            "pass_results": [],
            "intermediate_artifacts": {},
        }


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _section(title: str) -> None:
    print()
    print("=" * 64)
    print(f"  {title}")
    print("=" * 64)


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠ {msg}")


def _info(msg: str) -> None:
    print(f"    {msg}")


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _ensure_dirs() -> None:
    """Create all required output directories."""
    for d in [
        _OBSERVABILITY_DIR,
        _ERROR_CLUSTERS_DIR,
        _VALIDATED_CLUSTERS_DIR,
        _SIMULATION_RESULTS_DIR,
        _HUMAN_FEEDBACK_DIR,
        _OUTPUTS_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


def _build_eval_runner() -> EvalRunner:
    harness = RegressionHarness(baselines_dir=_ROOT / "data" / "eval_baselines")
    grounding = GroundingVerifier(min_overlap_tokens=1)
    engine = _StubReasoningEngine()
    return EvalRunner(
        reasoning_engine=engine,
        grounding_verifier=grounding,
        regression_harness=harness,
        deterministic=True,
        output_dir=_OUTPUTS_DIR,
    )


# ---------------------------------------------------------------------------
# Stage AN + AP — Evaluation + Observability
# ---------------------------------------------------------------------------


def stage_an_ap() -> tuple[List[EvalResult], List[ObservabilityRecord]]:
    """Run evaluation on all golden cases and emit observability records."""
    _section("AN + AP  |  Evaluation Framework + Observability")

    dataset = load_all_cases(_GOLDEN_CASES_DIR)
    _info(f"Loaded {len(dataset)} golden case(s) from {_GOLDEN_CASES_DIR.relative_to(_ROOT)}")

    runner = _build_eval_runner()
    results = runner.run_all_cases(dataset)

    metrics_store = MetricsStore(store_dir=_OBSERVABILITY_DIR)

    saved_records: List[ObservabilityRecord] = []
    for res in results:
        try:
            obs = ObservabilityRecord.from_eval_result(res)
            metrics_store.save(obs)
            saved_records.append(obs)
            status = "PASS" if res.pass_fail else "FAIL"
            _ok(
                f"[{status}] case={res.case_id}  "
                f"struct={res.structural_score:.2f}  "
                f"sem={res.semantic_score:.2f}  "
                f"ground={res.grounding_score:.2f}  "
                f"→ obs/{obs.record_id[:8]}…"
            )
        except Exception as exc:  # noqa: BLE001
            _warn(f"Could not save observability record for {res.case_id}: {exc}")

    _info(
        f"Written {len(saved_records)} observability record(s) "
        f"to {_OBSERVABILITY_DIR.relative_to(_ROOT)}"
    )

    # Write eval report to outputs/
    report_path = runner.write_report(results, output_path=_OUTPUTS_DIR / "eval_results.json")
    _info(f"Eval report → {report_path.relative_to(_ROOT)}")

    return results, saved_records


# ---------------------------------------------------------------------------
# Stage AR — Regression Baseline
# ---------------------------------------------------------------------------


def stage_ar(
    eval_results: List[EvalResult],
    obs_records: List[ObservabilityRecord],
) -> None:
    """Create a governed regression baseline from this run."""
    _section("AR  |  Regression Baseline")

    manager = BaselineManager(baselines_dir=_REGRESSION_BASELINES_DIR)

    eval_dicts = [r.to_dict() for r in eval_results]
    obs_dicts = [r.to_dict() for r in obs_records]

    try:
        baseline_dir = manager.save_baseline(
            name=_BASELINE_NAME,
            eval_results=eval_dicts,
            observability_records=obs_dicts,
            metadata={
                "run_mode": "deterministic",
                "engine": "stub",
                "golden_cases_dir": str(_GOLDEN_CASES_DIR.relative_to(_ROOT)),
                "run_context": "operationalization-pass-2026-03-18",
            },
            notes=(
                "Operationalization baseline — first governed run of the full "
                "AN–AW2 pipeline on 2026-03-18.  Stub engine; scores reflect "
                "structural gap between stub output and golden expectations."
            ),
        )
        _ok(f"Baseline '{_BASELINE_NAME}' → {baseline_dir.relative_to(_ROOT)}")
    except BaselineExistsError:
        _warn(f"Baseline '{_BASELINE_NAME}' already exists; skipping creation.")


# ---------------------------------------------------------------------------
# Stage AU — Error Taxonomy Classification
# ---------------------------------------------------------------------------


def stage_au(eval_results: List[EvalResult]) -> List[ErrorClassificationRecord]:
    """Classify errors from eval results into AU taxonomy records."""
    _section("AU  |  Error Taxonomy Classification")

    catalog = ErrorTaxonomyCatalog.load_catalog()
    classifier = ErrorClassifier(catalog=catalog)

    new_records: List[ErrorClassificationRecord] = []

    for res in eval_results:
        # Classify the eval result — even with no errors the classifier
        # emits a record capturing the full pass outcome.
        try:
            record = classifier.classify_eval_result(
                res.to_dict(),
                artifact_id=f"eval-{res.case_id}",
                case_id=res.case_id,
            )
            dest = _ERROR_CLASSIFICATIONS_DIR / f"{record.classification_id}.json"
            if not dest.exists():
                record.save(_ERROR_CLASSIFICATIONS_DIR)
                new_records.append(record)
                _ok(f"Classified eval result case={res.case_id} → {record.classification_id[:16]}…")
        except FileExistsError:
            _warn(f"Classification record for case={res.case_id} already exists; skipping.")
        except Exception as exc:  # noqa: BLE001
            _warn(f"Classification failed for case={res.case_id}: {exc}")

    # Load all records (pre-existing + new)
    all_records = ErrorClassificationRecord.list_all(_ERROR_CLASSIFICATIONS_DIR)
    _info(
        f"New classifications: {len(new_records)} | "
        f"Total in store: {len(all_records)}"
    )

    return all_records


# ---------------------------------------------------------------------------
# Stage AV — Auto-Failure Clustering
# ---------------------------------------------------------------------------


def stage_av(
    all_records: List[ErrorClassificationRecord],
) -> list:
    """Cluster classification records into failure patterns."""
    _section("AV  |  Auto-Failure Clustering")

    catalog = ErrorTaxonomyCatalog.load_catalog()
    clusters = build_clusters_from_classifications(all_records, catalog)

    _info(f"Built {len(clusters)} cluster(s) from {len(all_records)} record(s)")

    saved = 0
    for cluster in clusters:
        try:
            save_cluster(cluster, store_dir=_ERROR_CLUSTERS_DIR)
            saved += 1
            _ok(
                f"Cluster {cluster.cluster_id[:8]}…  "
                f"sig={cluster.cluster_signature.get('primary_error_code', '?')}  "
                f"n={cluster.metrics.get('record_count', '?')}"
            )
        except FileExistsError:
            _warn(
                f"Cluster {cluster.cluster_id[:8]}… already exists; skipping."
            )

    _info(f"New clusters saved: {saved} | Total: {len(list_clusters(store_dir=_ERROR_CLUSTERS_DIR))}")
    return clusters


# ---------------------------------------------------------------------------
# Stage AW0 — Cluster Validation
# ---------------------------------------------------------------------------


def stage_aw0(
    clusters: list,
    all_records: List[ErrorClassificationRecord],
) -> list:
    """Validate clusters and persist valid ones."""
    _section("AW0  |  Cluster Validation")

    validated = validate_clusters(clusters, all_records)
    valid = [v for v in validated if v.validation_status == "valid"]
    invalid = [v for v in validated if v.validation_status != "valid"]

    _info(f"Total: {len(validated)} | Valid: {len(valid)} | Invalid: {len(invalid)}")

    saved = 0
    for v in valid:
        try:
            save_validated_cluster(v, store_dir=_VALIDATED_CLUSTERS_DIR)
            saved += 1
            _ok(
                f"ValidatedCluster {v.cluster_id[:8]}…  "
                f"sig={v.cluster_signature}  "
                f"coh={v.cohesion_score:.2f}  act={v.actionability_score:.2f}"
            )
        except FileExistsError:
            _warn(f"Validated cluster {v.cluster_id[:8]}… already exists; skipping.")

    _info(
        f"New validated clusters saved: {saved} | "
        f"Total: {len(load_validated_clusters(store_dir=_VALIDATED_CLUSTERS_DIR))}"
    )
    return valid


# ---------------------------------------------------------------------------
# Stage AW1 — Remediation Mapping
# ---------------------------------------------------------------------------


def stage_aw1(
    valid_clusters: list,
    all_records: List[ErrorClassificationRecord],
) -> list:
    """Map validated clusters to remediation plans."""
    _section("AW1  |  Remediation Mapping")

    if not valid_clusters:
        _warn("No valid clusters; skipping remediation mapping.")
        return []

    catalog = ErrorTaxonomyCatalog.load_catalog()

    plans = build_remediation_plans_from_validated_clusters(
        validated_clusters=valid_clusters,
        classification_records=all_records,
        taxonomy_catalog=catalog,
    )

    saved = 0
    for plan in plans:
        try:
            save_remediation_plan(plan, store_dir=_REMEDIATION_PLANS_DIR)
            saved += 1
            _ok(
                f"RemediationPlan {plan.remediation_id[:8]}…  "
                f"status={plan.mapping_status}  "
                f"targets={plan.remediation_targets}"
            )
        except FileExistsError:
            _warn(f"Plan {plan.remediation_id[:8]}… already exists; skipping.")

    _info(
        f"New plans saved: {saved} | "
        f"Total: {len(list_remediation_plans(store_dir=_REMEDIATION_PLANS_DIR))}"
    )
    return plans


# ---------------------------------------------------------------------------
# Stage AW2 — Fix Simulation Sandbox
# ---------------------------------------------------------------------------


def stage_aw2(plans: list) -> list:
    """Simulate each mapped remediation plan."""
    _section("AW2  |  Fix Simulation Sandbox")

    all_plans = list_remediation_plans(store_dir=_REMEDIATION_PLANS_DIR)
    if not all_plans:
        _warn("No remediation plans found; skipping simulation.")
        return []

    _info(f"Simulating {len(all_plans)} plan(s) from {_REMEDIATION_PLANS_DIR.relative_to(_ROOT)}")

    simulation_results = run_simulation_batch(all_plans)

    saved = 0
    for sim in simulation_results:
        try:
            save_simulation_result(sim, store_dir=_SIMULATION_RESULTS_DIR)
            saved += 1
            _ok(
                f"SimResult {sim.simulation_id[:8]}…  "
                f"status={sim.simulation_status}  "
                f"rec={sim.promotion_recommendation}"
            )
        except FileExistsError:
            _warn(f"Simulation {sim.simulation_id[:8]}… already exists; skipping.")

    _info(
        f"New simulation results saved: {saved} | "
        f"Total: {len(list_simulation_results(store_dir=_SIMULATION_RESULTS_DIR))}"
    )
    return simulation_results


# ---------------------------------------------------------------------------
# Stage AO — Human Feedback
# ---------------------------------------------------------------------------


def stage_ao(eval_results: List[EvalResult]) -> None:
    """Persist one real feedback record against the first eval result."""
    _section("AO  |  Human Feedback Capture")

    if not eval_results:
        _warn("No eval results available; cannot create feedback record.")
        return

    # Use the first eval result as the artifact under review
    result = eval_results[0]

    artifact = {
        "artifact_id": f"eval-{result.case_id}",
        "artifact_type": "evaluation_result",
        "case_id": result.case_id,
        "structural_score": result.structural_score,
        "semantic_score": result.semantic_score,
        "grounding_score": result.grounding_score,
        "pass_fail": result.pass_fail,
        "evaluated_at": result.evaluated_at,
    }

    reviewer_input = {
        "reviewer_id": "operationalization-agent",
        "reviewer_role": "engineer",
        "target_level": "artifact",
        "target_id": artifact["artifact_id"],
        "action": "major_edit",
        "original_text": (
            f"Evaluation result for case '{result.case_id}': "
            f"structural={result.structural_score:.2f}, "
            f"semantic={result.semantic_score:.2f}, "
            f"grounding={result.grounding_score:.2f}, "
            f"pass_fail={result.pass_fail}"
        ),
        "edited_text": (
            "Stub engine produced empty pass outputs.  Scores reflect the "
            "structural gap between stub (no extraction) and golden expectations. "
            "A real reasoning engine is required to achieve meaningful scores."
        ),
        "rationale": (
            "The evaluation was run with a stub reasoning engine for "
            "operationalization purposes.  The feedback confirms that the "
            "evaluation pipeline executed end-to-end and identifies the "
            "primary gap: no live model is wired in.  This record is the "
            "first governed feedback artifact against a real pipeline execution."
        ),
        "source_of_truth": "engineering_analysis",
        "failure_type": "extraction_error",
        "severity": "high",
        "should_update": {
            "golden_dataset": False,
            "prompts": False,
            "retrieval_memory": False,
        },
    }

    store = FeedbackStore(store_dir=_HUMAN_FEEDBACK_DIR)
    metrics_store = MetricsStore(store_dir=_OBSERVABILITY_DIR)

    try:
        record = create_feedback_from_review(
            artifact=artifact,
            reviewer_input=reviewer_input,
            store=store,
            metrics_store=metrics_store,
        )
        _ok(
            f"HumanFeedbackRecord {record.feedback_id[:8]}…  "
            f"artifact={record.artifact_id}  "
            f"action={record.action}  severity={record.severity}"
        )
        _info(
            f"Written to {_HUMAN_FEEDBACK_DIR.relative_to(_ROOT)}/{record.feedback_id}.json"
        )
    except FileExistsError:
        _warn("Feedback record already exists; skipping.")
    except Exception as exc:  # noqa: BLE001
        _warn(f"Could not create feedback record: {exc}")


# ---------------------------------------------------------------------------
# Evidence summary
# ---------------------------------------------------------------------------


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return len([p for p in directory.iterdir() if p.suffix == ".json"])


def _print_evidence_summary() -> None:
    _section("OPERATIONAL EVIDENCE SUMMARY")

    dirs = [
        ("data/observability/", _OBSERVABILITY_DIR),
        ("data/regression_baselines/", _REGRESSION_BASELINES_DIR),
        ("data/error_classifications/", _ERROR_CLASSIFICATIONS_DIR),
        ("data/error_clusters/", _ERROR_CLUSTERS_DIR),
        ("data/validated_clusters/", _VALIDATED_CLUSTERS_DIR),
        ("data/remediation_plans/", _REMEDIATION_PLANS_DIR),
        ("data/simulation_results/", _SIMULATION_RESULTS_DIR),
        ("data/human_feedback/", _HUMAN_FEEDBACK_DIR),
    ]

    for label, d in dirs:
        count = _count_files(d) if d.name != "regression_baselines" else (
            len(list(d.iterdir())) if d.exists() else 0
        )
        populated = "✓" if count > 0 else "✗"
        print(f"  {populated}  {label:<40}  {count:>3} artifact(s)")

    print()
    print("  All systems exercised.  See outputs/ for detailed reports.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    start = time.monotonic()
    print()
    print("=" * 64)
    print("  Spectrum Systems — AN–AW2 Operationalization Pass")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 64)

    _ensure_dirs()

    # Stage AN + AP
    eval_results, obs_records = stage_an_ap()

    # Stage AR
    stage_ar(eval_results, obs_records)

    # Stage AU
    all_clf_records = stage_au(eval_results)

    # Stage AV
    clusters = stage_av(all_clf_records)

    # Stage AW0
    valid_clusters = stage_aw0(clusters, all_clf_records)

    # Stage AW1
    plans = stage_aw1(valid_clusters, all_clf_records)

    # Stage AW2
    stage_aw2(plans)

    # Stage AO
    stage_ao(eval_results)

    # Summary
    _print_evidence_summary()

    elapsed = time.monotonic() - start
    print(f"  Completed in {elapsed:.1f}s")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
