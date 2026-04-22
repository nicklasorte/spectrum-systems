"""Tests for Phase 3.3: ReplayVerifier."""

import random

import pytest

from spectrum_systems.promotion.replay_verifier import ReplayVerifier


def _deterministic_fn():
    return {"result": 42, "status": "ok"}


def _non_deterministic_fn():
    return {"result": random.randint(0, 10_000)}


@pytest.fixture()
def verifier():
    return ReplayVerifier()


# ---------------------------------------------------------------------------
# test_deterministic_execution_passes
# ---------------------------------------------------------------------------
def test_deterministic_execution_passes(verifier):
    ok, report = verifier.verify_determinism("art-1", _deterministic_fn, num_replays=5)
    assert ok is True
    assert report["determinism"] is True
    assert report["replays"] == 5


# ---------------------------------------------------------------------------
# test_non_deterministic_caught
# ---------------------------------------------------------------------------
def test_non_deterministic_caught(verifier):
    # Force non-determinism by ignoring the seed reset
    results = iter(range(100))

    def fn():
        return {"v": next(results)}

    ok, report = verifier.verify_determinism("art-2", fn, num_replays=5)
    assert ok is False
    assert report["determinism"] is False


# ---------------------------------------------------------------------------
# test_5_replays_all_match
# ---------------------------------------------------------------------------
def test_5_replays_all_match(verifier):
    ok, report = verifier.verify_determinism("art-3", _deterministic_fn, num_replays=5)
    assert ok is True
    assert len(verifier.run_hashes) == 5
    assert len(set(verifier.run_hashes)) == 1


# ---------------------------------------------------------------------------
# test_seed_control
# ---------------------------------------------------------------------------
def test_seed_control(verifier):
    def seeded_fn():
        # random.seed is reset to 42 before each run by verifier
        return {"v": random.randint(0, 1_000_000)}

    ok, report = verifier.verify_determinism("art-4", seeded_fn, num_replays=5, seed=42)
    assert ok is True


# ---------------------------------------------------------------------------
# test_divergence_debugging
# ---------------------------------------------------------------------------
def test_divergence_debugging(verifier):
    counter = {"n": 0}

    def diverging_fn():
        counter["n"] += 1
        return {"call": counter["n"]}

    ok, report = verifier.verify_determinism("art-5", diverging_fn, num_replays=5)
    assert ok is False
    assert "hashes" in report
    assert len(report["hashes"]) == 5


# ---------------------------------------------------------------------------
# test_promotion_blocked_on_divergence
# ---------------------------------------------------------------------------
def test_promotion_blocked_on_divergence(verifier):
    counter = {"n": 0}

    def diverging_fn():
        counter["n"] += 1
        return {"v": counter["n"]}

    ok, report = verifier.verify_determinism("art-6", diverging_fn)
    assert ok is False
    assert report["determinism"] is False
