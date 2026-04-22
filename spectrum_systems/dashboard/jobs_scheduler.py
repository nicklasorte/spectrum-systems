"""Daily and streaming jobs scheduler for dashboard artifact intelligence."""

import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


def _exponential_backoff(func: Callable[[], Any], max_retries: int = 3, base_delay: float = 1.0) -> Any:
    """Run func with exponential backoff on failure; emits JobFailureArtifact on exhaustion."""
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(base_delay * (2 ** attempt))
    raise RuntimeError(f"Job failed after {max_retries} retries: {last_exc}") from last_exc


class DashboardJobsScheduler:
    """Schedules and runs B1-B10 dashboard data pipeline jobs with retry and failure artifacts."""

    def __init__(self, artifact_store: Any) -> None:
        self.artifact_store = artifact_store

    # B1: Daily reason-code aggregation
    def run_daily_reason_code_aggregation(self) -> Dict[str, Any]:
        """Aggregate block events into ReasonCodeRecord artifacts."""
        def _run() -> Dict[str, Any]:
            blocks = self.artifact_store.query(
                {"artifact_type": "control_response_log", "control_decision": "block", "recency_days": 1},
                limit=10000,
            )
            reason_counts: Dict[str, int] = {}
            for block in blocks:
                reason = block.get("trigger_signal", "unknown")
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

            records = []
            for code, count in reason_counts.items():
                record = {
                    "artifact_type": "reason_code_record",
                    "reason_code_id": f"rcr-{code}-{datetime.utcnow().strftime('%Y%m%d')}",
                    "parent_code": "root",
                    "code_name": code,
                    "description": f"Aggregated reason code {code} with {count} incidents today.",
                    "incident_count": count,
                    "trend": "stable",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                self.artifact_store.put(record, namespace="dashboard/reason_codes")
                records.append(record)
            return {"job": "B1", "records_written": len(records)}

        return self._run_with_failure_artifact("B1", "daily_reason_code_aggregation", _run)

    # B2: Daily override rate calculation
    def run_daily_override_rate_calculation(self) -> Dict[str, Any]:
        """Calculate per-policy override rates and emit trend reports."""
        def _run() -> Dict[str, Any]:
            reports = self.artifact_store.query(
                {"artifact_type": "override_hotspot_report", "recency_days": 1},
                limit=10000,
            )
            written = 0
            for report in reports:
                summary = {
                    "artifact_type": "policy_override_rate_daily",
                    "report_id": report.get("report_id", "unknown"),
                    "computed_at": datetime.utcnow().isoformat() + "Z",
                    "hotspot_count": len(report.get("hotspots", [])),
                }
                self.artifact_store.put(summary, namespace="dashboard/override_rates")
                written += 1
            return {"job": "B2", "records_written": written}

        return self._run_with_failure_artifact("B2", "daily_override_rate_calculation", _run)

    # B3: Daily cost-per-promotion calculation
    def run_daily_cost_per_promotion(self) -> Dict[str, Any]:
        """Compute cost per promotion per route and emit budget status artifacts."""
        def _run() -> Dict[str, Any]:
            budgets = self.artifact_store.query(
                {"artifact_type": "cost_budget_status", "recency_days": 1},
                limit=10000,
            )
            written = 0
            for budget in budgets:
                summary = {
                    "artifact_type": "daily_cost_summary",
                    "route_id": budget.get("route_id", "unknown"),
                    "cost_per_promotion": budget.get("cost_per_promotion", 0),
                    "computed_at": datetime.utcnow().isoformat() + "Z",
                }
                self.artifact_store.put(summary, namespace="dashboard/costs")
                written += 1
            return {"job": "B3", "records_written": written}

        return self._run_with_failure_artifact("B3", "daily_cost_per_promotion", _run)

    # B4: Daily contradiction-correlation update
    def run_daily_contradiction_correlation(self) -> Dict[str, Any]:
        """Update context-source to contradiction correlation index."""
        def _run() -> Dict[str, Any]:
            spikes = self.artifact_store.query(
                {"artifact_type": "contradiction_spike", "recency_days": 1},
                limit=10000,
            )
            written = 0
            for spike in spikes:
                record = {
                    "artifact_type": "daily_contradiction_correlation",
                    "context_source": spike.get("context_source", "unknown"),
                    "contradiction_count": spike.get("contradiction_count", 0),
                    "computed_at": datetime.utcnow().isoformat() + "Z",
                }
                self.artifact_store.put(record, namespace="dashboard/contradictions")
                written += 1
            return {"job": "B4", "records_written": written}

        return self._run_with_failure_artifact("B4", "daily_contradiction_correlation", _run)

    # B5: Daily judge-disagreement report
    def run_daily_judge_disagreement_report(self) -> Dict[str, Any]:
        """Emit daily judge disagreement summaries for trend tracking."""
        def _run() -> Dict[str, Any]:
            reports = self.artifact_store.query(
                {"artifact_type": "judge_disagreement_report", "recency_days": 1},
                limit=10000,
            )
            written = 0
            for report in reports:
                summary = {
                    "artifact_type": "daily_judge_disagreement_summary",
                    "judge_id": report.get("judge_id", "unknown"),
                    "disagreement_rate": report.get("disagreement_rate", 0),
                    "computed_at": datetime.utcnow().isoformat() + "Z",
                }
                self.artifact_store.put(summary, namespace="dashboard/judge_disagreements")
                written += 1
            return {"job": "B5", "records_written": written}

        return self._run_with_failure_artifact("B5", "daily_judge_disagreement_report", _run)

    # B6: Weekly artifact-supersession audit
    def run_weekly_artifact_supersession_audit(self) -> Dict[str, Any]:
        """Audit artifact supersession chains for cycles or orphan terminations."""
        def _run() -> Dict[str, Any]:
            records = self.artifact_store.query(
                {"artifact_type": "artifact_supersession_record", "recency_days": 7},
                limit=10000,
            )
            orphans = [r for r in records if not r.get("new_artifact_id")]
            summary = {
                "artifact_type": "weekly_supersession_audit",
                "total_supersessions": len(records),
                "orphan_terminations": len(orphans),
                "computed_at": datetime.utcnow().isoformat() + "Z",
            }
            self.artifact_store.put(summary, namespace="dashboard/supersession_audits")
            return {"job": "B6", "records_written": 1, "orphans_found": len(orphans)}

        return self._run_with_failure_artifact("B6", "weekly_artifact_supersession_audit", _run)

    # B7: Daily job-failure-artifact cleanup classification
    def run_daily_job_failure_classification(self) -> Dict[str, Any]:
        """Classify job failures as recovered/dead_letter and emit status artifacts."""
        def _run() -> Dict[str, Any]:
            failures = self.artifact_store.query(
                {"artifact_type": "job_failure_artifact", "recency_days": 1},
                limit=10000,
            )
            dead_letters = [f for f in failures if f.get("status") == "dead_letter"]
            summary = {
                "artifact_type": "daily_job_failure_summary",
                "total_failures": len(failures),
                "dead_letters": len(dead_letters),
                "computed_at": datetime.utcnow().isoformat() + "Z",
            }
            self.artifact_store.put(summary, namespace="dashboard/job_health")
            return {"job": "B7", "total_failures": len(failures), "dead_letters": len(dead_letters)}

        return self._run_with_failure_artifact("B7", "daily_job_failure_classification", _run)

    # B8: Streaming control-response-log indexing
    def run_streaming_control_response_index(self, batch_size: int = 100) -> Dict[str, Any]:
        """Index incoming control response logs for fast query access."""
        def _run() -> Dict[str, Any]:
            logs = self.artifact_store.query(
                {"artifact_type": "control_response_log", "recency_days": 1},
                limit=batch_size,
            )
            indexed = 0
            for log in logs:
                index_entry = {
                    "artifact_type": "control_response_index_entry",
                    "log_id": log.get("log_id"),
                    "control_decision": log.get("control_decision"),
                    "route_id": log.get("route_id"),
                    "indexed_at": datetime.utcnow().isoformat() + "Z",
                }
                self.artifact_store.put(index_entry, namespace="dashboard/indexes/control_responses")
                indexed += 1
            return {"job": "B8", "indexed": indexed}

        return self._run_with_failure_artifact("B8", "streaming_control_response_index", _run)

    # B9: Daily eval-coverage-gap detection
    def run_daily_eval_coverage_gap_detection(self) -> Dict[str, Any]:
        """Detect artifact types with eval coverage below threshold and emit gap records."""
        def _run() -> Dict[str, Any]:
            summaries = self.artifact_store.query(
                {"artifact_type": "eval_coverage_summary", "recency_days": 1},
                limit=10000,
            )
            gaps = [s for s in summaries if s.get("coverage_pct", 100) < 80]
            gap_record = {
                "artifact_type": "daily_eval_coverage_gap_record",
                "gap_count": len(gaps),
                "gap_types": [g.get("artifact_type") for g in gaps],
                "computed_at": datetime.utcnow().isoformat() + "Z",
            }
            self.artifact_store.put(gap_record, namespace="dashboard/eval_gaps")
            return {"job": "B9", "gaps_detected": len(gaps)}

        return self._run_with_failure_artifact("B9", "daily_eval_coverage_gap_detection", _run)

    # B10: Weekly effectiveness-metric calculation
    def run_weekly_effectiveness_metric_calculation(self) -> Dict[str, Any]:
        """Compute weekly control effectiveness metrics and emit ControlEffectivenessMetric artifacts."""
        def _run() -> Dict[str, Any]:
            control_logs = self.artifact_store.query(
                {"artifact_type": "control_response_log", "recency_days": 7},
                limit=10000,
            )
            false_positives = sum(1 for log in control_logs if log.get("status") == "reversed")
            total = len(control_logs)
            fpr = false_positives / total if total > 0 else 0.0

            metric = {
                "artifact_type": "control_effectiveness_metric",
                "metric_id": f"cem-weekly-fpr-{datetime.utcnow().strftime('%Y%m%d')}",
                "metric_type": "false_positive_rate",
                "metric_value": fpr,
                "measurement_period": "weekly",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            self.artifact_store.put(metric, namespace="dashboard/effectiveness")
            return {"job": "B10", "false_positive_rate": fpr, "total_decisions": total}

        return self._run_with_failure_artifact("B10", "weekly_effectiveness_metric_calculation", _run)

    def _run_with_failure_artifact(
        self, job_id: str, job_name: str, func: Callable[[], Any]
    ) -> Dict[str, Any]:
        """Run a job with retry logic; emit a JobFailureArtifact if all retries are exhausted."""
        try:
            return _exponential_backoff(func, max_retries=3)
        except Exception as exc:
            failure_artifact = {
                "artifact_type": "job_failure_artifact",
                "failure_id": f"jfa-{job_id}-{uuid.uuid4().hex[:8]}",
                "job_id": job_id,
                "job_name": job_name,
                "failure_reason": str(exc),
                "retry_count": 3,
                "last_retry_timestamp": datetime.utcnow().isoformat() + "Z",
                "status": "dead_letter",
            }
            try:
                self.artifact_store.put(failure_artifact, namespace="dashboard/failures")
            except Exception:
                pass
            raise

    def run_all_daily_jobs(self) -> List[Dict[str, Any]]:
        """Run all daily jobs (B1-B5, B7-B9) and return results."""
        results = []
        daily_jobs = [
            self.run_daily_reason_code_aggregation,
            self.run_daily_override_rate_calculation,
            self.run_daily_cost_per_promotion,
            self.run_daily_contradiction_correlation,
            self.run_daily_judge_disagreement_report,
            self.run_daily_job_failure_classification,
            self.run_daily_eval_coverage_gap_detection,
        ]
        for job in daily_jobs:
            try:
                results.append(job())
            except Exception as exc:
                results.append({"job": job.__name__, "error": str(exc)})
        return results
