"""Phase 3.2: Signal Bus

Pub-sub system for real-time signal updates.
Signals dispatch synchronously; <200ms latency target.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


class Signal:
    """Represents a system signal."""

    def __init__(self, signal_type: str, data: Dict[str, Any]) -> None:
        self.signal_type = signal_type
        self.data = data
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.latency_ms: float = 0.0


class SignalBus:
    """Pub-sub bus for real-time signals."""

    LATENCY_TARGET_MS = 200.0

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Signal], None]]] = {}
        self._latencies: List[float] = []
        self._lock = threading.Lock()

    def subscribe(
        self, signal_type: str, callback: Callable[[Signal], None]
    ) -> None:
        """Subscribe to a signal type."""
        with self._lock:
            self._subscribers.setdefault(signal_type, []).append(callback)

    def publish(self, signal: Signal) -> None:
        """Publish a signal to all subscribers synchronously."""
        publish_start = time.perf_counter()

        with self._lock:
            handlers = list(self._subscribers.get(signal.signal_type, []))

        for callback in handlers:
            try:
                callback(signal)
            except Exception as exc:
                # Log but never fail
                print(f"Signal handler error [{signal.signal_type}]: {exc}")

        latency_ms = (time.perf_counter() - publish_start) * 1000
        signal.latency_ms = latency_ms

        with self._lock:
            self._latencies.append(latency_ms)

    def get_signal_latency_stats(self) -> Dict[str, float]:
        """Return signal latency statistics."""
        with self._lock:
            latencies = list(self._latencies)

        if not latencies:
            return {"p50_ms": 0.0, "p99_ms": 0.0, "avg_ms": 0.0, "max_ms": 0.0}

        sorted_lat = sorted(latencies)
        return {
            "p50_ms": sorted_lat[len(sorted_lat) // 2],
            "p99_ms": sorted_lat[int(len(sorted_lat) * 0.99)],
            "avg_ms": sum(sorted_lat) / len(sorted_lat),
            "max_ms": max(sorted_lat),
        }

    def clear_subscribers(self) -> None:
        """Remove all subscribers (useful for testing)."""
        with self._lock:
            self._subscribers.clear()
