"""PQX (Prompt Queue Execution) harness with fail-closed semantics."""

import json
import uuid
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

import jsonschema

from spectrum_systems.artifact_store.provenance import ArtifactStore, ProvenanceRecord


class PQXStepHarness:
    """Execution wrapper: trace, schema validation, provenance, fail-closed.

    Every step:
    1. Validates the input artifact against its declared schema.
    2. Executes the step function.
    3. Validates the output artifact against its declared schema.
    4. Stores the output with a ProvenanceRecord.
    Any validation or execution error produces an explicit failure artifact
    and returns status="FAILED" — never raises silently.
    """

    def __init__(
        self,
        step_id: str,
        step_name: str,
        artifact_store: ArtifactStore,
        schemas_path: str = "contracts/schemas",
    ):
        self.step_id = step_id
        self.step_name = step_name
        self.artifact_store = artifact_store
        self.schemas_path = Path(schemas_path)

    def execute(
        self,
        step_function: Callable[..., Dict],
        input_artifact: Dict,
        input_artifact_type: str,
        trace_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict:
        """Execute step with full harness. Returns status dict; never raises."""
        trace_id = trace_id or f"TRC-{uuid.uuid4().hex[:16].upper()}"

        # 1. Input validation
        schema_error = self._validate_artifact(input_artifact, input_artifact_type)
        if schema_error:
            return self._fail_closed("INPUT_VALIDATION_ERROR", schema_error, trace_id)
        print(f"✅ {self.step_id}: Input valid ({input_artifact_type})")

        # 2. Execute step
        try:
            print(f"▶  {self.step_id}: Executing {self.step_name}…")
            output_artifact = step_function(input_artifact, **kwargs)
            print(f"✅ {self.step_id}: Execution complete")
        except Exception as exc:
            return self._fail_closed(
                "EXECUTION_ERROR",
                f"{exc}\n{traceback.format_exc()}",
                trace_id,
            )

        # 3. Output validation
        output_type = output_artifact.get("artifact_type")
        if not output_type:
            return self._fail_closed(
                "OUTPUT_VALIDATION_ERROR",
                "Output artifact missing artifact_type",
                trace_id,
            )
        schema_error = self._validate_artifact(output_artifact, output_type)
        if schema_error:
            return self._fail_closed("OUTPUT_VALIDATION_ERROR", schema_error, trace_id)
        print(f"✅ {self.step_id}: Output valid ({output_type})")

        # 4. Store with provenance
        artifact_id = output_artifact.get("artifact_id", "")
        try:
            provenance = ProvenanceRecord(
                artifact_id=artifact_id,
                artifact_type=output_type,
                trace_id=trace_id,
                created_by=self.step_id,
                upstream_artifacts=[input_artifact.get("artifact_id", "")],
            )
            stored_path = self.artifact_store.store_artifact(output_artifact, provenance)
            print(f"✅ {self.step_id}: Stored at {stored_path}")
        except Exception as exc:
            return self._fail_closed("PROVENANCE_STORAGE_ERROR", str(exc), trace_id)

        return {
            "status": "SUCCESS",
            "trace_id": trace_id,
            "step_id": self.step_id,
            "input_artifact_id": input_artifact.get("artifact_id"),
            "output_artifact_id": artifact_id,
            "output_artifact_path": stored_path,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_artifact(self, artifact: Dict, artifact_type: str) -> Optional[str]:
        """Return an error message, or None if validation passes."""
        candidates: List[Path] = [
            self.schemas_path / f"{artifact_type}.json",
            self.schemas_path / f"{artifact_type}.schema.json",
        ]
        schema_path = next((p for p in candidates if p.exists()), None)
        if schema_path is None:
            return f"Schema not found for artifact_type '{artifact_type}'"
        try:
            with open(schema_path) as fh:
                schema = json.load(fh)
            jsonschema.validate(artifact, schema)
            return None
        except jsonschema.ValidationError as exc:
            return exc.message
        except Exception as exc:
            return str(exc)

    def _fail_closed(self, reason_code: str, details: str, trace_id: str) -> Dict:
        failure_id = f"FAIL-{uuid.uuid4().hex[:8].upper()}"
        ts = datetime.now(timezone.utc).isoformat()
        print(f"🔴 {self.step_id}: FAILED [{reason_code}] {details[:200]}")
        return {
            "status": "FAILED",
            "trace_id": trace_id,
            "step_id": self.step_id,
            "reason_code": reason_code,
            "details": details,
            "failure_artifact_id": failure_id,
            "timestamp": ts,
        }
