"""
Phase 8: Failure Replay Tests (9 tests)
"""

import json
import pytest
import tempfile
from pathlib import Path
from spectrum_systems.debugging.failure_replay import FailureReplayEngine, ReplaySandbox
from spectrum_systems.debugging.comparative_debug import ComparativeDebugger


class TestFailureReplay:
    """Test failure replay engine."""

    def test_sandbox_isolation(self):
        """Sandbox is isolated and cleans up."""
        sandbox = ReplaySandbox("test-1")
        assert Path(sandbox.get_artifact_store()).exists()
        sandbox.cleanup()
        assert not Path(sandbox.temp_dir).exists()

    def test_replay_engine_input_retrieval(self):
        """Engine can retrieve inputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = FailureReplayEngine(tmpdir)
            test_input = {"data": "test", "value": 42}
            input_file = Path(tmpdir) / "input_trace-001.json"
            input_file.write_text(json.dumps(test_input))

            retrieved = engine.get_input_for_trace("trace-001")
            assert retrieved == test_input

    def test_replay_matches_original(self):
        """Replay verification detects matches."""
        engine = FailureReplayEngine()

        original = {
            "reason_code": "VALUE_ERROR",
            "stack_trace": "ValueError: invalid\n  at line 42",
            "data": {"error": "invalid"},
        }
        replayed = original.copy()

        matches, msg = engine.verify_replay_matches_original(original, replayed)
        assert matches

    def test_replay_detects_divergence(self):
        """Replay verification detects mismatches."""
        engine = FailureReplayEngine()

        original = {
            "reason_code": "VALUE_ERROR",
            "stack_trace": "ValueError: invalid",
            "data": {"val": 1},
        }

        diverged = {
            "reason_code": "TYPE_ERROR",
            "stack_trace": "TypeError: wrong",
            "data": {"val": 2},
        }

        matches, msg = engine.verify_replay_matches_original(original, diverged)
        assert not matches

    def test_output_hash_consistency(self):
        """Output hashing is deterministic."""
        engine = FailureReplayEngine()

        output1 = {"data": "test", "value": 42}
        output2 = {"data": "test", "value": 42}
        output3 = {"data": "test", "value": 43}

        hash1 = engine._hash_output(output1)
        hash2 = engine._hash_output(output2)
        hash3 = engine._hash_output(output3)

        assert hash1 == hash2
        assert hash1 != hash3

    def test_minimal_repro_extraction(self):
        """Engine can extract minimal reproducing input."""
        engine = FailureReplayEngine()

        full_input = {"a": 1, "b": 2, "c": 3}

        def mock_exec(trace_id, input_data, seed, artifact_store=None):
            return {"failed": len(input_data) > 0}

        minimal = engine.extract_minimal_repro(
            {"failure_id": "F1", "trace_id": "T1"},
            full_input,
            mock_exec,
        )

        assert len(minimal) <= len(full_input)


class TestComparativeDebugger:
    """Test comparative debugging."""

    def test_compare_identical_runs(self):
        """Identical runs show no divergence."""
        debugger = ComparativeDebugger()

        with tempfile.TemporaryDirectory() as tmpdir:
            events = [
                {"event_type": "start", "data": {"x": 1}},
                {"event_type": "end", "data": {"x": 2}},
            ]

            (Path(tmpdir) / "events_trace-a.json").write_text(json.dumps(events))
            (Path(tmpdir) / "events_trace-b.json").write_text(json.dumps(events))

            comparison = debugger.compare_runs("trace-a", "trace-b", event_store=tmpdir)

            assert comparison["divergence_index"] is None
            assert comparison["total_differences"] == 0

    def test_compare_divergent_runs(self):
        """Divergent runs are detected."""
        debugger = ComparativeDebugger()

        with tempfile.TemporaryDirectory() as tmpdir:
            events_a = [
                {"event_type": "start", "data": {"x": 1}},
                {"event_type": "end", "data": {"x": 2}},
            ]

            events_b = [
                {"event_type": "start", "data": {"x": 1}},
                {"event_type": "end", "data": {"x": 99}},
            ]

            (Path(tmpdir) / "events_trace-x.json").write_text(json.dumps(events_a))
            (Path(tmpdir) / "events_trace-y.json").write_text(json.dumps(events_b))

            comparison = debugger.compare_runs("trace-x", "trace-y", event_store=tmpdir)

            assert comparison["divergence_index"] == 1
            assert comparison["total_differences"] > 0

    def test_divergence_point_identification(self):
        """Divergence point is correctly identified."""
        debugger = ComparativeDebugger()

        with tempfile.TemporaryDirectory() as tmpdir:
            events_a = [
                {"event_type": "start", "data": {"x": 1}},
                {"event_type": "split", "data": {"x": 2}},
                {"event_type": "end", "data": {"x": 3}},
            ]

            events_b = [
                {"event_type": "start", "data": {"x": 1}},
                {"event_type": "different", "data": {"x": 99}},
                {"event_type": "end", "data": {"x": 3}},
            ]

            (Path(tmpdir) / "events_trace-z.json").write_text(json.dumps(events_a))
            (Path(tmpdir) / "events_trace-w.json").write_text(json.dumps(events_b))

            comparison = debugger.compare_runs("trace-z", "trace-w", event_store=tmpdir)
            divergence = debugger.trace_to_divergence_point(comparison, tmpdir)

            assert divergence["divergence_at"] == 1
