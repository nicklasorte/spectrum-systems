"""Tests for Phase 3.2: SignalBus."""

import threading
import time

import pytest

from spectrum_systems.observability.signal_bus import Signal, SignalBus


@pytest.fixture()
def bus():
    b = SignalBus()
    yield b
    b.clear_subscribers()


# ---------------------------------------------------------------------------
# test_signal_published_to_subscribers
# ---------------------------------------------------------------------------
def test_signal_published_to_subscribers(bus):
    received = []
    bus.subscribe("eval_pass", lambda s: received.append(s))

    sig = Signal("eval_pass", {"score": 0.95})
    bus.publish(sig)

    assert len(received) == 1
    assert received[0].data["score"] == 0.95


# ---------------------------------------------------------------------------
# test_signal_latency_under_200ms
# ---------------------------------------------------------------------------
def test_signal_latency_under_200ms(bus):
    bus.subscribe("latency_test", lambda s: None)
    sig = Signal("latency_test", {})
    bus.publish(sig)
    assert sig.latency_ms < 200.0


# ---------------------------------------------------------------------------
# test_multiple_signal_types
# ---------------------------------------------------------------------------
def test_multiple_signal_types(bus):
    a_received = []
    b_received = []

    bus.subscribe("type-A", lambda s: a_received.append(s))
    bus.subscribe("type-B", lambda s: b_received.append(s))

    bus.publish(Signal("type-A", {"v": 1}))
    bus.publish(Signal("type-B", {"v": 2}))
    bus.publish(Signal("type-A", {"v": 3}))

    assert len(a_received) == 2
    assert len(b_received) == 1


# ---------------------------------------------------------------------------
# test_signal_accuracy
# ---------------------------------------------------------------------------
def test_signal_accuracy(bus):
    results = []
    bus.subscribe("accuracy", lambda s: results.append(s.data))

    payloads = [{"id": i, "val": i * 2} for i in range(5)]
    for p in payloads:
        bus.publish(Signal("accuracy", p))

    assert results == payloads


# ---------------------------------------------------------------------------
# test_concurrent_signals
# ---------------------------------------------------------------------------
def test_concurrent_signals(bus):
    counter = {"n": 0}
    lock = threading.Lock()

    def increment(sig):
        with lock:
            counter["n"] += 1

    bus.subscribe("concurrent", increment)

    threads = [
        threading.Thread(target=bus.publish, args=(Signal("concurrent", {"i": i}),))
        for i in range(50)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter["n"] == 50


# ---------------------------------------------------------------------------
# test_latency_stats
# ---------------------------------------------------------------------------
def test_latency_stats(bus):
    bus.subscribe("stats_test", lambda s: None)
    for _ in range(20):
        bus.publish(Signal("stats_test", {}))

    stats = bus.get_signal_latency_stats()
    assert "p50_ms" in stats
    assert "p99_ms" in stats
    assert "avg_ms" in stats
    assert stats["p99_ms"] >= stats["p50_ms"]
