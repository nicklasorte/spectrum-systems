"""EvalSlicer: Multi-dimensional eval rubrics. Detect failures hidden in aggregate metrics.
Never rely on pass rate alone. Slices > aggregates."""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class EvalSlice:
    """Single eval slice definition."""
    slice_name: str
    slice_filter: str
    pass_threshold: float
    severity: str
    is_critical: bool


@dataclass
class SliceResult:
    """Results for one slice."""
    slice_name: str
    slice_filter: str
    pass_rate: float
    sample_count: int
    severity: str
    status: str
    failing_samples: List[str]


class EvalSlicer:
    """Multi-dimensional eval harness: measure evals by slice, not just aggregate.
    Aggregates hide tail failures. This enforces slice-based reporting as default."""

    def __init__(self, artifact_store, eval_runner):
        self.artifact_store = artifact_store
        self.eval_runner = eval_runner
        self.slices: Dict[str, List[EvalSlice]] = {}

    def register_slices_for_artifact_family(self, artifact_family: str, slices: List[EvalSlice]) -> None:
        """Register eval slices for an artifact family."""
        if artifact_family not in self.slices:
            self.slices[artifact_family] = []

        self.slices[artifact_family].extend(slices)

        slice_registry = {
            'artifact_type': 'slice_registry',
            'artifact_family': artifact_family,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'slices': [asdict(s) for s in slices]
        }

        self.artifact_store.put(
            slice_registry,
            namespace='governance/evals/slice_registry',
            immutable=True
        )

    def evaluate_with_slices(self, artifact_family: str, eval_case_ids: List[str]) -> Dict[str, Any]:
        """Run evals on artifacts, measure by slice (not aggregate).
        Returns: artifact_family_health_report"""
        try:
            eval_results = []
            for case_id in eval_case_ids:
                result = self.eval_runner.get_result(case_id)
                if result:
                    eval_results.append(result)

            if not eval_results:
                return self._emit_error_artifact("No eval results found")

            slices = self.slices.get(artifact_family, [])
            if not slices:
                return self._emit_error_artifact(f"No slices registered for {artifact_family}")

            slice_results = []
            critical_failures = []
            overall_pass_count = sum(1 for r in eval_results if r.get('status') == 'pass')
            overall_pass_rate = overall_pass_count / len(eval_results) if eval_results else 0

            for slice_def in slices:
                slice_members = self._filter_by_predicate(eval_results, slice_def.slice_filter)

                if not slice_members:
                    slice_results.append(SliceResult(
                        slice_name=slice_def.slice_name,
                        slice_filter=slice_def.slice_filter,
                        pass_rate=0,
                        sample_count=0,
                        severity=slice_def.severity,
                        status='warning',
                        failing_samples=[]
                    ))
                    continue

                passes = sum(1 for m in slice_members if m.get('status') == 'pass')
                pass_rate = passes / len(slice_members)
                status = 'passing' if pass_rate >= slice_def.pass_threshold else 'failing'

                failing_samples = [m['artifact_id'] for m in slice_members if m.get('status') != 'pass']

                slice_result = SliceResult(
                    slice_name=slice_def.slice_name,
                    slice_filter=slice_def.slice_filter,
                    pass_rate=pass_rate,
                    sample_count=len(slice_members),
                    severity=slice_def.severity,
                    status=status,
                    failing_samples=failing_samples
                )

                slice_results.append(slice_result)

                if slice_def.is_critical and status == 'failing':
                    critical_failures.append(slice_def.slice_name)

            recommendations = []
            critical_status = 'all_failing' if len(critical_failures) == len([s for s in slices if s.is_critical]) \
                              else ('some_failing' if critical_failures else 'all_passing')

            if critical_failures:
                recommendations.append(f"CRITICAL: Slices {critical_failures} are failing. Block promotion.")

            for sr in slice_results:
                if sr.status == 'failing':
                    recommendations.append(
                        f"Slice '{sr.slice_name}' failing ({sr.pass_rate:.2%}). {sr.sample_count} samples."
                    )

            health_report = {
                'report_id': str(uuid.uuid4()),
                'artifact_family': artifact_family,
                'report_timestamp': datetime.utcnow().isoformat() + 'Z',
                'overall_pass_rate': overall_pass_rate,
                'slice_results': [asdict(sr) for sr in slice_results],
                'critical_slice_status': critical_status,
                'recommendations': recommendations
            }

            self.artifact_store.put(
                health_report,
                namespace='governance/evals/health_reports'
            )

            return health_report

        except Exception as e:
            return self._emit_error_artifact(f"Eval slicing failed: {str(e)}")

    def _filter_by_predicate(self, results: List[Dict], predicate: str) -> List[Dict]:
        """Filter results by string predicate."""
        matching = []
        for result in results:
            try:
                if self._evaluate_predicate(result, predicate):
                    matching.append(result)
            except Exception:
                pass
        return matching

    def _evaluate_predicate(self, item: Dict, predicate: str) -> bool:
        """Safely evaluate predicate against item fields."""
        safe_dict = {k: v for k, v in item.items() if isinstance(v, (int, float, str, bool))}

        try:
            return eval(predicate, {"__builtins__": {}}, safe_dict)
        except Exception:
            return False

    def _emit_error_artifact(self, error_msg: str) -> Dict[str, Any]:
        """Emit error_artifact and return fail-closed response."""
        error_artifact = {
            'artifact_type': 'error_artifact',
            'source': 'EvalSlicer',
            'error_message': error_msg,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass

        return {
            'report_id': str(uuid.uuid4()),
            'artifact_family': 'unknown',
            'report_timestamp': datetime.utcnow().isoformat() + 'Z',
            'overall_pass_rate': 0,
            'slice_results': [],
            'critical_slice_status': 'all_failing',
            'recommendations': ['ERROR: Eval slicing failed. Block promotion until resolved.']
        }
