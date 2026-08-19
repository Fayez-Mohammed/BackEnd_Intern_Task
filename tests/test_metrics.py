"""
Unit tests for high-resolution timer, statistics calculations, and metrics collector.
"""

import time
import unittest
from pathlib import Path
from benchmark.metrics.timer import HighResolutionTimer
from benchmark.metrics.stats import calculate_percentiles, summarize_latencies
from benchmark.metrics.collector import MetricsCollector


class TestMetrics(unittest.TestCase):
    def test_high_resolution_timer(self):
        with HighResolutionTimer() as timer:
            time.sleep(0.01)  # 10ms
        self.assertGreaterEqual(timer.elapsed_ms, 8.0)
        self.assertLess(timer.elapsed_ms, 100.0)

    def test_percentile_calculations(self):
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        stats = calculate_percentiles(latencies)
        self.assertEqual(stats["p50_ms"], 55.0)
        self.assertAlmostEqual(stats["p90_ms"], 91.0, places=0)
        self.assertEqual(stats["min_ms"], 10.0)
        self.assertEqual(stats["max_ms"], 100.0)
        self.assertEqual(stats["count"], 10)

    def test_empty_percentiles(self):
        stats = calculate_percentiles([])
        self.assertEqual(stats["count"], 0)
        self.assertEqual(stats["p50_ms"], 0.0)

    def test_summarize_latencies(self):
        summary = summarize_latencies(
            database="test_db",
            workload="test_workload",
            latencies_ms=[5.0, 10.0, 15.0],
            total_duration_sec=0.1
        )
        self.assertEqual(summary["database"], "test_db")
        self.assertEqual(summary["total_operations"], 3)
        self.assertGreater(summary["throughput_qps"], 0.0)


if __name__ == "__main__":
    unittest.main()
