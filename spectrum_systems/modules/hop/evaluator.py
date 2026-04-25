from __future__ import annotations

import hashlib
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .validator import validate_artifact_shape


class HOPEvaluationError(RuntimeError):
    """Raised when deterministic evaluation cannot complete."""


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _load_candidate(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("hop_candidate_module", str(path))
    if spec is None or spec.loader is None:
        raise HOPEvaluationError(f"unable to import candidate: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cls = getattr(module, "HarnessCandidate")
    return cls()


def _score_case(output: dict[str, Any], case: dict[str, Any]) -> tuple[bool, str]:
    text = json.dumps(output, sort_keys=True).lower()
    expected = case.get("expected", {})
    for token in expected.get("must_contain", []):
        if token.lower() not in text:
            return False, f"missing token: {token}"
    for token in expected.get("must_not_contain", []):
        if token.lower() in text:
            return False, f"forbidden token: {token}"
    min_items = int(expected.get("min_faq_items", 0))
    if len(output.get("faq_items", [])) < min_items:
        return False, "faq_count_below_minimum"
    return True, "ok"


def evaluate_candidate(
    *,
    candidate_artifact: dict[str, Any],
    eval_set_path: Path,
    trace_id: str,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    eval_set = json.loads(eval_set_path.read_text(encoding="utf-8"))
    cases = eval_set.get("cases", [])
    if not cases:
        raise HOPEvaluationError("missing eval cases")

    candidate = _load_candidate(Path(candidate_artifact["code_ref"]))
    run_artifacts = []
    passed = 0
    latencies: list[float] = []

    for case in cases:
        start = time.perf_counter()
        status = "pass"
        error = ""
        output: dict[str, Any]
        try:
            output = candidate.run(case["input"]["transcript"])
            ok, reason = _score_case(output, case)
            if not ok:
                status = "fail"
                error = reason
            else:
                passed += 1
        except Exception as exc:
            status = "fail"
            error = str(exc)
            output = {"artifact_type": "faq_cluster_artifact", "faq_items": []}

        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)
        run = {
            "artifact_type": "harness_run",
            "artifact_id": f"hop-run-{candidate_artifact['candidate_id']}-{case['eval_case_id']}",
            "schema_ref": "hop/harness_run.schema.json@1.0.0",
            "trace": {
                "trace_id": trace_id,
                "timestamp": _now(),
                "steps": [
                    {"name": "execute_candidate", "status": "start"},
                    {"name": "score_case", "status": "pass" if status == "pass" else "fail", "detail": error or "ok"},
                ],
            },
            "content_hash": _sha({"case": case["eval_case_id"], "output": output, "status": status}),
            "created_at": _now(),
            "run_id": f"run-{case['eval_case_id']}",
            "candidate_id": candidate_artifact["candidate_id"],
            "eval_case_id": case["eval_case_id"],
            "status": status,
            "output_artifact": {"artifact_type": output.get("artifact_type", "faq_cluster_artifact"), "payload": output},
            "error": error,
            "latency_ms": elapsed_ms,
        }
        validate_artifact_shape(run, "harness_run", schema_root=schema_root)
        run_artifacts.append(run)

    summary = {
        "artifact_type": "harness_score",
        "artifact_id": f"hop-score-{candidate_artifact['candidate_id']}",
        "schema_ref": "hop/harness_score.schema.json@1.0.0",
        "trace": {"trace_id": trace_id, "timestamp": _now(), "steps": [{"name": "eval_summary", "status": "pass"}]},
        "content_hash": _sha({"candidate_id": candidate_artifact["candidate_id"], "passed": passed, "total": len(cases)}),
        "created_at": _now(),
        "candidate_id": candidate_artifact["candidate_id"],
        "score": round(passed / len(cases), 6),
        "coverage": 1.0,
        "run_count": len(cases),
        "cost": float(candidate_artifact.get("cost", 0.0)),
        "latency_ms": round(sum(latencies) / len(latencies), 3),
    }
    validate_artifact_shape(summary, "harness_score", schema_root=schema_root)

    return {"eval_result_artifacts": run_artifacts, "eval_summary_artifact": summary}
