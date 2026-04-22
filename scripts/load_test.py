"""Load testing for dashboard."""

import time
import concurrent.futures
from typing import List, Tuple
try:
    import requests
except ImportError:
    requests = None


class LoadTester:
    """Simulate user load on dashboard."""

    def __init__(self, base_url: str, num_users: int = 1000):
        self.base_url = base_url
        self.num_users = num_users
        self.results: List[Tuple[str, float, int]] = []

    def load_test(self, duration_seconds: int = 60) -> dict:
        """Run load test for specified duration."""
        start_time = time.time()
        end_time = start_time + duration_seconds

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            futures = []

            for user_id in range(self.num_users):
                future = executor.submit(
                    self._simulate_user,
                    user_id,
                    end_time
                )
                futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    self.results.append(result)
                except Exception as e:
                    self.results.append(('error', 0, 0))

        return self._analyze_results()

    def _simulate_user(self, user_id: int, end_time: float) -> Tuple[str, float, int]:
        """Simulate single user browsing dashboard."""
        try:
            if requests is None:
                return ('error', 0, 0)

            # Fetch entropy snapshot
            start = time.time()
            response = requests.get(
                f'{self.base_url}/api/entropy/latest',
                timeout=5
            )
            latency = time.time() - start

            if response.status_code == 200:
                return ('success', latency, response.status_code)
            else:
                return ('error', latency, response.status_code)

        except Exception as e:
            if requests and hasattr(requests, 'Timeout') and isinstance(e, requests.Timeout):
                return ('timeout', 5.0, 0)
            return ('error', 0, 0)

    def _analyze_results(self) -> dict:
        """Analyze load test results."""
        if not self.results:
            return {'error': 'No results collected'}

        latencies = [r[1] for r in self.results if r[0] == 'success']
        errors = sum(1 for r in self.results if r[0] != 'success')

        if not latencies:
            return {
                'total_requests': len(self.results),
                'successful_requests': 0,
                'failed_requests': errors,
                'error_rate': 1.0,
            }

        latencies.sort()
        return {
            'total_requests': len(self.results),
            'successful_requests': len(latencies),
            'failed_requests': errors,
            'error_rate': errors / len(self.results),
            'p50_latency_ms': latencies[len(latencies) // 2] * 1000,
            'p95_latency_ms': latencies[int(len(latencies) * 0.95)] * 1000,
            'p99_latency_ms': latencies[int(len(latencies) * 0.99)] * 1000,
            'max_latency_ms': max(latencies) * 1000,
        }


if __name__ == '__main__':
    # Example usage
    tester = LoadTester('http://localhost:3000', num_users=100)
    results = tester.load_test(duration_seconds=10)
    print("Load Test Results:")
    for key, value in results.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
