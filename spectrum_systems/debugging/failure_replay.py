"""
Phase 8: Failure Replay Engine

Safely reproduce any failure in isolated sandbox.
Deterministic execution with fixed random seed.
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, Tuple, Any, Callable
from pathlib import Path
import random
import tempfile
import shutil


class ReplaySandbox:
    """Isolated environment for replay execution."""

    def __init__(self, failure_id: str):
        self.sandbox_id = f"sandbox_{failure_id}"
        self.original_trace_id = None
        self.temp_dir = tempfile.mkdtemp(prefix="replay_")
        self.state = {
            "created_at": datetime.now().isoformat(),
            "artifact_store": f"{self.temp_dir}/artifacts",
            "execution_log": [],
        }
        Path(self.state["artifact_store"]).mkdir(exist_ok=True, parents=True)

    def cleanup(self):
        """Delete sandbox after use."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def get_artifact_store(self) -> str:
        """Get isolated artifact store path."""
        return self.state["artifact_store"]

    def log_execution(self, event: Dict):
        """Log event in sandbox."""
        self.state["execution_log"].append(event)


class FailureReplayEngine:
    """Execute failure replays safely in isolation."""

    def __init__(self, input_store_path: str = "/tmp/artifacts"):
        self.input_store = Path(input_store_path)
        self.sandboxes = {}

    def get_input_for_trace(self, trace_id: str) -> Dict:
        """Retrieve input that caused failure."""
        input_file = self.input_store / f"input_{trace_id}.json"
        if input_file.exists():
            with open(input_file) as f:
                return json.load(f)
        return {}

    def create_sandbox(self, failure_id: str) -> ReplaySandbox:
        """Create isolated sandbox for replay."""
        sandbox = ReplaySandbox(failure_id)
        self.sandboxes[sandbox.sandbox_id] = sandbox
        return sandbox

    def replay_in_sandbox(
        self,
        failure_artifact: Dict,
        execution_fn: Callable,
        sandbox_id: str = None,
    ) -> Dict:
        """
        Replay failure in sandbox.

        Args:
            failure_artifact: Original failure (has trace_id, reason_code)
            execution_fn: Function to re-execute (takes trace_id + seed)
            sandbox_id: Use existing sandbox or create new

        Returns:
            Replayed failure artifact (should match original)
        """
        if not sandbox_id:
            sandbox = self.create_sandbox(failure_artifact["failure_id"])
        else:
            sandbox = self.sandboxes.get(sandbox_id)

        trace_id = failure_artifact["trace_id"]
        original_input = self.get_input_for_trace(trace_id)

        seed = failure_artifact.get("random_seed", 42)
        random.seed(seed)

        replayed_result = execution_fn(
            trace_id=trace_id,
            input_data=original_input,
            seed=seed,
            artifact_store=sandbox.get_artifact_store(),
        )

        return replayed_result

    @staticmethod
    def _hash_output(output: Any) -> str:
        """Compute deterministic hash of output."""
        output_json = json.dumps(output, sort_keys=True, default=str)
        return hashlib.sha256(output_json.encode()).hexdigest()

    def verify_replay_matches_original(
        self,
        original_failure: Dict,
        replayed_failure: Dict,
    ) -> Tuple[bool, str]:
        """Verify we reproduced the exact same failure."""
        if original_failure.get("reason_code") != replayed_failure.get("reason_code"):
            return False, "Reason code mismatch"

        orig_trace = original_failure.get("stack_trace", "")[:200]
        replay_trace = replayed_failure.get("stack_trace", "")[:200]

        if orig_trace != replay_trace:
            return False, "Stack trace mismatch"

        orig_hash = self._hash_output(original_failure.get("data", {}))
        replay_hash = self._hash_output(replayed_failure.get("data", {}))

        if orig_hash == replay_hash:
            return True, "Perfect match"
        else:
            return False, "Output hash mismatch"

    def extract_minimal_repro(
        self,
        failure_artifact: Dict,
        full_input: Dict,
        execution_fn: Callable,
    ) -> Dict:
        """Find minimal input that reproduces failure."""
        minimal_input = full_input.copy()

        for key in list(full_input.keys()):
            test_input = {k: v for k, v in full_input.items() if k != key}

            result = execution_fn(
                trace_id="test",
                input_data=test_input,
                seed=42,
            )

            if result.get("failed"):
                minimal_input = test_input

        return minimal_input
